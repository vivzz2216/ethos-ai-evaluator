import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  ChevronRight,
  ChevronDown,
  File,
  Folder,
  FolderOpen,
  Upload,
  Plus,
  Trash2,
  Edit3,
  Copy,
  Clipboard,
  FileText,
  FileCode,
  FileJson,
  Search,
  RefreshCw,
  FolderPlus,
  FilePlus,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────
export interface FileNode {
  id: string;
  name: string;
  type: 'file' | 'folder';
  content?: string;
  path: string;
  children?: FileNode[];
  rawFile?: globalThis.File;  // Raw File object for binary uploads (not read into memory)
}

// Binary file extensions — must NOT be read as text
const BINARY_EXTENSIONS = new Set([
  '.safetensors', '.bin', '.pt', '.pth', '.onnx', '.tflite',
  '.h5', '.hdf5', '.pkl', '.pickle', '.msgpack', '.pb',
  '.gguf', '.ggml', '.ckpt', '.mar', '.params',
  '.model', '.spiece', '.sentencepiece',
]);

interface IDEFileExplorerProps {
  files: FileNode[];
  selectedFile: FileNode | null;
  onFileSelect: (file: FileNode) => void;
  onFilesUploaded: (files: FileNode[]) => void;
  onFileRename: (fileId: string, newName: string) => void;
  onFileDelete: (fileId: string) => void;
  onFileCreate: (parentPath: string, name: string, type: 'file' | 'folder') => void;
}

// ── Helpers ────────────────────────────────────────────────────────
let _id = 0;
const uid = () => `f${++_id}_${Math.random().toString(36).slice(2, 7)}`;

const EXT_COLORS: Record<string, string> = {
  '.py': 'text-[#4584b6]',
  '.js': 'text-[#f7df1e]',
  '.jsx': 'text-[#61dafb]',
  '.ts': 'text-[#3178c6]',
  '.tsx': 'text-[#3178c6]',
  '.html': 'text-[#e34c26]',
  '.css': 'text-[#563d7c]',
  '.scss': 'text-[#c6538c]',
  '.json': 'text-[#cbcb41]',
  '.md': 'text-[#519aba]',
  '.txt': 'text-[#a0a0a0]',
  '.yml': 'text-[#cb171e]',
  '.yaml': 'text-[#cb171e]',
  '.env': 'text-[#ecd53f]',
  '.gitignore': 'text-[#f05032]',
  '.svg': 'text-[#ffb13b]',
  '.png': 'text-[#a074c4]',
  '.jpg': 'text-[#a074c4]',
};

function extColor(name: string) {
  const dot = name.lastIndexOf('.');
  if (dot === -1) return 'text-[#a0a0a0]';
  return EXT_COLORS[name.slice(dot).toLowerCase()] ?? 'text-[#a0a0a0]';
}

function fileIcon(name: string) {
  const ext = name.slice(name.lastIndexOf('.')).toLowerCase();
  if (['.js', '.jsx', '.ts', '.tsx', '.py', '.java', '.cpp', '.c', '.rs', '.go'].includes(ext))
    return <FileCode className={`w-4 h-4 flex-shrink-0 ${extColor(name)}`} />;
  if (['.json', '.yml', '.yaml', '.toml'].includes(ext))
    return <FileJson className={`w-4 h-4 flex-shrink-0 ${extColor(name)}`} />;
  if (['.md', '.txt', '.rst', '.log'].includes(ext))
    return <FileText className={`w-4 h-4 flex-shrink-0 ${extColor(name)}`} />;
  return <File className={`w-4 h-4 flex-shrink-0 ${extColor(name)}`} />;
}

const EXCLUDED = ['node_modules', '.git', '__pycache__', '.pytest_cache', 'venv', '.venv', 'env', '.env', '.coverage'];

function shouldInclude(path: string) {
  for (const ex of EXCLUDED) if (path.includes(ex + '/') || path.endsWith(ex)) return false;
  return true;
}

