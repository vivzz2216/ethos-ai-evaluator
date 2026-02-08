"""
ETHOS AI Agent Service
Core orchestration engine using OpenAI's function-calling API.
Manages conversation, tool execution, and streaming responses.
"""
import json
import time
import asyncio
import traceback
from typing import AsyncGenerator, Optional, List, Dict, Any
from dataclasses import dataclass, field

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

from .config import AgentConfig
from .tools import file_operations, search_tools, terminal_executor, code_analysis

# ── Tool Definitions (OpenAI function-calling schema) ───────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file from workspace root"}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file or overwrite an existing file with the given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path for the new file"},
                    "content": {"type": "string", "description": "Full content to write to the file"}
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file by replacing a specific unique string with a new string. The old_string must appear exactly once in the file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file"},
                    "old_string": {"type": "string", "description": "The exact string to find and replace (must be unique in file)"},
                    "new_string": {"type": "string", "description": "The replacement string"}
                },
                "required": ["file_path", "old_string", "new_string"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file or directory from the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file or directory to delete"}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rename_file",
            "description": "Rename or move a file/directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_path": {"type": "string", "description": "Current relative path"},
                    "new_path": {"type": "string", "description": "New relative path"}
                },
                "required": ["old_path", "new_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in a given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {"type": "string", "description": "Relative directory path (use '.' for workspace root)", "default": "."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_tree",
            "description": "Get a tree view of the project structure (ignoring node_modules, .git, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_depth": {"type": "integer", "description": "Maximum depth to traverse", "default": 3}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search for a text pattern across files in the workspace. Supports regex.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern (regex supported)"},
                    "file_glob": {"type": "string", "description": "Glob to filter files, e.g. '*.py' or '*.tsx'", "default": "*"}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "Find files or directories matching a glob pattern by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern to match, e.g. '*.py' or 'test_*'"},
                    "file_type": {"type": "string", "enum": ["any", "file", "directory"], "default": "any"}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a terminal/shell command in the workspace directory. Use for installing packages, running scripts, git commands, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)", "default": 30}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_file",
            "description": "Analyze a code file to extract its structure: functions, classes, imports, exports.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file to analyze"}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_project",
            "description": "Analyze the overall project: detect tech stack, frameworks, dependencies, and entry points.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_environment_info",
            "description": "Get information about the current environment: OS, installed tools (node, python, git, etc).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
]

SYSTEM_PROMPT = """You are ETHOS Agent, an autonomous AI coding assistant. You help users by executing tasks in their codebase.

CAPABILITIES:
- Read, create, edit, and delete files
- Search code with grep and find
- Analyze code structure and project setup
- Run terminal commands (install packages, run scripts, git, etc.)
- Understand project architecture

RULES:
1. Always explore the codebase FIRST before making changes. Use get_project_tree, read_file, analyze_project to understand context.
2. Make precise, minimal edits. Don't rewrite entire files unless necessary.
3. When creating files, include all necessary imports and ensure the code is immediately runnable.
4. Explain what you're doing and why at each step.
5. If a task is ambiguous, state your assumptions before proceeding.
6. For destructive operations (delete, overwrite), explain what will be affected.
7. After making changes, verify them if possible (e.g., read the file back, run a test).
8. Keep the user informed of progress on multi-step tasks.
9. If you encounter an error, analyze it and try a different approach.
10. Never execute dangerous commands that could harm the system.

When the user asks you to do something, break it into steps, execute each step using the available tools, and report the results."""


@dataclass
class ConversationMessage:
    role: str  # 'system', 'user', 'assistant', 'tool'
    content: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

    def to_openai(self) -> dict:
        msg = {"role": self.role}
        if self.content is not None:
            msg["content"] = self.content
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name and self.role == 'tool':
            msg["name"] = self.name
        return msg


@dataclass
class AgentSession:
    session_id: str
    workspace_root: str
    messages: List[ConversationMessage] = field(default_factory=list)
    is_running: bool = False
    iteration: int = 0
    total_tokens: int = 0
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.messages:
            self.messages.append(ConversationMessage(role="system", content=SYSTEM_PROMPT))


# ── Agent Service ───────────────────────────────────────────────────

