/**
 * React hook for the AI Agent system.
 * Handles SSE streaming, message management, config, and IndexedDB persistence.
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import type { AgentConfig, AgentEvent, ChatMessage, ToolCallInfo } from '@/types/agent';
import * as chatDb from '@/lib/chat-db';
import type { StoredChat } from '@/lib/chat-db';

const API_BASE = 'http://localhost:8000/api/agent';

function genId() {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function useAgent() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [chatId, setChatId] = useState<string>(() => `chat_${Date.now()}`);
  const [sessionId, setSessionId] = useState<string>(() => `agent_${Date.now()}`);
  const [chatList, setChatList] = useState<StoredChat[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [error, setError] = useState<string | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Load chat list from IndexedDB on mount ────────────────────────
  const refreshChatList = useCallback(async () => {
    try {
      const chats = await chatDb.getAllChats();
      setChatList(chats);
    } catch { /* IndexedDB not available */ }
  }, []);

  useEffect(() => { refreshChatList(); }, [refreshChatList]);

  // ── Auto-save messages to IndexedDB (debounced) ───────────────────
  const persistMessages = useCallback(async (msgs: ChatMessage[], currentChatId: string) => {
    if (msgs.length === 0) return;
    try {
      // Ensure chat exists
      const existing = await chatDb.getChat(currentChatId);
      if (!existing) {
        const firstUser = msgs.find(m => m.role === 'user');
        const title = firstUser ? chatDb.generateTitle(firstUser.content) : `Chat ${new Date().toLocaleString()}`;
        await chatDb.createChat(currentChatId, title, 'gpt-4o');
      }

      // Save all messages
      const storedMsgs = msgs
        .filter(m => m.role !== 'status')
        .map(m => ({
          id: m.id,
          chatId: currentChatId,
          role: m.role,
          content: m.content,
          timestamp: m.timestamp,
          toolCalls: m.toolCalls,
        }));
      await chatDb.saveMessages(storedMsgs);

      // Update chat metadata
      const lastMsg = msgs.filter(m => m.role !== 'status').pop();
      await chatDb.updateChat(currentChatId, {
        messageCount: storedMsgs.length,
        preview: lastMsg ? lastMsg.content.slice(0, 100) : '',
      });

      refreshChatList();
    } catch { /* ignore persistence errors */ }
  }, [refreshChatList]);

  const scheduleSave = useCallback((msgs: ChatMessage[], cid: string) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => persistMessages(msgs, cid), 500);
  }, [persistMessages]);

  // ── Load a specific chat from IndexedDB ───────────────────────────
  const loadChat = useCallback(async (id: string) => {
    try {
      const msgs = await chatDb.getMessages(id);
      const chatMessages: ChatMessage[] = msgs.map(m => ({
        id: m.id,
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
        toolCalls: m.toolCalls,
        isStreaming: false,
      }));
      setMessages(chatMessages);
      setChatId(id);
      setActiveChatId(id);
      // Create a new backend session for resumed chats
      setSessionId(`agent_${Date.now()}`);
      setError(null);
    } catch { /* ignore */ }
  }, []);

  // ── Start a new chat ──────────────────────────────────────────────
  const newChat = useCallback(() => {
    const id = `chat_${Date.now()}`;
    setChatId(id);
    setActiveChatId(null);
    setSessionId(`agent_${Date.now()}`);
    setMessages([]);
    setError(null);
    // Clear backend session
    fetch(`${API_BASE}/session/${sessionId}`, { method: 'DELETE' }).catch(() => {});
  }, [sessionId]);

  // ── Delete a chat ─────────────────────────────────────────────────
  const deleteChatById = useCallback(async (id: string) => {
    try {
      await chatDb.deleteChat(id);
      if (chatId === id) newChat();
      refreshChatList();
    } catch { /* ignore */ }
  }, [chatId, newChat, refreshChatList]);

  // ── Rename a chat ─────────────────────────────────────────────────
  const renameChat = useCallback(async (id: string, title: string) => {
    try {
      await chatDb.updateChat(id, { title });
      refreshChatList();
    } catch { /* ignore */ }
  }, [refreshChatList]);

  // ── Pin/unpin a chat ──────────────────────────────────────────────
  const togglePinChat = useCallback(async (id: string) => {
    try {
      const chat = await chatDb.getChat(id);
      if (chat) {
        await chatDb.updateChat(id, { pinned: !chat.pinned });
        refreshChatList();
      }
    } catch { /* ignore */ }
  }, [refreshChatList]);

  // ── Search chats ──────────────────────────────────────────────────
  const searchChats = useCallback(async (query: string) => {
    if (!query.trim()) { refreshChatList(); return; }
    try {
      const results = await chatDb.searchChats(query);
      setChatList(results);
    } catch { /* ignore */ }
  }, [refreshChatList]);

  // ── Load config from backend ──────────────────────────────────────
  const loadConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/config`);
      if (res.ok) {
        const data = await res.json();
        setConfig(data);
        return data;
      }
    } catch {
      // Backend not available
    }
    return null;
  }, []);

  // ── Update config ─────────────────────────────────────────────────
  const updateConfig = useCallback(async (updates: Partial<AgentConfig>) => {
    try {
      const res = await fetch(`${API_BASE}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (res.ok) {
        await loadConfig();
        return true;
      }
    } catch {
      // Backend not available
    }
    return false;
  }, [loadConfig]);

  // ── Send message to agent (SSE streaming) ─────────────────────────
  const sendMessage = useCallback(async (message: string, workspaceRoot: string) => {
    setError(null);
    const currentChatId = chatId;
    setActiveChatId(currentChatId);

    // Add user message
    const userMsg: ChatMessage = {
      id: genId(),
      role: 'user',
      content: message,
      timestamp: Date.now(),
    };
    setMessages(prev => { const n = [...prev, userMsg]; scheduleSave(n, currentChatId); return n; });

    // Create assistant message placeholder for streaming
    const assistantId = genId();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      toolCalls: [],
      isStreaming: true,
    };
    setMessages(prev => [...prev, assistantMsg]);
    setIsRunning(true);

    const abort = new AbortController();
    abortRef.current = abort;

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          session_id: sessionId,
          workspace_root: workspaceRoot,
        }),
        signal: abort.signal,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
        throw new Error(errData.error || `HTTP ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr) continue;

          let event: AgentEvent;
          try {
            event = JSON.parse(jsonStr);
          } catch {
            continue;
          }

          // Process event
          switch (event.type) {
            case 'content':
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: m.content + (event.text || '') }
                  : m
              ));
              break;

            case 'status':
              setMessages(prev => {
                const last = prev[prev.length - 1];
                if (last?.role === 'status') {
                  return [...prev.slice(0, -1), { ...last, content: event.message || '' }];
                }
                return [...prev, {
                  id: genId(),
                  role: 'status',
                  content: event.message || '',
                  timestamp: Date.now(),
                }];
              });
              break;

            case 'tool_call': {
              const toolCall: ToolCallInfo = {
                id: event.tool_call_id || genId(),
                tool: event.tool || '',
                arguments: event.arguments || {},
                status: 'pending',
                needs_approval: event.needs_approval,
              };
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, toolCalls: [...(m.toolCalls || []), toolCall] }
                  : m
              ));
              break;
            }

            case 'tool_executing':
              setMessages(prev => prev.map(m => {
                if (m.id !== assistantId) return m;
                const calls = (m.toolCalls || []).map(tc =>
                  tc.tool === event.tool && tc.status === 'pending'
                    ? { ...tc, status: 'executing' as const }
                    : tc
                );
                return { ...m, toolCalls: calls };
              }));
              break;

            case 'tool_result':
              setMessages(prev => prev.map(m => {
                if (m.id !== assistantId) return m;
                const calls = (m.toolCalls || []).map(tc =>
                  tc.id === event.tool_call_id
                    ? { ...tc, status: 'done' as const, result: event.result }
                    : tc
                );
                return { ...m, toolCalls: calls };
              }));
              break;

            case 'error':
              setError(event.message || 'Unknown error');
              setMessages(prev => [...prev, {
                id: genId(),
                role: 'error',
                content: event.message || 'Unknown error',
                timestamp: Date.now(),
              }]);
              break;

            case 'done':
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, isStreaming: false } : m
              ));
              break;

            case 'stream_end':
            case 'cancelled':
              break;
          }
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setMessages(prev => [...prev, {
          id: genId(),
          role: 'status',
          content: 'Agent stopped.',
          timestamp: Date.now(),
        }]);
      } else {
        const errMsg = err.message || 'Failed to communicate with agent';
        setError(errMsg);
        setMessages(prev => [...prev, {
          id: genId(),
          role: 'error',
          content: errMsg,
          timestamp: Date.now(),
        }]);
      }
    } finally {
      setIsRunning(false);
      abortRef.current = null;
      // Remove trailing status messages
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last?.role === 'status') return prev.slice(0, -1);
        return prev;
      });
      // Mark assistant as not streaming & persist
      setMessages(prev => {
        const final = prev.map(m => m.isStreaming ? { ...m, isStreaming: false } : m);
        persistMessages(final, currentChatId);
        return final;
      });
    }
  }, [sessionId, chatId, scheduleSave, persistMessages]);

  // ── Stop agent ────────────────────────────────────────────────────
  const stopAgent = useCallback(() => {
    abortRef.current?.abort();
    fetch(`${API_BASE}/session/${sessionId}/stop`, { method: 'POST' }).catch(() => {});
  }, [sessionId]);

  // ── Clear current chat messages ───────────────────────────────────
  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
    fetch(`${API_BASE}/session/${sessionId}`, { method: 'DELETE' }).catch(() => {});
  }, [sessionId]);

  return {
    messages,
    isRunning,
    config,
    error,
    sessionId,
    chatId,
    chatList,
    activeChatId,
    sendMessage,
    stopAgent,
    clearMessages,
    loadConfig,
    updateConfig,
    loadChat,
    newChat,
    deleteChatById,
    renameChat,
    togglePinChat,
    searchChats,
    refreshChatList,
  };
}