// ── Context Menu ───────────────────────────────────────────────────
interface CtxMenuProps {
  x: number;
  y: number;
  node: FileNode | null;
  onClose: () => void;
  onRename: () => void;
  onDelete: () => void;
  onNewFile: () => void;
  onNewFolder: () => void;
  onCopy: () => void;
}

const ContextMenu: React.FC<CtxMenuProps> = ({ x, y, node, onClose, onRename, onDelete, onNewFile, onNewFolder, onCopy }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as HTMLElement)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  const items = [
    { label: 'New File', icon: FilePlus, action: onNewFile },
    { label: 'New Folder', icon: FolderPlus, action: onNewFolder },
    null, // separator
    { label: 'Copy Path', icon: Copy, action: onCopy },
    { label: 'Rename', icon: Edit3, action: onRename },
    null,
    { label: 'Delete', icon: Trash2, action: onDelete, danger: true },
  ];

  return (
    <div
      ref={ref}
      className="fixed z-[9999] min-w-[180px] bg-[#252526] border border-[#3e3e42] rounded-md shadow-2xl py-1 text-[13px]"
      style={{ left: x, top: y }}
    >
      {items.map((item, i) =>
        item === null ? (
          <div key={`sep-${i}`} className="h-px bg-[#3e3e42] my-1" />
        ) : (
          <button
            key={item.label}
            onClick={() => { item.action(); onClose(); }}
            className={`w-full flex items-center gap-2 px-3 py-1.5 hover:bg-[#094771] transition-colors ${
              (item as any).danger ? 'text-red-400 hover:text-red-300' : 'text-[#cccccc] hover:text-white'
            }`}
          >
            <item.icon className="w-4 h-4 flex-shrink-0" />
            {item.label}
          </button>
        )
      )}
    </div>
  );
};

// ── Inline Rename Input ────────────────────────────────────────────
const InlineInput: React.FC<{
  initial: string;
  onSubmit: (val: string) => void;
  onCancel: () => void;
}> = ({ initial, onSubmit, onCancel }) => {
  const [val, setVal] = useState(initial);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => { ref.current?.select(); }, []);

  return (
    <input
      ref={ref}
      autoFocus
      value={val}
      onChange={e => setVal(e.target.value)}
      onKeyDown={e => {
        if (e.key === 'Enter' && val.trim()) onSubmit(val.trim());
        if (e.key === 'Escape') onCancel();
      }}
      onBlur={() => { if (val.trim()) onSubmit(val.trim()); else onCancel(); }}
      className="bg-[#3c3c3c] text-[#cccccc] text-[13px] px-1 py-0 border border-[#007acc] rounded-sm outline-none w-full"
    />
  );
};

