"""
FastAPI routes for the AI Agent.
Provides SSE streaming for chat, config management, and session control.
"""
import json
import os
import uuid
import asyncio
from typing import Optional

from fastapi import APIRouter, Request, HTTPException  # pyright: ignore[reportMissingImports]
from fastapi.responses import StreamingResponse, JSONResponse  # pyright: ignore[reportMissingImports]
from pydantic import BaseModel  # pyright: ignore[reportMissingImports]

from .agent_service import agent_service
from .config import AgentConfig, config as global_config

router = APIRouter(prefix="/api/agent", tags=["agent"])


# ── Request/Response Models ─────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    workspace_root: Optional[str] = None

class ConfigUpdate(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_iterations: Optional[int] = None
    auto_approve_reads: Optional[bool] = None
    auto_approve_writes: Optional[bool] = None
    auto_approve_deletes: Optional[bool] = None
    auto_approve_terminal: Optional[bool] = None
    max_tokens: Optional[int] = None


# ── SSE Chat Endpoint ───────────────────────────────────────────────

@router.post("/chat")
async def agent_chat(req: ChatRequest):
    """Stream agent responses as Server-Sent Events."""
    session_id = req.session_id or str(uuid.uuid4())
    workspace_root = req.workspace_root or ''

    # The backend dir is where app.py / agent/ / projects/ live
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Resolve relative paths against the MAIN PROJECT ROOT (parent of backend/)
    if workspace_root and not os.path.isabs(workspace_root):
        # e.g. "backend/projects/project_xxx" → resolve from repo root
        repo_root = os.path.dirname(backend_dir)
        workspace_root = os.path.normpath(os.path.join(repo_root, workspace_root))

    # If still empty, try to find the most recent uploaded project
    if not workspace_root or not os.path.isdir(workspace_root):
        projects_dir = os.path.join(backend_dir, 'projects')
        if os.path.isdir(projects_dir):
            project_dirs = sorted(
                [d for d in os.listdir(projects_dir) if os.path.isdir(os.path.join(projects_dir, d))],
                key=lambda d: os.path.getmtime(os.path.join(projects_dir, d)),
                reverse=True,
            )
            if project_dirs:
                workspace_root = os.path.join(projects_dir, project_dirs[0])

    # Final fallback: use global config or repo root
    if not workspace_root or not os.path.isdir(workspace_root):
        workspace_root = global_config.workspace_root or os.path.dirname(backend_dir)

    session = agent_service.get_or_create_session(session_id, workspace_root)

    if session.is_running:
        return JSONResponse(
            status_code=409,
            content={"error": "Agent is already running in this session. Wait or stop it first."}
        )

    async def event_stream():
        try:
            async for event in agent_service.chat_stream(session, req.message, global_config):
                data = json.dumps(event, ensure_ascii=False)
                yield f"data: {data}\n\n"
            yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
        except asyncio.CancelledError:
            yield f"data: {json.dumps({'type': 'cancelled'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": session_id,
        }
    )


# ── Session Management ──────────────────────────────────────────────

@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session status and history."""
    session = agent_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "is_running": session.is_running,
        "iteration": session.iteration,
        "total_tokens": session.total_tokens,
        "message_count": len(session.messages),
        "workspace_root": session.workspace_root,
    }


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear a session's conversation history."""
    agent_service.clear_session(session_id)
    return {"status": "cleared"}


@router.post("/session/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop a running agent session."""
    session = agent_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.is_running = False
    return {"status": "stopping"}


# ── History ─────────────────────────────────────────────────────────

@router.get("/session/{session_id}/history")
async def get_history(session_id: str):
    """Get conversation history for a session."""
    session = agent_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    history = []
    for msg in session.messages:
        if msg.role == 'system':
            continue
        entry = {"role": msg.role}
        if msg.content:
            entry["content"] = msg.content
        if msg.tool_calls:
            entry["tool_calls"] = msg.tool_calls
        if msg.name:
            entry["tool_name"] = msg.name
        history.append(entry)
    return {"session_id": session_id, "history": history}


# ── Config Endpoints ────────────────────────────────────────────────

@router.get("/config")
async def get_config():
    """Get current agent configuration (API key is masked)."""
    return {
        "api_key": ("sk-..." + global_config.api_key[-4:]) if len(global_config.api_key) > 8 else ("set" if global_config.api_key else ""),
        "model": global_config.model,
        "temperature": global_config.temperature,
        "max_iterations": global_config.max_iterations,
        "auto_approve_reads": global_config.auto_approve_reads,
        "auto_approve_writes": global_config.auto_approve_writes,
        "auto_approve_deletes": global_config.auto_approve_deletes,
        "auto_approve_terminal": global_config.auto_approve_terminal,
        "max_tokens": global_config.max_tokens,
        "has_key": bool(global_config.api_key),
    }


@router.post("/config")
async def update_config(update: ConfigUpdate):
    """Update agent configuration."""
    if update.api_key is not None:
        global_config.api_key = update.api_key
    if update.model is not None:
        global_config.model = update.model
    if update.temperature is not None:
        global_config.temperature = max(0.0, min(2.0, update.temperature))
    if update.max_iterations is not None:
        global_config.max_iterations = max(1, min(50, update.max_iterations))
    if update.auto_approve_reads is not None:
        global_config.auto_approve_reads = update.auto_approve_reads
    if update.auto_approve_writes is not None:
        global_config.auto_approve_writes = update.auto_approve_writes
    if update.auto_approve_deletes is not None:
        global_config.auto_approve_deletes = update.auto_approve_deletes
    if update.auto_approve_terminal is not None:
        global_config.auto_approve_terminal = update.auto_approve_terminal
    if update.max_tokens is not None:
        global_config.max_tokens = max(256, min(16384, update.max_tokens))

    global_config.save()
    return {"status": "updated"}


# ── Health ──────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {
        "status": "ok",
        "has_api_key": bool(global_config.api_key),
        "model": global_config.model,
        "active_sessions": len(agent_service.sessions),
    }
