import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Files,
  Search,
  GitBranch,
  Terminal,
  Settings,
  Brain,
  PanelLeft,
  PanelRight,
  PanelBottom,
  X,
  Circle,
  AlertCircle,
  CheckCircle,
  Download,
  Play,
  Save,
  ArrowLeft,
  AlertTriangle,
  Globe,
  Bot,
  FlaskConical,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import MonacoEditor from '@/components/MonacoEditor';
import IDEFileExplorer from '@/components/IDEFileExplorer';
import type { FileNode } from '@/components/IDEFileExplorer';
import IDEModelSidebar, { getDefaultModelId } from '@/components/IDEModelSidebar';
import IDETerminal from '@/components/IDETerminal';
import type { TerminalConfig, VenvStatus } from '@/components/IDETerminal';
import IDESettings from '@/components/IDESettings';
import AIAgentPanel from '@/components/AIAgentPanel';
import { ModelUploadWizard } from '@/components/ModelUploadWizard';
import { ModelDashboard } from '@/components/ModelDashboard';
import { EthosTestResults } from '@/components/EthosTestResults';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useEthosTest } from '@/hooks/use-ethos-test';
import { useToast } from '@/hooks/use-toast';
import * as fsApi from '@/lib/fs-api';

// ── Re-export types for backward compat ────────────────────────────
export interface TestResult {
  prompt_id: string;
  prompt: string;
  expected_label: string;
  category: string;
  evaluation: {
    score: number;
    aligned?: boolean;
    correct?: boolean;
    category: string;
    metrics: {
      alignment?: number;
      toxicity?: number;
      reasoning?: number;
      correctness?: number;
      coherence?: number;
    };
    explanation: string;
  };
}

export interface TestSummary {
  ethical_alignment_score?: number;
  logical_correctness_score?: number;
  truthfulness_score?: number;
  total_evaluated: number;
  aligned_responses?: number;
  correct_responses?: number;
  truthful_responses?: number;
  metrics: {
    alignment?: number;
    toxicity?: number;
    reasoning?: number;
    correctness?: number;
    coherence?: number;
    factual_accuracy?: number;
    honesty?: number;
    transparency?: number;
  };
  category_breakdown: {
    [key: string]: {
      count: number;
      score: number;
    };
  };
}

export interface TestResponse {
  results: TestResult[];
  summary: TestSummary;
}

// ── Language detection helper ──────────────────────────────────────
function detectLanguage(filename: string): string {
  const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase();
  const map: Record<string, string> = {
    '.py': 'python', '.js': 'javascript', '.jsx': 'javascript',
    '.ts': 'typescript', '.tsx': 'typescript', '.html': 'html',
    '.css': 'css', '.scss': 'scss', '.json': 'json',
    '.md': 'markdown', '.yml': 'yaml', '.yaml': 'yaml',
    '.xml': 'xml', '.sql': 'sql', '.sh': 'shell',
    '.bash': 'shell', '.rs': 'rust', '.go': 'go',
    '.java': 'java', '.cpp': 'cpp', '.c': 'c',
    '.txt': 'plaintext',
  };
  return map[ext] || 'plaintext';
}

// ── Tab interface ──────────────────────────────────────────────────
interface EditorTab {
  id: string;
  name: string;
  path: string;
  content: string;
  language: string;
  isDirty: boolean;
  savedContent: string;
}

// ── Activity Bar Item ──────────────────────────────────────────────
interface ActivityItem {
  id: string;
  icon: React.ElementType;
  label: string;
  shortcut?: string;
}

const ACTIVITY_ITEMS: ActivityItem[] = [
  { id: 'explorer', icon: Files, label: 'Explorer', shortcut: 'Ctrl+B' },
  { id: 'search', icon: Search, label: 'Search', shortcut: 'Ctrl+P' },
  { id: 'agent', icon: Bot, label: 'AI Agent', shortcut: 'Ctrl+Shift+A' },
  { id: 'source-control', icon: GitBranch, label: 'Source Control' },
  { id: 'models', icon: Brain, label: 'AI Models', shortcut: 'Ctrl+Shift+M' },
  { id: 'model-testing', icon: FlaskConical, label: 'Model Testing' },
  { id: 'settings', icon: Settings, label: 'Settings' },
];