// ── Tree Node ──────────────────────────────────────────────────────
const TreeNode: React.FC<{
  node: FileNode;
  depth: number;
  selectedId: string | null;
  onSelect: (n: FileNode) => void;
  onContextMenu: (e: React.MouseEvent, n: FileNode) => void;
  renamingId: string | null;
  onRenameSubmit: (id: string, name: string) => void;
  onRenameCancel: () => void;
  filter: string;
}> = ({ node, depth, selectedId, onSelect, onContextMenu, renamingId, onRenameSubmit, onRenameCancel, filter }) => {
  const [expanded, setExpanded] = useState(depth < 2);
  const isFolder = node.type === 'folder';
  const isSelected = selectedId === node.id;
  const isRenaming = renamingId === node.id;

  // Filter logic
  if (filter) {
    const lf = filter.toLowerCase();
    if (isFolder) {
      const hasMatch = node.children?.some(c => matchesFilter(c, lf));
      if (!hasMatch) return null;
    } else {
      if (!node.name.toLowerCase().includes(lf)) return null;
    }
  }

  const handleClick = () => {
    if (isFolder) setExpanded(p => !p);
    else onSelect(node);
  };

  return (
    <div>
      <div
        className={`flex items-center h-[22px] cursor-pointer select-none group transition-colors duration-75 ${
          isSelected ? 'bg-[#094771]' : 'hover:bg-[#2a2d2e]'
        }`}
        style={{ paddingLeft: depth * 12 + 4 }}
        onClick={handleClick}
        onContextMenu={e => onContextMenu(e, node)}
      >
        {/* Chevron */}
        <span className="w-4 h-4 flex items-center justify-center flex-shrink-0">
          {isFolder ? (
            expanded ? <ChevronDown className="w-3.5 h-3.5 text-[#c5c5c5]" /> : <ChevronRight className="w-3.5 h-3.5 text-[#c5c5c5]" />
          ) : null}
        </span>

        {/* Icon */}
        <span className="mr-1.5 flex items-center">
          {isFolder ? (
            expanded ? <FolderOpen className="w-4 h-4 text-[#dcb67a] flex-shrink-0" /> : <Folder className="w-4 h-4 text-[#dcb67a] flex-shrink-0" />
          ) : (
            fileIcon(node.name)
          )}
        </span>

        {/* Name or rename input */}
        {isRenaming ? (
          <InlineInput
            initial={node.name}
            onSubmit={name => onRenameSubmit(node.id, name)}
            onCancel={onRenameCancel}
          />
        ) : (
          <span className={`text-[13px] truncate ${isSelected ? 'text-white' : 'text-[#cccccc]'}`}>
            {node.name}
          </span>
        )}
      </div>

      {/* Children */}
      {isFolder && expanded && node.children && (
        <div>
          {sortNodes(node.children).map(child => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
              onContextMenu={onContextMenu}
              renamingId={renamingId}
              onRenameSubmit={onRenameSubmit}
              onRenameCancel={onRenameCancel}
              filter={filter}
            />
          ))}
        </div>
      )}
    </div>
  );
};

function matchesFilter(node: FileNode, filter: string): boolean {
  if (node.name.toLowerCase().includes(filter)) return true;
  if (node.children) return node.children.some(c => matchesFilter(c, filter));
  return false;
}

