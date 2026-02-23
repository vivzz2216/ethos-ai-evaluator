/**
 * Real Filesystem API client.
 * Talks to the Node.js terminal-server's /fs/* endpoints
 * to perform ACTUAL disk operations.
 */

const FS_BASE = 'http://localhost:8001';

export interface FsFileNode {
  id: string;
  name: string;
  type: 'file' | 'folder';
  path: string;
  children?: FsFileNode[];
  size?: number;
  content?: string;
}

// ── Workspace ────────────────────────────────────────────────────────

export async function setWorkspace(dirPath: string): Promise<string | null> {
  try {
    const res = await fetch(`${FS_BASE}/fs/workspace`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: dirPath }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.workspace;
  } catch {
    return null;
  }
}

export async function getWorkspace(): Promise<string | null> {
  try {
    const res = await fetch(`${FS_BASE}/fs/workspace`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.workspace;
  } catch {
    return null;
  }
}

// ── Tree ─────────────────────────────────────────────────────────────

export async function getTree(depth = 4): Promise<FsFileNode[]> {
  try {
    const res = await fetch(`${FS_BASE}/fs/tree?depth=${depth}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.tree || [];
  } catch {
    return [];
  }
}

// ── Read file ────────────────────────────────────────────────────────

export async function readFile(filePath: string): Promise<{ content: string; size: number } | null> {
  try {
    const res = await fetch(`${FS_BASE}/fs/read?path=${encodeURIComponent(filePath)}`);
    if (!res.ok) return null;
    const data = await res.json();
    return { content: data.content, size: data.size };
  } catch {
    return null;
  }
}

// ── Write / Create file ──────────────────────────────────────────────

export async function writeFile(filePath: string, content: string): Promise<boolean> {
  try {
    const res = await fetch(`${FS_BASE}/fs/write`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: filePath, content }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

// ── Delete ───────────────────────────────────────────────────────────

export async function deleteFile(filePath: string): Promise<boolean> {
  try {
    const res = await fetch(`${FS_BASE}/fs/delete?path=${encodeURIComponent(filePath)}`, {
      method: 'DELETE',
    });
    return res.ok;
  } catch {
    return false;
  }
}

// ── Rename / Move ────────────────────────────────────────────────────

export async function renameFile(oldPath: string, newPath: string): Promise<boolean> {
  try {
    const res = await fetch(`${FS_BASE}/fs/rename`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ oldPath, newPath }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

// ── Create directory ─────────────────────────────────────────────────

export async function mkdir(dirPath: string): Promise<boolean> {
  try {
    const res = await fetch(`${FS_BASE}/fs/mkdir`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: dirPath }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

// ── Check exists ─────────────────────────────────────────────────────

export async function exists(filePath: string): Promise<{ exists: boolean; type: 'file' | 'folder' | null }> {
  try {
    const res = await fetch(`${FS_BASE}/fs/exists?path=${encodeURIComponent(filePath)}`);
    if (!res.ok) return { exists: false, type: null };
    return await res.json();
  } catch {
    return { exists: false, type: null };
  }
}

// ── Health check ─────────────────────────────────────────────────────

export async function fsHealthCheck(): Promise<boolean> {
  try {
    const res = await fetch(`${FS_BASE}/health`, { signal: AbortSignal.timeout(2000) });
    return res.ok;
  } catch {
    return false;
  }
}