// ════════════════════════════════════════════════════════════════════
// ── EDITOR COMPONENT ───────────────────────────────────────────────
// ════════════════════════════════════════════════════════════════════
const Editor: React.FC = () => {
  // ── Layout state ─────────────────────────────────────────────────
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(false);
  const [terminalVisible, setTerminalVisible] = useState(true);
  const [terminalHeight, setTerminalHeight] = useState(250);
  const [activeActivity, setActiveActivity] = useState('explorer');

  // ── File state ───────────────────────────────────────────────────
  const [files, setFiles] = useState<FileNode[]>([]);
  const [selectedFile, setSelectedFile] = useState<FileNode | null>(null);
  const [tabs, setTabs] = useState<EditorTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);

  // ── Editor state ─────────────────────────────────────────────────
  const [code, setCode] = useState('# Welcome to ETHOS Editor\n# Upload your Python files or start coding here\n\nprint("Hello, ETHOS!")\n');
  const [language, setLanguage] = useState('python');
  const [cursorLine, setCursorLine] = useState(1);
  const [cursorCol, setCursorCol] = useState(1);

  // ── Session state ────────────────────────────────────────────────
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [selectedModelId, setSelectedModelId] = useState(getDefaultModelId());
  const [workspacePath, setWorkspacePath] = useState<string | null>(null);
  const [fsAvailable, setFsAvailable] = useState(false);

  // ── Load workspace tree from real filesystem ──────────────────────
  const loadWorkspaceTree = useCallback(async () => {
    const tree = await fsApi.getTree();
    if (tree.length > 0) {
      setFiles(tree as FileNode[]);
    }
  }, []);

  // Check filesystem server on mount
  useEffect(() => {
    fsApi.fsHealthCheck().then(ok => {
      setFsAvailable(ok);
      if (ok) {
        fsApi.getWorkspace().then(ws => {
          if (ws) {
            setWorkspacePath(ws);
            loadWorkspaceTree();
          }
        });
      }
    });
  }, [loadWorkspaceTree]);

  // ── Terminal config & venv state ──────────────────────────────────
  const [terminalConfig, setTerminalConfig] = useState<TerminalConfig>({
    autoCreateVenv: true,
    autoActivateVenv: true,
    autoInstallDeps: 'ask',
    preferredPython: navigator.platform.startsWith('Win') ? 'python' : 'python3',
    showVenvInTree: true,
  });
  const [venvStatus, setVenvStatus] = useState<VenvStatus | null>(null);

  // ── ETHOS testing state ──────────────────────────────────────────
  const [showEthosDialog, setShowEthosDialog] = useState(false);
  const [currentPrompts, setCurrentPrompts] = useState<any[]>([]);
  const [currentTestType, setCurrentTestType] = useState<'ethical' | 'logical' | 'truthfulness'>('ethical');
  const { toast } = useToast();
  const {
    isLoading: isTestLoading,
    ethicalResults,
    logicalResults,
    truthfulnessResults,
    runEthicalTestDirect,
    runTruthfulnessTestDirect,
    runAutomatedTest,
    getPrompts,
  } = useEthosTest();

  // ── Terminal resize drag ─────────────────────────────────────────
  const isDragging = useRef(false);
  const startY = useRef(0);
  const startH = useRef(0);

  const onDragStart = useCallback((e: React.MouseEvent) => {
    isDragging.current = true;
    startY.current = e.clientY;
    startH.current = terminalHeight;
    document.body.style.cursor = 'ns-resize';
    document.body.style.userSelect = 'none';
  }, [terminalHeight]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const delta = startY.current - e.clientY;
      setTerminalHeight(Math.max(100, Math.min(600, startH.current + delta)));
    };
    const onUp = () => {
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, []);

  // ── Keyboard shortcuts ───────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const ctrl = e.ctrlKey || e.metaKey;

      // Ctrl+B — toggle file explorer
      if (ctrl && e.key === 'b') {
        e.preventDefault();
        setLeftSidebarOpen(p => !p);
      }
      // Ctrl+` — toggle terminal
      if (ctrl && e.key === '`') {
        e.preventDefault();
        setTerminalVisible(p => !p);
      }
      // Ctrl+Shift+M — toggle model sidebar
      if (ctrl && e.shiftKey && e.key === 'M') {
        e.preventDefault();
        setRightSidebarOpen(p => !p);
      }
      // Ctrl+Shift+A — toggle AI Agent panel
      if (ctrl && e.shiftKey && e.key === 'A') {
        e.preventDefault();
        if (activeActivity === 'agent' && rightSidebarOpen) {
          setRightSidebarOpen(false);
        } else {
          setActiveActivity('agent');
          setRightSidebarOpen(true);
          setLeftSidebarOpen(false);
        }
      }
      // Ctrl+S — save
      if (ctrl && e.key === 's') {
        e.preventDefault();
        saveCurrentFile();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [tabs, activeTabId, code]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Session creation on file upload ──────────────────────────────
  const uploadFilesToBackend = useCallback(async (fileNodes: FileNode[]) => {
    let sid = sessionId;
    let projectDir = '';
    if (!sid) {
      try {
        const res = await fetch('http://localhost:8000/api/session/create', { method: 'POST' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        sid = data.session_id;
        projectDir = data.project_dir || '';
        setSessionId(sid);
      } catch (err) {
        console.warn('Backend not available — running in local-only mode. Start backend: python backend/app.py');
        toast({
          title: 'Backend not running',
          description: 'Files loaded locally. Start the Python backend (python backend/app.py) for terminal execution and ETHOS tests.',
        });
        return;
      }
    }

    try {
      const formData = new FormData();
      const addFile = (node: FileNode, prefix: string) => {
        const relPath = prefix ? `${prefix}/${node.name}` : node.name;
        if (node.type === 'file') {
          if (node.rawFile) {
            // Binary model weights — send raw File object (no text conversion)
            formData.append('files', new File([node.rawFile], relPath, { type: 'application/octet-stream' }));
          } else if (node.content) {
            // Text files — safe to create Blob from string content
            const blob = new Blob([node.content], { type: 'text/plain' });
            formData.append('files', new File([blob], relPath, { type: 'text/plain' }));
          }
        }
        node.children?.forEach(c => addFile(c, relPath));
      };
      fileNodes.forEach(n => addFile(n, ''));
      if (formData.getAll('files').length === 0) return;

      const uploadRes = await fetch(`http://localhost:8000/api/session/${sid}/upload`, { method: 'POST', body: formData });
      if (uploadRes.ok) {
        const uploadData = await uploadRes.json();
        // Use the project_dir from session create or upload response
        const dir = projectDir || uploadData.project_dir || '';
        if (dir) {
          const wsRes = await fsApi.setWorkspace(dir);
          if (wsRes) {
            setWorkspacePath(wsRes);
            setFsAvailable(true);
            // Reload tree from real filesystem after upload
            setTimeout(() => loadWorkspaceTree(), 500);
          }
        }
      }
    } catch (err) {
      console.warn('Failed to upload files to backend:', err);
    }
  }, [sessionId, toast, loadWorkspaceTree]);

  // ── File operations ──────────────────────────────────────────────
  const handleFilesUploaded = useCallback((newFiles: FileNode[]) => {
    setFiles(newFiles);
    if (newFiles.length > 0) uploadFilesToBackend(newFiles);

    // Auto-open first file
    const findFirst = (nodes: FileNode[]): FileNode | null => {
      for (const n of nodes) {
        if (n.type === 'file') return n;
        if (n.children) { const f = findFirst(n.children); if (f) return f; }
      }
      return null;
    };
    const first = findFirst(newFiles);
    if (first) openFileInTab(first);
  }, [uploadFilesToBackend]); // eslint-disable-line react-hooks/exhaustive-deps

  // Binary extensions that must never be opened in Monaco
  const BINARY_EXTS = new Set([
    '.safetensors', '.bin', '.pt', '.pth', '.onnx', '.tflite',
    '.h5', '.hdf5', '.pkl', '.pickle', '.msgpack', '.pb',
    '.gguf', '.ggml', '.ckpt', '.mar', '.params',
    '.model', '.spiece', '.sentencepiece',
  ]);

  const openFileInTab = useCallback(async (file: FileNode) => {
    if (file.type === 'folder') return;
    setSelectedFile(file);

    // Block binary model files from Monaco — they crash the editor worker
    const ext = file.name.includes('.') ? '.' + file.name.split('.').pop()!.toLowerCase() : '';
    if (BINARY_EXTS.has(ext)) {
      const sizeMB = file.rawFile ? (file.rawFile.size / (1024 * 1024)).toFixed(1) : '?';
      const placeholder = `// Binary model weight file: ${file.name}\n// Size: ${sizeMB} MB\n// This file cannot be viewed in the editor.\n// It will be uploaded to the backend for model testing.`;
      setCode(placeholder);
      setLanguage('plaintext');
      setTabs(prev => {
        const existing = prev.find(t => t.id === file.id);
        if (existing) {
          setActiveTabId(file.id);
          return prev.map(t => t.id === file.id ? { ...t, content: placeholder, savedContent: placeholder, isDirty: false } : t);
        }
        setActiveTabId(file.id);
        return [...prev, { id: file.id, name: file.name, path: file.path, content: placeholder, language: 'plaintext', isDirty: false, savedContent: placeholder }];
      });
      return;
    }

    // Try to read from real filesystem first
    let content = file.content || '';
    if (fsAvailable && file.path) {
      const result = await fsApi.readFile(file.path);
      if (result) content = result.content;
    }

    const lang = detectLanguage(file.name);
    setCode(content);
    setLanguage(lang);

    setTabs(prev => {
      const existing = prev.find(t => t.id === file.id);
      if (existing) {
        // Refresh content from disk
        setActiveTabId(file.id);
        return prev.map(t => t.id === file.id ? { ...t, content, savedContent: content, isDirty: false } : t);
      }
      const newTab: EditorTab = {
        id: file.id,
        name: file.name,
        path: file.path,
        content,
        language: lang,
        isDirty: false,
        savedContent: content,
      };
      setActiveTabId(file.id);
      return [...prev, newTab];
    });
  }, [fsAvailable]);

  const handleTabSelect = useCallback((tabId: string) => {
    setActiveTabId(tabId);
    setTabs(prev => {
      const tab = prev.find(t => t.id === tabId);
      if (tab) {
        setCode(tab.content);
        setLanguage(tab.language);
      }
      return prev;
    });
  }, []);

  const handleTabClose = useCallback((tabId: string) => {
    setTabs(prev => {
      const idx = prev.findIndex(t => t.id === tabId);
      const next = prev.filter(t => t.id !== tabId);
      if (activeTabId === tabId) {
        if (next.length > 0) {
          const newActive = next[Math.min(idx, next.length - 1)];
          setActiveTabId(newActive.id);
          setCode(newActive.content);
          setLanguage(newActive.language);
        } else {
          setActiveTabId(null);
          setCode('# Welcome to ETHOS Editor\n# Upload your Python files or start coding here\n\nprint("Hello, ETHOS!")\n');
          setLanguage('python');
          setSelectedFile(null);
        }
      }
      return next;
    });
  }, [activeTabId]);

  // Track code changes → mark tab dirty
  const handleCodeChange = useCallback((newCode: string) => {
    setCode(newCode);
    setTabs(prev =>
      prev.map(t =>
        t.id === activeTabId ? { ...t, content: newCode, isDirty: newCode !== t.savedContent } : t
      )
    );
  }, [activeTabId]);

  const saveCurrentFile = useCallback(async () => {
    setTabs(prev =>
      prev.map(t => (t.id === activeTabId ? { ...t, savedContent: t.content, isDirty: false } : t))
    );
    // Update file tree content
    if (selectedFile) {
      const update = (nodes: FileNode[]): FileNode[] =>
        nodes.map(n => {
          if (n.id === selectedFile.id) return { ...n, content: code };
          if (n.children) return { ...n, children: update(n.children) };
          return n;
        });
      setFiles(prev => update(prev));

      // Write to real filesystem
      if (fsAvailable && selectedFile.path) {
        const ok = await fsApi.writeFile(selectedFile.path, code);
        if (!ok) {
          toast({ title: 'Save failed', description: 'Could not write file to disk', variant: 'destructive' });
          return;
        }
      }
    }
    toast({ title: 'Saved', description: selectedFile?.name || 'File saved' });
  }, [activeTabId, selectedFile, code, toast, fsAvailable]);

  // ── File tree operations ─────────────────────────────────────────
  const handleFileRename = useCallback(async (fileId: string, newName: string) => {
    // Find the node to get old path
    let oldPath = '';
    const findPath = (nodes: FileNode[]): void => {
      for (const n of nodes) {
        if (n.id === fileId) { oldPath = n.path; return; }
        if (n.children) findPath(n.children);
      }
    };
    findPath(files);

    const newPath = oldPath ? oldPath.replace(/[^/]+$/, newName) : newName;

    // Rename on real filesystem
    if (fsAvailable && oldPath) {
      const ok = await fsApi.renameFile(oldPath, newPath);
      if (!ok) {
        toast({ title: 'Rename failed', description: 'Could not rename on disk', variant: 'destructive' });
        return;
      }
    }

    const rename = (nodes: FileNode[]): FileNode[] =>
      nodes.map(n => {
        if (n.id === fileId) return { ...n, name: newName, path: newPath };
        if (n.children) return { ...n, children: rename(n.children) };
        return n;
      });
    setFiles(prev => rename(prev));
    setTabs(prev => prev.map(t => (t.id === fileId ? { ...t, name: newName, path: newPath } : t)));
  }, [files, fsAvailable, toast]);

  const handleFileDelete = useCallback(async (fileId: string) => {
    // Find the node to get path
    let filePath = '';
    const findPath = (nodes: FileNode[]): void => {
      for (const n of nodes) {
        if (n.id === fileId) { filePath = n.path; return; }
        if (n.children) findPath(n.children);
      }
    };
    findPath(files);

    // Delete from real filesystem
    if (fsAvailable && filePath) {
      const ok = await fsApi.deleteFile(filePath);
      if (!ok) {
        toast({ title: 'Delete failed', description: 'Could not delete from disk', variant: 'destructive' });
        return;
      }
    }

    const remove = (nodes: FileNode[]): FileNode[] =>
      nodes.filter(n => {
        if (n.id === fileId) return false;
        if (n.children) n.children = remove(n.children);
        return true;
      });
    setFiles(prev => remove(prev));
    handleTabClose(fileId);
  }, [handleTabClose, files, fsAvailable, toast]);

  const handleFileCreate = useCallback(async (parentPath: string, name: string, type: 'file' | 'folder') => {
    const filePath = parentPath ? `${parentPath}/${name}` : name;

    // Create on real filesystem
    if (fsAvailable) {
      let ok: boolean;
      if (type === 'folder') {
        ok = await fsApi.mkdir(filePath);
      } else {
        ok = await fsApi.writeFile(filePath, '');
      }
      if (!ok) {
        toast({ title: 'Create failed', description: `Could not create ${type} on disk`, variant: 'destructive' });
        return;
      }
    }

    const newNode: FileNode = {
      id: `new_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      name,
      type,
      path: filePath,
      content: type === 'file' ? '' : undefined,
      children: type === 'folder' ? [] : undefined,
    };

    if (!parentPath) {
      setFiles(prev => [...prev, newNode]);
    } else {
      const insert = (nodes: FileNode[]): FileNode[] =>
        nodes.map(n => {
          if (n.path === parentPath && n.type === 'folder') {
            return { ...n, children: [...(n.children || []), newNode] };
          }
          if (n.children) return { ...n, children: insert(n.children) };
          return n;
        });
      setFiles(prev => insert(prev));
    }

    if (type === 'file') openFileInTab(newNode);
  }, [openFileInTab, fsAvailable, toast]);

  // ── Activity bar click ───────────────────────────────────────────
  const handleActivityClick = useCallback((id: string) => {
    if (id === 'explorer') {
      if (activeActivity === 'explorer' && leftSidebarOpen) setLeftSidebarOpen(false);
      else { setActiveActivity('explorer'); setLeftSidebarOpen(true); setRightSidebarOpen(false); }
    } else if (id === 'models') {
      if (activeActivity === 'models' && rightSidebarOpen) setRightSidebarOpen(false);
      else { setActiveActivity('models'); setRightSidebarOpen(true); setLeftSidebarOpen(false); }
    } else if (id === 'agent') {
      if (activeActivity === 'agent' && rightSidebarOpen) setRightSidebarOpen(false);
      else { setActiveActivity('agent'); setRightSidebarOpen(true); setLeftSidebarOpen(false); }
    } else if (id === 'model-testing') {
      if (activeActivity === 'model-testing' && rightSidebarOpen) setRightSidebarOpen(false);
      else { setActiveActivity('model-testing'); setRightSidebarOpen(true); setLeftSidebarOpen(false); }
    } else {
      setActiveActivity(id);
      setLeftSidebarOpen(true);
      setRightSidebarOpen(false);
    }
  }, [activeActivity, leftSidebarOpen, rightSidebarOpen]);

  // ── ETHOS test handler ───────────────────────────────────────────
  const handleStartEthosTest = useCallback(async (type: 'ethical' | 'logical' | 'truthfulness') => {
    setCurrentTestType(type);
    try {
      if (type === 'truthfulness') {
        toast({ title: 'Truthfulness Test', description: 'Running truthfulness evaluation...' });
        await runTruthfulnessTestDirect(20);
      } else if (selectedFile?.content?.trim()) {
        toast({ title: 'Code Analysis', description: 'Analyzing code...' });
        await runAutomatedTest(selectedFile.content);
      } else {
        toast({ title: 'Model Test', description: `Running ${type} evaluation...` });
        await runEthicalTestDirect(20);
      }
      const prompts = await getPrompts(type);
      setCurrentPrompts(prompts);
      setShowEthosDialog(true);
    } catch (err) {
      toast({ title: 'Test Failed', description: err instanceof Error ? err.message : 'Unknown error', variant: 'destructive' });
    }
  }, [selectedFile, toast, runTruthfulnessTestDirect, runAutomatedTest, runEthicalTestDirect, getPrompts]);

  // ── PDF download ─────────────────────────────────────────────────
  const resultsRef = useRef<HTMLDivElement>(null);
  const handleDownloadPdf = useCallback(() => {
    try {
      const content = resultsRef.current?.innerHTML || '';
      const win = window.open('', '_blank');
      if (!win) return;
      win.document.write(`<html><head><title>ETHOS Test Results</title><style>body{font-family:system-ui;padding:24px}h1,h2,h3{margin:0 0 8px}.card{border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-bottom:12px}</style></head><body>${content}</body></html>`);
      win.document.close();
      win.focus();
      setTimeout(() => { win.print(); win.close(); }, 250);
    } catch { toast({ title: 'Download failed', variant: 'destructive' }); }
  }, [toast]);

  // ── Active tab data ──────────────────────────────────────────────
  const activeTab = tabs.find(t => t.id === activeTabId);

  // ════════════════════════════════════════════════════════════════════
  // ── RENDER ─────────────────────────────────────────────────────────
  // ════════════════════════════════════════════════════════════════════
  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: '#1e1e1e' }}>

      {/* ── Title Bar ─────────────────────────────────────────────── */}
      <div className="h-[30px] flex items-center justify-between px-3 flex-shrink-0 select-none"
           style={{ background: '#323233', borderBottom: '1px solid #3e3e42' }}>
        <div className="flex items-center gap-3">
          <button onClick={() => window.history.back()}
                  className="text-[11px] text-[#cccccc] hover:text-white flex items-center gap-1 hover:bg-[#505050] px-2 py-0.5 rounded transition-colors">
            <ArrowLeft className="w-3 h-3" /> Back
          </button>
          <span className="text-[11px] text-[#999]">ETHOS AI Evaluator</span>
        </div>
        <div className="flex items-center gap-1">
          {/* ETHOS Test buttons */}
          <button onClick={() => handleStartEthosTest('ethical')}
                  className="text-[11px] text-[#cccccc] hover:text-white flex items-center gap-1 hover:bg-[#505050] px-2 py-0.5 rounded transition-colors">
            <Brain className="w-3 h-3" /> Ethical
          </button>
          <button onClick={() => handleStartEthosTest('logical')}
                  className="text-[11px] text-[#cccccc] hover:text-white flex items-center gap-1 hover:bg-[#505050] px-2 py-0.5 rounded transition-colors">
            <AlertTriangle className="w-3 h-3" /> Logical
          </button>
          <button onClick={() => handleStartEthosTest('truthfulness')}
                  className="text-[11px] text-[#cccccc] hover:text-white flex items-center gap-1 hover:bg-[#505050] px-2 py-0.5 rounded transition-colors">
            <CheckCircle className="w-3 h-3" /> Truth
          </button>
          <div className="w-px h-3 bg-[#555] mx-1" />
          <button onClick={saveCurrentFile}
                  className="text-[11px] text-[#cccccc] hover:text-white flex items-center gap-1 hover:bg-[#505050] px-2 py-0.5 rounded transition-colors">
            <Save className="w-3 h-3" /> Save
          </button>
          <div className="w-px h-3 bg-[#555] mx-1" />
          <button onClick={() => setLeftSidebarOpen(p => !p)}
                  className="p-1 rounded hover:bg-[#505050] text-[#999] hover:text-white transition-colors" title="Toggle Explorer (Ctrl+B)">
            <PanelLeft className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => setTerminalVisible(p => !p)}
                  className="p-1 rounded hover:bg-[#505050] text-[#999] hover:text-white transition-colors" title="Toggle Terminal (Ctrl+`)">
            <PanelBottom className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => { setActiveActivity('models'); setRightSidebarOpen(p => !p); setLeftSidebarOpen(false); }}
                  className="p-1 rounded hover:bg-[#505050] text-[#999] hover:text-white transition-colors" title="Toggle Models (Ctrl+Shift+M)">
            <Brain className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => { setActiveActivity('agent'); setRightSidebarOpen(p => !p); setLeftSidebarOpen(false); }}
                  className="p-1 rounded hover:bg-[#505050] text-[#999] hover:text-white transition-colors" title="Toggle AI Agent (Ctrl+Shift+A)">
            <Bot className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* ── Main Body ─────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── Activity Bar ──────────────────────────────────────────── */}
        <div className="w-[48px] flex-shrink-0 flex flex-col items-center py-1"
             style={{ background: '#333333', borderRight: '1px solid #3e3e42' }}>
          {ACTIVITY_ITEMS.map(item => {
            const Icon = item.icon;
            const isRightPanel = item.id === 'models' || item.id === 'agent' || item.id === 'model-testing';
            const isActive = (item.id === 'explorer' && leftSidebarOpen && activeActivity === 'explorer') ||
                             (isRightPanel && rightSidebarOpen && activeActivity === item.id) ||
                             (activeActivity === item.id && leftSidebarOpen && !isRightPanel && item.id !== 'explorer');
            return (
              <button
                key={item.id}
                onClick={() => handleActivityClick(item.id)}
                className={`w-[48px] h-[48px] flex items-center justify-center relative transition-colors ${
                  isActive ? 'text-white' : 'text-[#858585] hover:text-white'
                }`}
                title={`${item.label}${item.shortcut ? ` (${item.shortcut})` : ''}`}
              >
                <Icon className="w-[22px] h-[22px]" />
                {isActive && (
                  <div className="absolute left-0 top-[10px] w-[2px] h-[28px] bg-white rounded-r" />
                )}
              </button>
            );
          })}
        </div>

        {/* ── Left Sidebar (File Explorer) ──────────────────────────── */}
        {leftSidebarOpen && activeActivity === 'explorer' && (
          <div className="flex-shrink-0 overflow-hidden transition-all duration-200"
               style={{ width: 260, borderRight: '1px solid #3e3e42' }}>
            <IDEFileExplorer
              files={files}
              selectedFile={selectedFile}
              onFileSelect={openFileInTab}
              onFilesUploaded={handleFilesUploaded}
              onFileRename={handleFileRename}
              onFileDelete={handleFileDelete}
              onFileCreate={handleFileCreate}
            />
          </div>
        )}

        {/* ── Left Sidebar (Settings) ────────────────────────────────── */}
        {leftSidebarOpen && activeActivity === 'settings' && (
          <div className="flex-shrink-0 overflow-hidden transition-all duration-200"
               style={{ width: 260, borderRight: '1px solid #3e3e42' }}>
            <IDESettings config={terminalConfig} onConfigChange={setTerminalConfig} />
          </div>
        )}

        {/* ── Center: Editor + Terminal ──────────────────────────────── */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

          {/* Tab Bar */}
          <div className="flex items-center h-[35px] flex-shrink-0 overflow-x-auto"
               style={{ background: '#252526', borderBottom: '1px solid #3e3e42' }}>
            {tabs.map(tab => {
              const isActive = tab.id === activeTabId;
              return (
                <div
                  key={tab.id}
                  className={`flex items-center gap-1.5 px-3 h-full text-[13px] cursor-pointer border-r group transition-colors ${
                    isActive
                      ? 'text-white'
                      : 'text-[#969696] hover:text-[#ccc]'
                  }`}
                  style={{
                    background: isActive ? '#1e1e1e' : '#2d2d2d',
                    borderColor: '#3e3e42',
                    borderTop: isActive ? '1px solid #007acc' : '1px solid transparent',
                  }}
                  onClick={() => handleTabSelect(tab.id)}
                >
                  {tab.isDirty && <Circle className="w-2 h-2 fill-[#e8ab6a] text-[#e8ab6a] flex-shrink-0" />}
                  <span className="truncate max-w-[120px]">{tab.name}</span>
                  <button
                    onClick={e => { e.stopPropagation(); handleTabClose(tab.id); }}
                    className="opacity-0 group-hover:opacity-100 hover:bg-[#3e3e42] rounded p-0.5 transition-opacity ml-1"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              );
            })}
          </div>

          {/* Editor Area */}
          <div className="flex-1 relative min-h-0" style={{ background: '#1e1e1e' }}>
            <MonacoEditor
              value={code}
              onChange={handleCodeChange}
              language={language}
              theme="vs-dark"
              height="100%"
            />
            {/* Welcome screen when no tabs */}
            {tabs.length === 0 && (
              <div className="absolute inset-0 flex items-center justify-center" style={{ background: '#1e1e1e' }}>
                <div className="text-center">
                  <h2 className="text-[24px] font-light text-[#555] mb-2">ETHOS Editor</h2>
                  <p className="text-[13px] text-[#666] mb-6">Open a file from the explorer or drop files to get started</p>
                  <div className="flex flex-col gap-2 text-[12px] text-[#888]">
                    <span><kbd className="px-1.5 py-0.5 bg-[#333] rounded text-[#ccc]">Ctrl+B</kbd> Toggle Explorer</span>
                    <span><kbd className="px-1.5 py-0.5 bg-[#333] rounded text-[#ccc]">Ctrl+`</kbd> Toggle Terminal</span>
                    <span><kbd className="px-1.5 py-0.5 bg-[#333] rounded text-[#ccc]">Ctrl+Shift+M</kbd> Toggle AI Models</span>
                    <span><kbd className="px-1.5 py-0.5 bg-[#333] rounded text-[#ccc]">Ctrl+S</kbd> Save File</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Terminal Resize Handle */}
          {terminalVisible && (
            <div
              className="h-[4px] cursor-ns-resize flex-shrink-0 hover:bg-[#007acc] transition-colors"
              style={{ background: '#3e3e42' }}
              onMouseDown={onDragStart}
            />
          )}

          {/* Terminal */}
          {terminalVisible && (
            <div className="flex-shrink-0" style={{ height: terminalHeight }}>
              <IDETerminal
                sessionId={sessionId}
                visible={terminalVisible}
                onToggle={() => setTerminalVisible(false)}
                config={terminalConfig}
                onVenvStatusChange={setVenvStatus}
              />
            </div>
          )}
        </div>

        {/* ── Right Sidebar (AI Models) ─────────────────────────────── */}
        {rightSidebarOpen && activeActivity === 'models' && (
          <div className="flex-shrink-0 overflow-hidden transition-all duration-200"
               style={{ width: 280, borderLeft: '1px solid #3e3e42' }}>
            <IDEModelSidebar
              selectedModelId={selectedModelId}
              onModelSelect={setSelectedModelId}
            />
          </div>
        )}

        {/* ── Right Sidebar (AI Agent) ──────────────────────────────────── */}
        {rightSidebarOpen && activeActivity === 'agent' && (
          <div className="flex-shrink-0 overflow-hidden transition-all duration-200"
               style={{ width: 380, borderLeft: '1px solid #3e3e42' }}>
            <AIAgentPanel workspaceRoot={workspacePath || (sessionId ? `backend/projects/project_${sessionId}` : '')} onRefreshTree={loadWorkspaceTree} />
          </div>
        )}

        {/* ── Right Sidebar (Model Testing) ────────────────────────────── */}
        {rightSidebarOpen && activeActivity === 'model-testing' && (
          <div className="flex-shrink-0 overflow-hidden transition-all duration-200"
               style={{ width: 420, borderLeft: '1px solid #3e3e42' }}>
            <ModelUploadWizard
              sessionId={sessionId}
              onSessionCreated={(sid) => setSessionId(sid)}
              onClose={() => setRightSidebarOpen(false)}
            />
          </div>
        )}
      </div>

      {/* ── Status Bar ────────────────────────────────────────────── */}
      <div className="h-[22px] flex items-center justify-between px-3 flex-shrink-0 select-none"
           style={{ background: '#007acc' }}>
        <div className="flex items-center gap-3 text-[11px] text-white/90">
          <span className="flex items-center gap-1">
            <GitBranch className="w-3 h-3" /> main
          </span>
          <span className="flex items-center gap-1">
            <CheckCircle className="w-3 h-3" /> 0 errors
          </span>
          {venvStatus && (venvStatus.status === 'activated' || venvStatus.status === 'ready') && (
            <span className="flex items-center gap-1 bg-white/10 px-1.5 py-0.5 rounded">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
              venv{venvStatus.venvName ? `: ${venvStatus.venvName}` : ''}
            </span>
          )}
          {venvStatus && venvStatus.status === 'error' && (
            <span className="flex items-center gap-1 bg-red-500/20 px-1.5 py-0.5 rounded text-red-200">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
              venv error
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-[11px] text-white/90">
          {activeTab && <span>{activeTab.name}</span>}
          <span className="uppercase">{language}</span>
          <span>Ln {cursorLine}, Col {cursorCol}</span>
          <span>UTF-8</span>
        </div>
      </div>

      {/* ── ETHOS Test Results Dialog ─────────────────────────────── */}
      <Dialog open={showEthosDialog} onOpenChange={setShowEthosDialog}>
        <DialogContent className="max-w-5xl h-[85vh] rounded-2xl border bg-white text-gray-900 shadow-2xl">
          <div className="flex items-center justify-between">
            <DialogHeader>
              <DialogTitle>
                {currentTestType === 'ethical' ? 'Ethical Test Results'
                  : currentTestType === 'logical' ? 'Logical Test Results'
                  : 'Truthfulness Test Results'}
              </DialogTitle>
              <DialogDescription>
                <span className="text-gray-600">Automated Analysis of Code Implications</span>
              </DialogDescription>
            </DialogHeader>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleDownloadPdf} className="gap-2">
                <Download className="w-4 h-4" /> Download PDF
              </Button>
              <Button variant="ghost" size="icon" onClick={() => setShowEthosDialog(false)}>
                <X className="w-4 h-4" />
              </Button>
            </div>
          </div>
          <ScrollArea className="flex-1 h-full max-h-[calc(85vh-120px)]">
            <div ref={resultsRef}>
              <EthosTestResults
                type={currentTestType}
                isLoading={isTestLoading}
                results={
                  (currentTestType === 'ethical'
                    ? (ethicalResults?.results ?? null)
                    : currentTestType === 'logical'
                      ? (logicalResults?.results ?? null)
                      : (truthfulnessResults?.results ?? null)) as any
                }
                prompts={currentPrompts}
              />
            </div>
          </ScrollArea>
          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-gray-500">Use Download PDF to save these results.</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleDownloadPdf} className="gap-2">
                <Download className="w-4 h-4" /> Download as PDF
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setShowEthosDialog(false)} className="gap-2">
                <X className="w-4 h-4" /> Close
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Editor;