function sortNodes(nodes: FileNode[]): FileNode[] {
  return [...nodes].sort((a, b) => {
    if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
}

// ── Main Component ─────────────────────────────────────────────────
const IDEFileExplorer: React.FC<IDEFileExplorerProps> = ({
  files,
  selectedFile,
  onFileSelect,
  onFilesUploaded,
  onFileRename,
  onFileDelete,
  onFileCreate,
}) => {
  const [filter, setFilter] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const [ctxMenu, setCtxMenu] = useState<{ x: number; y: number; node: FileNode | null } | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [creatingIn, setCreatingIn] = useState<{ parentPath: string; type: 'file' | 'folder' } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  // ── Drag & Drop ──────────────────────────────────────────────────
  const handleDragOver = useCallback((e: React.DragEvent) => { e.preventDefault(); setIsDragOver(true); }, []);
  const handleDragLeave = useCallback((e: React.DragEvent) => { e.preventDefault(); setIsDragOver(false); }, []);

  const readFileContent = (file: globalThis.File): Promise<string> =>
    new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = e => resolve(e.target?.result as string);
      r.onerror = reject;
      r.readAsText(file);
    });

  const processFileList = useCallback(async (fileList: FileList) => {
    const map = new Map<string, FileNode>();
    const MAX = 2000;
    const valid: globalThis.File[] = [];

    for (let i = 0; i < fileList.length; i++) {
      const f = fileList[i];
      const relPath = f.webkitRelativePath || f.name;
      if (shouldInclude(relPath)) valid.push(f);
    }

    if (valid.length > MAX) {
      alert(`Too many files (${valid.length}). Max is ${MAX}.`);
      return [];
    }

    for (const file of valid) {
      try {
        const parts = (file.webkitRelativePath || file.name).split('/');
        const fileName = parts[parts.length - 1];
        const ext = fileName.includes('.') ? '.' + fileName.split('.').pop()!.toLowerCase() : '';
        const isBinary = BINARY_EXTENSIONS.has(ext);

        // Binary files: store raw File object, DO NOT read into memory
        // Text files: read content as text for Monaco editor
        let content: string | undefined;
        let rawFile: globalThis.File | undefined;
        if (isBinary) {
          rawFile = file;
          const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
          content = `[Binary model file: ${fileName} (${sizeMB} MB)]`;
        } else {
          content = await readFileContent(file);
        }

        const fileNode: FileNode = {
          id: uid(),
          name: fileName,
          type: 'file',
          content,
          path: file.webkitRelativePath || file.name,
          rawFile,
        };

        let parentNode: FileNode | undefined;
        let currentPath = '';

        for (let j = 0; j < parts.length - 1; j++) {
          currentPath = currentPath ? `${currentPath}/${parts[j]}` : parts[j];
          if (!map.has(currentPath)) {
            const folder: FileNode = { id: uid(), name: parts[j], type: 'folder', path: currentPath, children: [] };
            map.set(currentPath, folder);
            if (parentNode) parentNode.children!.push(folder);
          }
          parentNode = map.get(currentPath);
        }

        if (parentNode) parentNode.children!.push(fileNode);
        else map.set(fileNode.path, fileNode);
      } catch { /* skip unreadable files */ }
    }

    return Array.from(map.values()).filter(n => !n.path.includes('/'));
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files.length) {
      const nodes = await processFileList(e.dataTransfer.files);
      if (nodes.length) onFilesUploaded([...files, ...nodes]);
    }
  }, [files, onFilesUploaded, processFileList]);

  const handleInputChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) {
      const nodes = await processFileList(e.target.files);
      if (nodes.length) onFilesUploaded([...files, ...nodes]);
    }
    e.target.value = '';
  }, [files, onFilesUploaded, processFileList]);

  // ── Context Menu Handlers ────────────────────────────────────────
  const handleContextMenu = useCallback((e: React.MouseEvent, node: FileNode) => {
    e.preventDefault();
    e.stopPropagation();
    setCtxMenu({ x: e.clientX, y: e.clientY, node });
  }, []);

  const handleRootContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setCtxMenu({ x: e.clientX, y: e.clientY, node: null });
  }, []);

  return (
    <div className="h-full flex flex-col bg-[#252526] select-none">
      {/* Header */}
      <div className="flex items-center justify-between px-3 h-[35px] flex-shrink-0 border-b border-[#3e3e42]">
        <span className="text-[11px] font-semibold tracking-wider text-[#bbbbbb] uppercase">Explorer</span>
        <div className="flex items-center gap-0.5">
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-1 rounded hover:bg-[#3e3e42] text-[#cccccc] hover:text-white transition-colors"
            title="Upload Files"
          >
            <FilePlus className="w-4 h-4" />
          </button>
          <button
            onClick={() => folderInputRef.current?.click()}
            className="p-1 rounded hover:bg-[#3e3e42] text-[#cccccc] hover:text-white transition-colors"
            title="Upload Folder"
          >
            <FolderPlus className="w-4 h-4" />
          </button>
          <button
            onClick={() => onFilesUploaded([])}
            className="p-1 rounded hover:bg-[#3e3e42] text-[#cccccc] hover:text-white transition-colors"
            title="Clear All"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="px-2 py-1.5 border-b border-[#3e3e42]">
        <div className="flex items-center bg-[#3c3c3c] rounded px-2 h-[24px]">
          <Search className="w-3.5 h-3.5 text-[#848484] flex-shrink-0" />
          <input
            value={filter}
            onChange={e => setFilter(e.target.value)}
            placeholder="Search files..."
            className="bg-transparent text-[12px] text-[#cccccc] placeholder-[#848484] outline-none w-full ml-1.5"
          />
        </div>
      </div>

      {/* Tree or Drop Zone */}
      <div
        className={`flex-1 overflow-y-auto overflow-x-hidden transition-colors ${
          isDragOver ? 'bg-[#094771]/30' : ''
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onContextMenu={handleRootContextMenu}
      >
        {files.length === 0 ? (
          /* Empty state / drop zone */
          <div className="flex flex-col items-center justify-center h-full px-4 text-center">
            <div className={`border-2 border-dashed rounded-lg p-6 w-full transition-all duration-300 ${
              isDragOver
                ? 'border-[#007acc] bg-[#094771]/20 scale-[1.02]'
                : 'border-[#3e3e42] hover:border-[#555]'
            }`}>
              <Upload className={`w-10 h-10 mx-auto mb-3 transition-colors ${
                isDragOver ? 'text-[#007acc]' : 'text-[#555]'
              }`} />
              <p className="text-[12px] text-[#888] mb-3">
                {isDragOver ? 'Drop files here' : 'Drag & drop files or folders'}
              </p>
              <div className="flex gap-2 justify-center">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="text-[11px] px-3 py-1 rounded bg-[#0e639c] text-white hover:bg-[#1177bb] transition-colors"
                >
                  Open Files
                </button>
                <button
                  onClick={() => folderInputRef.current?.click()}
                  className="text-[11px] px-3 py-1 rounded bg-[#3c3c3c] text-[#cccccc] hover:bg-[#4e4e4e] transition-colors"
                >
                  Open Folder
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="py-0.5">
            {sortNodes(files).map(node => (
              <TreeNode
                key={node.id}
                node={node}
                depth={0}
                selectedId={selectedFile?.id ?? null}
                onSelect={onFileSelect}
                onContextMenu={handleContextMenu}
                renamingId={renamingId}
                onRenameSubmit={(id, name) => { onFileRename(id, name); setRenamingId(null); }}
                onRenameCancel={() => setRenamingId(null)}
                filter={filter}
              />
            ))}

            {/* Inline create */}
            {creatingIn && (
              <div className="flex items-center h-[22px] pl-4 gap-1.5">
                {creatingIn.type === 'folder' ? (
                  <Folder className="w-4 h-4 text-[#dcb67a]" />
                ) : (
                  <File className="w-4 h-4 text-[#a0a0a0]" />
                )}
                <InlineInput
                  initial=""
                  onSubmit={name => { onFileCreate(creatingIn.parentPath, name, creatingIn.type); setCreatingIn(null); }}
                  onCancel={() => setCreatingIn(null)}
                />
              </div>
            )}

            {/* Drop overlay when files exist */}
            {isDragOver && (
              <div className="mx-2 my-2 border-2 border-dashed border-[#007acc] rounded-md p-3 text-center">
                <p className="text-[11px] text-[#007acc]">Drop to add files</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Hidden inputs */}
      <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleInputChange} />
      <input ref={folderInputRef} type="file" multiple {...({ webkitdirectory: '' } as any)} className="hidden" onChange={handleInputChange} />

      {/* Context Menu */}
      {ctxMenu && (
        <ContextMenu
          x={ctxMenu.x}
          y={ctxMenu.y}
          node={ctxMenu.node}
          onClose={() => setCtxMenu(null)}
          onRename={() => { if (ctxMenu.node) setRenamingId(ctxMenu.node.id); }}
          onDelete={() => { if (ctxMenu.node) onFileDelete(ctxMenu.node.id); }}
          onNewFile={() => {
            const parentPath = ctxMenu.node?.type === 'folder' ? ctxMenu.node.path : '';
            setCreatingIn({ parentPath, type: 'file' });
          }}
          onNewFolder={() => {
            const parentPath = ctxMenu.node?.type === 'folder' ? ctxMenu.node.path : '';
            setCreatingIn({ parentPath, type: 'folder' });
          }}
          onCopy={() => {
            if (ctxMenu.node) navigator.clipboard.writeText(ctxMenu.node.path);
          }}
        />
      )}
    </div>
  );
};

export default IDEFileExplorer;