class AgentService:
    def __init__(self):
        self.sessions: Dict[str, AgentSession] = {}

    def get_or_create_session(self, session_id: str, workspace_root: str) -> AgentSession:
        if session_id not in self.sessions:
            self.sessions[session_id] = AgentSession(session_id=session_id, workspace_root=workspace_root)
        return self.sessions[session_id]

    def get_session(self, session_id: str) -> Optional[AgentSession]:
        return self.sessions.get(session_id)

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]

    def _execute_tool(self, session: AgentSession, tool_name: str, arguments: dict) -> dict:
        """Execute a tool call and return the result."""
        ws = session.workspace_root
        try:
            if tool_name == "read_file":
                return file_operations.read_file(ws, arguments["file_path"])
            elif tool_name == "create_file":
                return file_operations.create_file(ws, arguments["file_path"], arguments["content"])
            elif tool_name == "edit_file":
                return file_operations.edit_file(ws, arguments["file_path"], arguments["old_string"], arguments["new_string"])
            elif tool_name == "delete_file":
                return file_operations.delete_file(ws, arguments["file_path"])
            elif tool_name == "rename_file":
                return file_operations.rename_file(ws, arguments["old_path"], arguments["new_path"])
            elif tool_name == "list_directory":
                return file_operations.list_directory(ws, arguments.get("dir_path", "."))
            elif tool_name == "get_project_tree":
                return file_operations.get_project_tree(ws, arguments.get("max_depth", 3))
            elif tool_name == "grep_search":
                return search_tools.grep_search(ws, arguments["pattern"], arguments.get("file_glob", "*"))
            elif tool_name == "find_files":
                return search_tools.find_files(ws, arguments["pattern"], arguments.get("file_type", "any"))
            elif tool_name == "run_command":
                return terminal_executor.run_command(ws, arguments["command"], arguments.get("timeout", 30))
            elif tool_name == "analyze_file":
                return code_analysis.analyze_file(ws, arguments["file_path"])
            elif tool_name == "analyze_project":
                return code_analysis.analyze_project(ws)
            elif tool_name == "get_environment_info":
                return terminal_executor.get_environment_info(ws)
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"success": False, "error": f"Tool execution error: {str(e)}", "traceback": traceback.format_exc()[:500]}

    async def chat_stream(self, session: AgentSession, user_message: str, config: AgentConfig) -> AsyncGenerator[dict, None]:
        """Stream agent responses. Yields event dicts for SSE."""
        if not config.api_key:
            yield {"type": "error", "message": "OpenAI API key not configured. Go to Agent Settings to add your key."}
            return

        if AsyncOpenAI is None:
            yield {"type": "error", "message": "openai package not installed. Run: pip install openai>=1.0.0"}
            return

        client = AsyncOpenAI(api_key=config.api_key)

        # Add user message
        session.messages.append(ConversationMessage(role="user", content=user_message))
        session.is_running = True
        session.iteration = 0

        try:
            while session.iteration < config.max_iterations:
                session.iteration += 1
                yield {"type": "status", "message": f"Thinking... (step {session.iteration})", "iteration": session.iteration}

                # Build messages for API
                api_messages = [m.to_openai() for m in session.messages]

                # Call OpenAI with streaming
                try:
                    stream = await client.chat.completions.create(
                        model=config.model,
                        messages=api_messages,
                        tools=TOOLS,
                        tool_choice="auto",
                        temperature=config.temperature,
                        max_tokens=config.max_tokens,
                        stream=True,
                    )
                except Exception as api_err:
                    err_msg = str(api_err)
                    if 'api_key' in err_msg.lower() or 'auth' in err_msg.lower():
                        yield {"type": "error", "message": "Invalid OpenAI API key. Check your key in Agent Settings."}
                    elif 'rate_limit' in err_msg.lower() or '429' in err_msg:
                        yield {"type": "error", "message": "Rate limited by OpenAI. Please wait a moment and try again."}
                    elif 'model' in err_msg.lower():
                        yield {"type": "error", "message": f"Model error: {err_msg}. Try switching to a different model."}
                    else:
                        yield {"type": "error", "message": f"OpenAI API error: {err_msg}"}
                    break

                # Collect streamed response
                assistant_content = ""
                tool_calls_raw: Dict[int, Dict] = {}
                finish_reason = None

                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if not delta:
                        continue
                    finish_reason = chunk.choices[0].finish_reason

                    # Stream text content
                    if delta.content:
                        assistant_content += delta.content
                        yield {"type": "content", "text": delta.content}

                    # Accumulate tool calls
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_raw:
                                tool_calls_raw[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
                            if tc.id:
                                tool_calls_raw[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    tool_calls_raw[idx]["function"]["name"] += tc.function.name
                                if tc.function.arguments:
                                    tool_calls_raw[idx]["function"]["arguments"] += tc.function.arguments

                    if chunk.usage:
                        session.total_tokens += chunk.usage.total_tokens

                # Build tool_calls list
                tool_calls = []
                if tool_calls_raw:
                    for idx in sorted(tool_calls_raw.keys()):
                        tc = tool_calls_raw[idx]
                        tool_calls.append({
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"]["arguments"],
                            }
                        })

                # Save assistant message
                session.messages.append(ConversationMessage(
                    role="assistant",
                    content=assistant_content if assistant_content else None,
                    tool_calls=tool_calls if tool_calls else None,
                ))

                # If no tool calls, we're done
                if not tool_calls:
                    yield {"type": "done", "iterations": session.iteration, "total_tokens": session.total_tokens}
                    break

                # Execute each tool call
                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    try:
                        fn_args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        fn_args = {}

                    # Check if this needs approval
                    needs_approval = False
                    if fn_name in ('delete_file', 'rename_file') and not config.auto_approve_deletes:
                        needs_approval = True
                    elif fn_name in ('create_file', 'edit_file') and not config.auto_approve_writes:
                        needs_approval = True
                    elif fn_name == 'run_command' and not config.auto_approve_terminal:
                        danger = terminal_executor.is_dangerous(fn_args.get('command', ''))
                        if danger:
                            needs_approval = True

                    yield {
                        "type": "tool_call",
                        "tool": fn_name,
                        "arguments": fn_args,
                        "tool_call_id": tc["id"],
                        "needs_approval": needs_approval,
                    }

                    # Execute the tool
                    yield {"type": "tool_executing", "tool": fn_name}
                    result = self._execute_tool(session, fn_name, fn_args)
                    # Truncate large results for context window
                    result_str = json.dumps(result, ensure_ascii=False)
                    if len(result_str) > 8000:
                        result_str = result_str[:8000] + '... [truncated]'

                    yield {
                        "type": "tool_result",
                        "tool": fn_name,
                        "result": result,
                        "tool_call_id": tc["id"],
                    }

                    # Add tool result to messages
                    session.messages.append(ConversationMessage(
                        role="tool",
                        content=result_str,
                        tool_call_id=tc["id"],
                        name=fn_name,
                    ))

            else:
                yield {"type": "error", "message": f"Reached maximum iterations ({config.max_iterations}). Task may be incomplete."}

        except asyncio.CancelledError:
            yield {"type": "status", "message": "Agent stopped by user."}
        except Exception as e:
            yield {"type": "error", "message": f"Agent error: {str(e)}"}
        finally:
            session.is_running = False


# Singleton
agent_service = AgentService()
