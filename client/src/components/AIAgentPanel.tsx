import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Send, Square, Trash2, Bot, User, AlertCircle, Loader2,
  FileText, FolderOpen, Search, Terminal as TerminalIcon,
  Code, ChevronDown, ChevronRight, Check, X, Settings,
  Sparkles, Zap, Brain, Key, RefreshCw, Plus, Pin, PinOff,
  MessageSquare, Clock, Edit3, ArrowLeft,
} from 'lucide-react';
import { useAgent } from '@/hooks/use-agent';
import type { ChatMessage, ToolCallInfo, AgentConfig } from '@/types/agent';
import type { StoredChat } from '@/lib/chat-db';
import { formatTimestamp } from '@/lib/chat-db';

// ── Tool Icon Map ──────────────────────────────────────────────────
const TOOL_ICONS: Record<string, React.ElementType> = {
  read_file: FileText,
  create_file: FileText,
  edit_file: Code,
  delete_file: Trash2,
  rename_file: FileText,
  list_directory: FolderOpen,
  get_project_tree: FolderOpen,
  grep_search: Search,
  find_files: Search,
  run_command: TerminalIcon,
  analyze_file: Code,
  analyze_project: Brain,
  get_environment_info: TerminalIcon,
};

const TOOL_COLORS: Record<string, string> = {
  read_file: '#3b82f6',
  create_file: '#22c55e',
  edit_file: '#eab308',
  delete_file: '#ef4444',
  rename_file: '#a855f7',
  list_directory: '#06b6d4',
  get_project_tree: '#06b6d4',
  grep_search: '#f97316',
  find_files: '#f97316',
  run_command: '#8b5cf6',
  analyze_file: '#ec4899',
  analyze_project: '#14b8a6',
  get_environment_info: '#64748b',
};

