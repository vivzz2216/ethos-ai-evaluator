import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Terminal as XTerminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';
import {
  Terminal as TerminalIcon,
  Plus,
  X,
  ChevronDown,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ExternalLink,
  Download,
  Circle,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────
export interface TerminalConfig {
  autoCreateVenv: boolean;
  autoActivateVenv: boolean;
  autoInstallDeps: 'ask' | 'always' | 'never';
  preferredPython: string;
  showVenvInTree: boolean;
}

export interface VenvStatus {
  status: string;
  message: string;
  errorType?: string;
  suggestion?: string;
  installUrl?: string;
  venvName?: string;
  venvPath?: string;
  pythonExe?: string;
  pythonCmd?: string;
  hasRequirements?: boolean;
}

interface TerminalTab {
  id: string;
  name: string;
  terminalId: string;
}

interface IDETerminalProps {
  sessionId: string | null;
  visible: boolean;
  onToggle: () => void;
  workingDir?: string;
  config: TerminalConfig;
  onVenvStatusChange?: (status: VenvStatus) => void;
}

const WS_URL = 'ws://localhost:8001';

// ── Notification Banner ────────────────────────────────────────────
const VenvBanner: React.FC<{
  status: VenvStatus | null;
  onInstallDeps: () => void;
  onDismiss: () => void;
}> = ({ status, onInstallDeps, onDismiss }) => {
  if (!status) return null;

  // Only show banner for actionable statuses
  const showStatuses = [
    'detected', 'python-found', 'creating', 'created', 'activating',
    'activated', 'installing', 'install-started', 'ask-install', 'ready',
    'error', 'not-python',
  ];
  if (!showStatuses.includes(status.status)) return null;

  // Auto-dismiss non-actionable statuses after display
  const isError = status.status === 'error';
  const isAsk = status.status === 'ask-install';
  const isActive = status.status === 'activated' || status.status === 'ready';
  const isProgress = ['creating', 'activating', 'installing', 'install-started'].includes(status.status);

  let bgColor = 'bg-[#1e3a5f]';
  let borderColor = 'border-[#264f78]';
  let Icon = Circle;

  if (isError) {
    bgColor = 'bg-[#5f1e1e]';
    borderColor = 'border-[#782626]';
    Icon = XCircle;
  } else if (isActive) {
    bgColor = 'bg-[#1e3f1e]';
    borderColor = 'border-[#267826]';
    Icon = CheckCircle2;
  } else if (isProgress) {
    Icon = Loader2;
  } else if (isAsk) {
    bgColor = 'bg-[#3f3a1e]';
    borderColor = 'border-[#786e26]';
    Icon = AlertTriangle;
  }

  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 text-[11px] ${bgColor} border-b ${borderColor} flex-shrink-0`}>
      <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${isProgress ? 'animate-spin' : ''} ${
        isError ? 'text-red-400' : isActive ? 'text-green-400' : isAsk ? 'text-yellow-400' : 'text-blue-400'
      }`} />
      <span className="text-[#cccccc] flex-1">{status.message}</span>

      {/* Error: show suggestion + link */}
      {isError && status.suggestion && (
        <span className="text-[#999] text-[10px]">{status.suggestion}</span>
      )}
      {isError && status.installUrl && (
        <a
          href={status.installUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-[#4fc1ff] hover:text-[#80d4ff] text-[10px]"
        >
          Install <ExternalLink className="w-3 h-3" />
        </a>
      )}

      {/* Ask: install button */}
      {isAsk && (
        <button
          onClick={onInstallDeps}
          className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#0e639c] text-white hover:bg-[#1177bb] text-[10px] transition-colors"
        >
          <Download className="w-3 h-3" /> Install
        </button>
      )}

      {/* Dismiss */}
      {(isActive || isError || isAsk) && (
        <button onClick={onDismiss} className="text-[#888] hover:text-white p-0.5">
          <X className="w-3 h-3" />
        </button>
      )}
    </div>
  );
};

// ── Single Terminal Instance (WebSocket + node-pty) ────────────────
const TerminalInstance: React.FC<{
  terminalId: string;
  workingDir: string;
  config: TerminalConfig;
  active: boolean;
  onVenvStatus: (status: VenvStatus) => void;
}> = ({ terminalId, workingDir, config, active, onVenvStatus }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<XTerminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isConnected = useRef(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'fallback'>('connecting');

  // Fallback refs for HTTP mode
  const inputBuffer = useRef('');
  const historyRef = useRef<string[]>([]);
  const historyIdx = useRef(-1);
  const currentLineRef = useRef('');
  const isExecuting = useRef(false);
  const sessionIdRef = useRef<string | null>(null);
  const PROMPT = '\x1b[38;5;39m$\x1b[0m ';

  // ── Fallback: HTTP-based command execution ─────────────────────
  const fallbackExecute = useCallback(async (cmd: string, term: XTerminal) => {
    if (!cmd.trim()) { term.write('\r\n' + PROMPT); return; }

    historyRef.current.unshift(cmd);
    if (historyRef.current.length > 200) historyRef.current.pop();
    historyIdx.current = -1;

    if (cmd === 'clear') { term.clear(); term.write(PROMPT); return; }
    if (cmd === 'help') {
      term.write('\r\n\x1b[1;36mETHOS Terminal\x1b[0m — HTTP fallback mode\r\n');
      term.write('\r\n  \x1b[33mclear\x1b[0m          Clear terminal');
      term.write('\r\n  \x1b[33mhelp\x1b[0m           Show this help');
      term.write('\r\n  \x1b[33m<command>\x1b[0m      Execute via backend API\r\n');
      term.write(PROMPT);
      return;
    }

    // Try to find a session ID from the backend
    if (!sessionIdRef.current) {
      try {
        const res = await fetch('http://localhost:8000/api/debug/sessions');
        const data = await res.json();
        if (data.active_sessions?.length > 0) {
          sessionIdRef.current = data.active_sessions[0];
        }
      } catch { /* ignore */ }
    }

    if (!sessionIdRef.current) {
      term.write('\r\n\x1b[31mNo active session.\x1b[0m Upload files to create one.\r\n' + PROMPT);
      return;
    }

    isExecuting.current = true;
    term.write('\r\n');

    try {
      const res = await fetch(`http://localhost:8000/api/session/${sessionIdRef.current}/execute-command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `command=${encodeURIComponent(cmd)}`,
      });
      const data = await res.json();
      if (res.ok) {
        if (data.stdout) term.write(data.stdout.replace(/\r?\n/g, '\r\n'));
        if (data.stderr) term.write('\x1b[31m' + data.stderr.replace(/\r?\n/g, '\r\n') + '\x1b[0m');
        if (!data.stdout && !data.stderr && data.success) term.write('\x1b[32mOK\x1b[0m');
        if (!data.success && !data.stdout && !data.stderr) term.write(`\x1b[31mFailed (exit ${data.returncode})\x1b[0m`);
      } else {
        term.write(`\x1b[31mError: ${data.detail || res.statusText}\x1b[0m`);
      }
    } catch (err) {
      term.write(`\x1b[31mFailed: ${err}\x1b[0m`);
    }

    isExecuting.current = false;
    term.write('\r\n' + PROMPT);
  }, []);

  // ── Initialize xterm ───────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    const term = new XTerminal({
      theme: {
        background: '#1e1e1e',
        foreground: '#cccccc',
        cursor: '#aeafad',
        cursorAccent: '#1e1e1e',
        selectionBackground: '#264f78',
        selectionForeground: '#ffffff',
        black: '#000000',
        red: '#cd3131',
        green: '#0dbc79',
        yellow: '#e5e510',
        blue: '#2472c8',
        magenta: '#bc3fbc',
        cyan: '#11a8cd',
        white: '#e5e5e5',
        brightBlack: '#666666',
        brightRed: '#f14c4c',
        brightGreen: '#23d18b',
        brightYellow: '#f5f543',
        brightBlue: '#3b8eea',
        brightMagenta: '#d670d6',
        brightCyan: '#29b8db',
        brightWhite: '#e5e5e5',
      },
      fontFamily: '"Cascadia Code", "Fira Code", Menlo, Monaco, "Courier New", monospace',
      fontSize: 13,
      lineHeight: 1.4,
      cursorBlink: true,
      cursorStyle: 'bar',
      scrollback: 5000,
      allowProposedApi: true,
    });

    const fit = new FitAddon();
    const links = new WebLinksAddon();
    term.loadAddon(fit);
    term.loadAddon(links);
    term.open(containerRef.current);

    requestAnimationFrame(() => { try { fit.fit(); } catch {} });

    termRef.current = term;
    fitRef.current = fit;

    // ── Try WebSocket connection to node-pty server ──────────────
    const connectWs = () => {
      setConnectionStatus('connecting');
      const safeConfig = config || { autoCreateVenv: true, autoActivateVenv: true, autoInstallDeps: 'ask', preferredPython: 'python', showVenvInTree: true };
      const configStr = encodeURIComponent(JSON.stringify(safeConfig));
      const cwdParam = workingDir ? encodeURIComponent(workingDir) : '';
      const wsUrl = `${WS_URL}?terminalId=${terminalId}&cwd=${cwdParam}&config=${configStr}`;

      let ws: WebSocket;
      try {
        ws = new WebSocket(wsUrl);
      } catch {
        enterFallbackMode(term);
        return;
      }

      // Timeout: if not connected within 3s, fall back to HTTP mode
      const connectTimeout = setTimeout(() => {
        if (!isConnected.current) {
          try { ws.close(); } catch {}
          enterFallbackMode(term);
        }
      }, 3000);

      ws.onopen = () => {
        clearTimeout(connectTimeout);
        isConnected.current = true;
        setConnectionStatus('connected');
        wsRef.current = ws;

        // Send initial resize
        const dims = fit.proposeDimensions();
        if (dims) {
          ws.send(JSON.stringify({ type: 'resize', cols: dims.cols, rows: dims.rows }));
        }
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          switch (msg.type) {
            case 'output':
              term.write(msg.data);
              break;
            case 'venv-status':
              onVenvStatus(msg as VenvStatus);
              break;
            case 'error':
              onVenvStatus({
                status: 'error',
                message: msg.message,
                errorType: msg.errorType,
                suggestion: msg.suggestion,
                installUrl: msg.installUrl,
              });
              break;
            case 'exit':
              term.write(`\r\n\x1b[90m[Process exited with code ${msg.exitCode}]\x1b[0m\r\n`);
              break;
            case 'state':
            case 'config-updated':
              // State updates handled by parent
              break;
            default:
              break;
          }
        } catch {
          // Raw data
          term.write(event.data);
        }
      };

      ws.onclose = () => {
        clearTimeout(connectTimeout);
        isConnected.current = false;
        wsRef.current = null;
        // Fall back if not already in fallback mode
        if (connectionStatus !== 'fallback') {
          enterFallbackMode(term);
        }
      };

      ws.onerror = () => {
        // Will trigger onclose
      };
    };

    const enterFallbackMode = (t: XTerminal) => {
      setConnectionStatus('fallback');
      isConnected.current = false;
      t.write('\x1b[1;36mETHOS Terminal\x1b[0m \x1b[90m(HTTP mode)\x1b[0m\r\n');
      t.write('\x1b[90mNode.js terminal server not running. Using HTTP fallback.\x1b[0m\r\n');
      t.write('\x1b[90mStart server: node server/terminal-server.js\x1b[0m\r\n');
      t.write(PROMPT);

      // Set up fallback input handling
      t.onData(data => {
        if (isExecuting.current) return;
        const code = data.charCodeAt(0);

        if (data === '\r') {
          const cmd = inputBuffer.current;
          inputBuffer.current = '';
          currentLineRef.current = '';
          fallbackExecute(cmd, t);
        } else if (code === 127 || data === '\b') {
          if (inputBuffer.current.length > 0) {
            inputBuffer.current = inputBuffer.current.slice(0, -1);
            t.write('\b \b');
          }
        } else if (data === '\x1b[A') {
          if (historyRef.current.length > 0 && historyIdx.current < historyRef.current.length - 1) {
            if (historyIdx.current === -1) currentLineRef.current = inputBuffer.current;
            historyIdx.current++;
            const entry = historyRef.current[historyIdx.current];
            t.write('\r' + PROMPT + ' '.repeat(inputBuffer.current.length) + '\r' + PROMPT + entry);
            inputBuffer.current = entry;
          }
        } else if (data === '\x1b[B') {
          if (historyIdx.current > -1) {
            historyIdx.current--;
            const entry = historyIdx.current >= 0 ? historyRef.current[historyIdx.current] : currentLineRef.current;
            t.write('\r' + PROMPT + ' '.repeat(inputBuffer.current.length) + '\r' + PROMPT + entry);
            inputBuffer.current = entry;
          }
        } else if (data === '\x03') {
          inputBuffer.current = '';
          t.write('^C\r\n' + PROMPT);
        } else if (data === '\x0c') {
          t.clear();
          t.write(PROMPT + inputBuffer.current);
        } else if (code >= 32) {
          inputBuffer.current += data;
          t.write(data);
        }
      });
    };

    // Try WebSocket first
    connectWs();

    // If WebSocket mode: pipe xterm input to pty via ws
    term.onData(data => {
      if (isConnected.current && wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'input', data }));
      }
    });

    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      term.dispose();
      termRef.current = null;
      fitRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Resize handling ────────────────────────────────────────────
  useEffect(() => {
    if (!active || !fitRef.current) return;
    const timer = setTimeout(() => {
      try {
        fitRef.current?.fit();
        if (wsRef.current?.readyState === WebSocket.OPEN && fitRef.current) {
          const dims = fitRef.current.proposeDimensions();
          if (dims) wsRef.current.send(JSON.stringify({ type: 'resize', cols: dims.cols, rows: dims.rows }));
        }
      } catch {}
    }, 50);
    return () => clearTimeout(timer);
  }, [active]);

  useEffect(() => {
    if (!containerRef.current || !fitRef.current) return;
    const ro = new ResizeObserver(() => {
      try {
        fitRef.current?.fit();
        if (wsRef.current?.readyState === WebSocket.OPEN && fitRef.current) {
          const dims = fitRef.current.proposeDimensions();
          if (dims) wsRef.current.send(JSON.stringify({ type: 'resize', cols: dims.cols, rows: dims.rows }));
        }
      } catch {}
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="w-full h-full relative">
      <div
        ref={containerRef}
        className="w-full h-full"
        style={{ display: active ? 'block' : 'none' }}
      />
      {/* Connection indicator */}
      {active && (
        <div className="absolute top-1 right-2 flex items-center gap-1 text-[9px] opacity-60">
          <div className={`w-1.5 h-1.5 rounded-full ${
            connectionStatus === 'connected' ? 'bg-green-400' :
            connectionStatus === 'connecting' ? 'bg-yellow-400 animate-pulse' :
            connectionStatus === 'fallback' ? 'bg-orange-400' :
            'bg-red-400'
          }`} />
          <span className="text-[#888]">
            {connectionStatus === 'connected' ? 'pty' :
             connectionStatus === 'fallback' ? 'http' :
             connectionStatus === 'connecting' ? '...' : 'off'}
          </span>
        </div>
      )}
    </div>
  );
};

// ── Main Terminal Component ────────────────────────────────────────
const IDETerminal: React.FC<IDETerminalProps> = ({
  sessionId,
  visible,
  onToggle,
  workingDir,
  config,
  onVenvStatusChange,
}) => {
  const [tabs, setTabs] = useState<TerminalTab[]>([
    { id: '1', name: 'Terminal', terminalId: `term_1_${Date.now()}` },
  ]);
  const [activeTab, setActiveTab] = useState('1');
  const [venvStatus, setVenvStatus] = useState<VenvStatus | null>(null);
  const tabCounter = useRef(1);

  const cwd = workingDir || (typeof window !== 'undefined' ? '' : '');

  const handleVenvStatus = useCallback((status: VenvStatus) => {
    setVenvStatus(status);
    onVenvStatusChange?.(status);
  }, [onVenvStatusChange]);

  const handleInstallDeps = useCallback(() => {
    // Send install command to the terminal server
    const activeTerminal = tabs.find(t => t.id === activeTab);
    if (!activeTerminal) return;
    fetch('http://localhost:8001/install-requirements', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ terminalId: activeTerminal.terminalId }),
    }).catch(() => {
      // Fallback: just dismiss
      setVenvStatus(null);
    });
    setVenvStatus(prev => prev ? { ...prev, status: 'installing', message: 'Installing dependencies...' } : null);
  }, [tabs, activeTab]);

  const addTab = useCallback(() => {
    tabCounter.current++;
    const id = String(tabCounter.current);
    setTabs(prev => [...prev, {
      id,
      name: `Terminal ${tabCounter.current}`,
      terminalId: `term_${id}_${Date.now()}`,
    }]);
    setActiveTab(id);
  }, []);

  const closeTab = useCallback((id: string) => {
    setTabs(prev => {
      const next = prev.filter(t => t.id !== id);
      if (next.length === 0) {
        onToggle();
        return prev;
      }
      if (activeTab === id) setActiveTab(next[next.length - 1].id);
      return next;
    });
  }, [activeTab, onToggle]);

  if (!visible) return null;

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] border-t border-[#3e3e42]">
      {/* Venv Status Banner */}
      <VenvBanner
        status={venvStatus}
        onInstallDeps={handleInstallDeps}
        onDismiss={() => setVenvStatus(null)}
      />

      {/* Terminal Tab Bar */}
      <div className="flex items-center h-[35px] bg-[#252526] border-b border-[#3e3e42] flex-shrink-0">
        <div className="flex items-center flex-1 overflow-x-auto">
          {tabs.map(tab => (
            <div
              key={tab.id}
              className={`flex items-center gap-1.5 px-3 h-full text-[12px] cursor-pointer border-r border-[#3e3e42] group transition-colors ${
                activeTab === tab.id
                  ? 'bg-[#1e1e1e] text-white'
                  : 'text-[#888] hover:text-[#ccc] hover:bg-[#2a2a2a]'
              }`}
              onClick={() => setActiveTab(tab.id)}
            >
              <TerminalIcon className="w-3.5 h-3.5 flex-shrink-0" />
              <span>{tab.name}</span>
              <button
                onClick={e => { e.stopPropagation(); closeTab(tab.id); }}
                className="opacity-0 group-hover:opacity-100 hover:bg-[#3e3e42] rounded p-0.5 transition-opacity"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}

          <button
            onClick={addTab}
            className="flex items-center justify-center w-7 h-7 text-[#888] hover:text-white hover:bg-[#3e3e42] rounded mx-1 transition-colors"
            title="New Terminal"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="flex items-center gap-0.5 px-2">
          <button
            onClick={onToggle}
            className="p-1 rounded hover:bg-[#3e3e42] text-[#888] hover:text-white transition-colors"
            title="Hide Terminal"
          >
            <ChevronDown className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Terminal Instances */}
      <div className="flex-1 overflow-hidden">
        {tabs.map(tab => (
          <TerminalInstance
            key={tab.terminalId}
            terminalId={tab.terminalId}
            workingDir={cwd}
            config={config}
            active={activeTab === tab.id}
            onVenvStatus={handleVenvStatus}
          />
        ))}
      </div>
    </div>
  );
};

export default IDETerminal;
export type { TerminalConfig as IDETerminalConfig };