// ── Tool Call Component ────────────────────────────────────────────
const ToolCallView: React.FC<{ tc: ToolCallInfo }> = ({ tc }) => {
  const [expanded, setExpanded] = useState(false);
  const Icon = TOOL_ICONS[tc.tool] || Code;
  const color = TOOL_COLORS[tc.tool] || '#888';

  const statusIcon = tc.status === 'executing'
    ? <Loader2 className="w-3 h-3 animate-spin" style={{ color }} />
    : tc.status === 'done'
    ? <Check className="w-3 h-3 text-green-400" />
    : tc.status === 'error'
    ? <X className="w-3 h-3 text-red-400" />
    : <Loader2 className="w-3 h-3 text-[#666]" />;

  const argSummary = Object.entries(tc.arguments || {})
    .map(([k, v]) => {
      const val = typeof v === 'string' ? (v.length > 60 ? v.slice(0, 60) + '...' : v) : JSON.stringify(v).slice(0, 60);
      return `${k}: ${val}`;
    })
    .join(', ');

  return (
    <div className="my-1.5 rounded border border-[#3e3e42] bg-[#1e1e1e] overflow-hidden">
      <div
        className="flex items-center gap-2 px-2.5 py-1.5 cursor-pointer hover:bg-[#2a2a2a] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? <ChevronDown className="w-3 h-3 text-[#888]" /> : <ChevronRight className="w-3 h-3 text-[#888]" />}
        <Icon className="w-3.5 h-3.5 flex-shrink-0" style={{ color }} />
        <span className="text-[12px] font-mono flex-1 truncate" style={{ color }}>
          {tc.tool}
        </span>
        <span className="text-[10px] text-[#666] truncate max-w-[200px]">{argSummary}</span>
        {statusIcon}
      </div>
      {expanded && (
        <div className="px-3 py-2 border-t border-[#3e3e42] text-[11px] font-mono">
          <div className="text-[#888] mb-1">Arguments:</div>
          <pre className="text-[#ccc] whitespace-pre-wrap break-all max-h-[150px] overflow-y-auto">
            {JSON.stringify(tc.arguments, null, 2)}
          </pre>
          {tc.result && (
            <>
              <div className="text-[#888] mt-2 mb-1">Result:</div>
              <pre className="text-[#aaa] whitespace-pre-wrap break-all max-h-[200px] overflow-y-auto">
                {JSON.stringify(tc.result, null, 2).slice(0, 2000)}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  );
};

// ── Message Component ──────────────────────────────────────────────
const MessageView: React.FC<{ msg: ChatMessage }> = ({ msg }) => {
  if (msg.role === 'status') {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 text-[11px] text-[#888]">
        <Loader2 className="w-3 h-3 animate-spin" />
        {msg.content}
      </div>
    );
  }

  if (msg.role === 'error') {
    return (
      <div className="flex items-start gap-2 px-3 py-2 mx-2 my-1 rounded bg-red-500/10 border border-red-500/20">
        <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
        <span className="text-[12px] text-red-300">{msg.content}</span>
      </div>
    );
  }

  const isUser = msg.role === 'user';
  return (
    <div className={`px-3 py-2.5 ${isUser ? 'bg-[#2a2d36]' : ''}`}>
      <div className="flex items-start gap-2">
        <div className={`w-6 h-6 rounded flex items-center justify-center flex-shrink-0 mt-0.5 ${
          isUser ? 'bg-[#007acc]' : 'bg-[#5b21b6]'
        }`}>
          {isUser
            ? <User className="w-3.5 h-3.5 text-white" />
            : <Bot className="w-3.5 h-3.5 text-white" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] text-[#888] mb-0.5 font-semibold uppercase tracking-wider">
            {isUser ? 'You' : 'ETHOS Agent'}
            {msg.isStreaming && <span className="ml-1 text-[#007acc]">●</span>}
          </div>
          {msg.content && (
            <div className="text-[13px] text-[#ccc] leading-relaxed whitespace-pre-wrap break-words">
              {msg.content}
              {msg.isStreaming && !msg.content && (
                <span className="inline-flex gap-0.5">
                  <span className="w-1 h-1 rounded-full bg-[#888] animate-pulse" />
                  <span className="w-1 h-1 rounded-full bg-[#888] animate-pulse" style={{ animationDelay: '0.2s' }} />
                  <span className="w-1 h-1 rounded-full bg-[#888] animate-pulse" style={{ animationDelay: '0.4s' }} />
                </span>
              )}
            </div>
          )}
          {msg.toolCalls && msg.toolCalls.length > 0 && (
            <div className="mt-2">
              {msg.toolCalls.map(tc => (
                <ToolCallView key={tc.id} tc={tc} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ── Settings Inline Panel ──────────────────────────────────────────
const AgentSettingsPanel: React.FC<{
  config: AgentConfig | null;
  onUpdate: (updates: Partial<AgentConfig>) => Promise<boolean>;
  onClose: () => void;
  backendAvailable: boolean;
}> = ({ config, onUpdate, onClose, backendAvailable }) => {
  const [apiKey, setApiKey] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSaveKey = async () => {
    if (!apiKey.trim()) return;
    setSaving(true);
    await onUpdate({ api_key: apiKey.trim() });
    setApiKey('');
    setSaving(false);
  };

  if (!backendAvailable) {
    return (
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[12px] font-semibold text-[#ccc]">Agent Settings</span>
          <button onClick={onClose} className="p-1 hover:bg-[#3e3e42] rounded"><X className="w-3.5 h-3.5 text-[#888]" /></button>
        </div>
        <div className="p-3 rounded bg-red-500/10 border border-red-500/20 text-[12px] text-red-300">
          Backend not available. Start it with: <code className="bg-[#333] px-1 rounded">python backend/app.py</code>
        </div>
      </div>
    );
  }

  return (
    <div className="p-3 border-b border-[#3e3e42]">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[12px] font-semibold text-[#ccc]">Agent Settings</span>
        <button onClick={onClose} className="p-1 hover:bg-[#3e3e42] rounded"><X className="w-3.5 h-3.5 text-[#888]" /></button>
      </div>

      {/* API Key */}
      <div className="mb-3">
        <label className="text-[11px] text-[#888] block mb-1">OpenAI API Key</label>
        <div className="flex gap-1">
          <input
            type="password"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            placeholder={config?.has_key ? '••••••••••' : 'sk-...'}
            className="flex-1 bg-[#3c3c3c] text-[#ccc] text-[12px] px-2 py-1.5 rounded border border-[#3e3e42] outline-none focus:border-[#007acc]"
            onKeyDown={e => e.key === 'Enter' && handleSaveKey()}
          />
          <button
            onClick={handleSaveKey}
            disabled={saving || !apiKey.trim()}
            className="px-2 py-1 bg-[#007acc] text-white text-[11px] rounded hover:bg-[#006bb3] disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Key className="w-3 h-3" />}
          </button>
        </div>
        {config?.has_key && <span className="text-[10px] text-green-400 mt-0.5 block">✓ Key configured ({config.api_key})</span>}
      </div>

      {/* Model */}
      <div className="mb-3">
        <label className="text-[11px] text-[#888] block mb-1">Model</label>
        <select
          value={config?.model || 'gpt-4o'}
          onChange={e => onUpdate({ model: e.target.value })}
          className="w-full bg-[#3c3c3c] text-[#ccc] text-[12px] px-2 py-1.5 rounded border border-[#3e3e42] outline-none focus:border-[#007acc]"
        >
          <option value="gpt-4o">GPT-4o (Recommended)</option>
          <option value="gpt-4o-mini">GPT-4o Mini (Fast & Cheap)</option>
          <option value="gpt-4-turbo">GPT-4 Turbo</option>
          <option value="gpt-4">GPT-4</option>
          <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
        </select>
      </div>

      {/* Temperature */}
      <div className="mb-3">
        <label className="text-[11px] text-[#888] block mb-1">Temperature: {config?.temperature?.toFixed(1) || '0.7'}</label>
        <input
          type="range"
          min="0" max="2" step="0.1"
          value={config?.temperature || 0.7}
          onChange={e => onUpdate({ temperature: parseFloat(e.target.value) })}
          className="w-full h-1 accent-[#007acc]"
        />
      </div>

      {/* Max Iterations */}
      <div className="mb-3">
        <label className="text-[11px] text-[#888] block mb-1">Max Steps: {config?.max_iterations || 15}</label>
        <input
          type="range"
          min="1" max="30" step="1"
          value={config?.max_iterations || 15}
          onChange={e => onUpdate({ max_iterations: parseInt(e.target.value) })}
          className="w-full h-1 accent-[#007acc]"
        />
      </div>

      {/* Auto-approve toggles */}
      <div className="space-y-1.5">
        <label className="text-[11px] text-[#888] block">Auto-approve:</label>
        {[
          { key: 'auto_approve_writes', label: 'File writes' },
          { key: 'auto_approve_deletes', label: 'File deletes' },
          { key: 'auto_approve_terminal', label: 'Terminal commands' },
        ].map(({ key, label }) => (
          <label key={key} className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={(config as any)?.[key] || false}
              onChange={e => onUpdate({ [key]: e.target.checked })}
              className="accent-[#007acc]"
            />
            <span className="text-[11px] text-[#ccc]">{label}</span>
          </label>
        ))}
      </div>
    </div>
  );
};

// ── Main Agent Panel ───────────────────────────────────────────────
interface AIAgentPanelProps {
  workspaceRoot: string;
  onRefreshTree?: () => void;
}

const AIAgentPanel: React.FC<AIAgentPanelProps> = ({ workspaceRoot, onRefreshTree }) => {
  const {
    messages, isRunning, config, error,
    sendMessage, stopAgent, clearMessages,
    loadConfig, updateConfig,
    chatList, activeChatId, chatId,
    loadChat, newChat, deleteChatById, renameChat, togglePinChat, searchChats,
  } = useAgent();

  const [input, setInput] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [historySearch, setHistorySearch] = useState('');
  const [renamingChatId, setRenamingChatId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [backendAvailable, setBackendAvailable] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load config on mount
  useEffect(() => {
    loadConfig().then(cfg => {
      setBackendAvailable(cfg !== null);
      if (!cfg?.has_key) setShowSettings(true);
    });
  }, [loadConfig]);

  // Refresh file tree when agent finishes (files may have changed)
  const prevRunning = useRef(false);
  useEffect(() => {
    if (prevRunning.current && !isRunning && onRefreshTree) {
      onRefreshTree();
    }
    prevRunning.current = isRunning;
  }, [isRunning, onRefreshTree]);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = useCallback(() => {
    const msg = input.trim();
    if (!msg || isRunning) return;
    setInput('');
    sendMessage(msg, workspaceRoot);
    setShowHistory(false);
  }, [input, isRunning, sendMessage, workspaceRoot]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleHistorySearch = (q: string) => {
    setHistorySearch(q);
    searchChats(q);
  };

  const handleSelectChat = (id: string) => {
    loadChat(id);
    setShowHistory(false);
  };

  const handleRenameSubmit = (id: string) => {
    if (renameValue.trim()) {
      renameChat(id, renameValue.trim());
    }
    setRenamingChatId(null);
    setRenameValue('');
  };

  // ── Chat History View ─────────────────────────────────────────────
  if (showHistory) {
    return (
      <div className="h-full flex flex-col bg-[#252526] select-none">
        {/* History Header */}
        <div className="flex items-center justify-between px-3 h-[35px] flex-shrink-0 border-b border-[#3e3e42]">
          <div className="flex items-center gap-2">
            <button onClick={() => setShowHistory(false)} className="p-0.5 rounded hover:bg-[#3e3e42]">
              <ArrowLeft className="w-3.5 h-3.5 text-[#888]" />
            </button>
            <span className="text-[11px] font-semibold tracking-wider text-[#bbbbbb] uppercase">Chat History</span>
          </div>
          <button
            onClick={() => { newChat(); setShowHistory(false); }}
            className="p-1 rounded hover:bg-[#3e3e42] transition-colors"
            title="New Chat"
          >
            <Plus className="w-3.5 h-3.5 text-[#888]" />
          </button>
        </div>

        {/* Search */}
        <div className="px-2 py-1.5 border-b border-[#3e3e42]">
          <div className="flex items-center bg-[#3c3c3c] rounded px-2 h-[26px]">
            <Search className="w-3.5 h-3.5 text-[#666] flex-shrink-0" />
            <input
              value={historySearch}
              onChange={e => handleHistorySearch(e.target.value)}
              placeholder="Search chats..."
              className="bg-transparent text-[12px] text-[#ccc] placeholder-[#666] outline-none w-full ml-1.5"
            />
          </div>
        </div>

        {/* Chat List */}
        <div className="flex-1 overflow-y-auto">
          {chatList.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-4">
              <MessageSquare className="w-8 h-8 text-[#555] mb-2" />
              <p className="text-[12px] text-[#888]">No previous chats</p>
              <p className="text-[11px] text-[#666] mt-1">Start a conversation to see it here</p>
            </div>
          ) : (
            <div className="py-1">
              {chatList.map(chat => (
                <div
                  key={chat.id}
                  className={`group px-3 py-2 cursor-pointer border-b border-[#3e3e42]/50 transition-colors ${
                    chat.id === activeChatId ? 'bg-[#094771]/40' : 'hover:bg-[#2a2d2e]'
                  }`}
                  onClick={() => renamingChatId !== chat.id && handleSelectChat(chat.id)}
                >
                  <div className="flex items-start justify-between gap-1">
                    <div className="flex-1 min-w-0">
                      {renamingChatId === chat.id ? (
                        <input
                          autoFocus
                          value={renameValue}
                          onChange={e => setRenameValue(e.target.value)}
                          onKeyDown={e => { if (e.key === 'Enter') handleRenameSubmit(chat.id); if (e.key === 'Escape') setRenamingChatId(null); }}
                          onBlur={() => handleRenameSubmit(chat.id)}
                          className="w-full bg-[#3c3c3c] text-[12px] text-[#ccc] px-1.5 py-0.5 rounded border border-[#007acc] outline-none"
                          onClick={e => e.stopPropagation()}
                        />
                      ) : (
                        <div className="flex items-center gap-1">
                          {chat.pinned && <Pin className="w-2.5 h-2.5 text-[#007acc] flex-shrink-0" />}
                          <span className="text-[12px] text-[#ccc] truncate font-medium">{chat.title}</span>
                        </div>
                      )}
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] text-[#666]">{formatTimestamp(chat.updatedAt)}</span>
                        <span className="text-[10px] text-[#555]">{chat.messageCount} msgs</span>
                      </div>
                      {chat.preview && (
                        <p className="text-[10px] text-[#555] truncate mt-0.5">{chat.preview}</p>
                      )}
                    </div>
                    {/* Action buttons (visible on hover) */}
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                      <button
                        onClick={e => { e.stopPropagation(); togglePinChat(chat.id); }}
                        className="p-0.5 rounded hover:bg-[#3e3e42]"
                        title={chat.pinned ? 'Unpin' : 'Pin'}
                      >
                        {chat.pinned ? <PinOff className="w-3 h-3 text-[#007acc]" /> : <Pin className="w-3 h-3 text-[#888]" />}
                      </button>
                      <button
                        onClick={e => { e.stopPropagation(); setRenamingChatId(chat.id); setRenameValue(chat.title); }}
                        className="p-0.5 rounded hover:bg-[#3e3e42]"
                        title="Rename"
                      >
                        <Edit3 className="w-3 h-3 text-[#888]" />
                      </button>
                      <button
                        onClick={e => { e.stopPropagation(); if (confirm('Delete this chat?')) deleteChatById(chat.id); }}
                        className="p-0.5 rounded hover:bg-[#3e3e42]"
                        title="Delete"
                      >
                        <Trash2 className="w-3 h-3 text-red-400" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Main Chat View ────────────────────────────────────────────────
  return (
    <div className="h-full flex flex-col bg-[#252526] select-none">
      {/* Header */}
      <div className="flex items-center justify-between px-3 h-[35px] flex-shrink-0 border-b border-[#3e3e42]">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-[#a78bfa]" />
          <span className="text-[11px] font-semibold tracking-wider text-[#bbbbbb] uppercase">AI Agent</span>
          {isRunning && <Loader2 className="w-3 h-3 text-[#007acc] animate-spin" />}
        </div>
        <div className="flex items-center gap-0.5">
          <button
            onClick={() => setShowHistory(true)}
            className="p-1 rounded hover:bg-[#3e3e42] transition-colors"
            title="Chat History"
          >
            <Clock className="w-3.5 h-3.5 text-[#888]" />
          </button>
          <button
            onClick={newChat}
            className="p-1 rounded hover:bg-[#3e3e42] transition-colors"
            title="New Chat"
          >
            <Plus className="w-3.5 h-3.5 text-[#888]" />
          </button>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`p-1 rounded hover:bg-[#3e3e42] transition-colors ${showSettings ? 'bg-[#3e3e42]' : ''}`}
            title="Settings"
          >
            <Settings className="w-3.5 h-3.5 text-[#888]" />
          </button>
          <button
            onClick={clearMessages}
            className="p-1 rounded hover:bg-[#3e3e42] transition-colors"
            title="Clear chat"
          >
            <Trash2 className="w-3.5 h-3.5 text-[#888]" />
          </button>
        </div>
      </div>

      {/* Settings Panel (collapsible) */}
      {showSettings && (
        <AgentSettingsPanel
          config={config}
          onUpdate={updateConfig}
          onClose={() => setShowSettings(false)}
          backendAvailable={backendAvailable}
        />
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {messages.length === 0 && !showSettings && (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="w-12 h-12 rounded-full bg-[#5b21b6]/20 flex items-center justify-center mb-3">
              <Sparkles className="w-6 h-6 text-[#a78bfa]" />
            </div>
            <h3 className="text-[14px] text-[#ccc] font-medium mb-1">ETHOS AI Agent</h3>
            <p className="text-[12px] text-[#888] mb-4 leading-relaxed max-w-[220px]">
              I can create, edit, and delete files, run commands, search code, and analyze your project.
            </p>
            <div className="space-y-1.5 w-full max-w-[230px]">
              {[
                'Create a new React component',
                'Find all TODO comments',
                'Analyze the project structure',
                'Run the test suite',
              ].map((suggestion, i) => (
                <button
                  key={i}
                  onClick={() => { setInput(suggestion); inputRef.current?.focus(); }}
                  className="w-full text-left text-[11px] text-[#aaa] bg-[#2a2a2a] hover:bg-[#333] px-3 py-2 rounded border border-[#3e3e42] transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
            {chatList.length > 0 && (
              <button
                onClick={() => setShowHistory(true)}
                className="mt-4 text-[11px] text-[#007acc] hover:text-[#1a8fe0] flex items-center gap-1"
              >
                <Clock className="w-3 h-3" />
                View {chatList.length} previous chat{chatList.length !== 1 ? 's' : ''}
              </button>
            )}
          </div>
        )}

        {messages.map(msg => (
          <MessageView key={msg.id} msg={msg} />
        ))}
      </div>

      {/* Input Area */}
      <div className="border-t border-[#3e3e42] p-2">
        {!backendAvailable && (
          <div className="text-[10px] text-orange-400 px-2 py-1 mb-1 flex items-center gap-1">
            <AlertCircle className="w-3 h-3" />
            Backend not running. Start: <code className="bg-[#333] px-1 rounded">python backend/app.py</code>
          </div>
        )}
        <div className="flex items-end gap-1.5">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isRunning ? 'Agent is working...' : 'Ask the agent to do something...'}
            disabled={isRunning}
            rows={1}
            className="flex-1 bg-[#3c3c3c] text-[#ccc] text-[13px] px-3 py-2 rounded-lg border border-[#3e3e42] outline-none focus:border-[#007acc] resize-none min-h-[36px] max-h-[100px] disabled:opacity-50 placeholder:text-[#666]"
            style={{ lineHeight: '1.4' }}
            onInput={(e) => {
              const t = e.currentTarget;
              t.style.height = 'auto';
              t.style.height = Math.min(t.scrollHeight, 100) + 'px';
            }}
          />
          {isRunning ? (
            <button
              onClick={stopAgent}
              className="p-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors flex-shrink-0"
              title="Stop agent"
            >
              <Square className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim() || !backendAvailable}
              className="p-2 rounded-lg bg-[#007acc] text-white hover:bg-[#006bb3] transition-colors disabled:opacity-30 flex-shrink-0"
              title="Send message"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default AIAgentPanel;
