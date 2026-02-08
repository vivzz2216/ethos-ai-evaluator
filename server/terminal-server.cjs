/**
 * ETHOS Terminal Server
 * Node.js WebSocket server using node-pty for real terminal I/O.
 * Handles: Python detection, venv auto-creation/activation, requirements install,
 * error handling, and terminal state persistence.
 */

const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const pty = require('node-pty');
const os = require('os');
const path = require('path');
const fs = require('fs');

const PORT = 8001;
const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

// ── Session Store ──────────────────────────────────────────────────
const sessions = new Map(); // terminalId -> { pty, ws, state }

// ── Configuration Defaults ─────────────────────────────────────────
const DEFAULT_CONFIG = {
  autoCreateVenv: true,
  autoActivateVenv: true,
  autoInstallDeps: 'ask', // 'ask' | 'always' | 'never'
  preferredPython: os.platform() === 'win32' ? 'python' : 'python3',
  showVenvInTree: true,
};

// ── Helpers ────────────────────────────────────────────────────────
function getShell() {
  if (os.platform() === 'win32') {
    return { shell: 'powershell.exe', args: ['-NoLogo'] };
  }
  const shell = process.env.SHELL || '/bin/bash';
  return { shell, args: [] };
}

function detectPython(workingDir) {
  // Check for Python project indicators
  const indicators = [
    'requirements.txt',
    'setup.py',
    'setup.cfg',
    'pyproject.toml',
    'Pipfile',
    'poetry.lock',
    'environment.yml',
    'conda.yml',
  ];

  const pyFiles = [];
  try {
    const entries = fs.readdirSync(workingDir);
    for (const entry of entries) {
      if (indicators.includes(entry)) return { isPython: true, indicator: entry };
      if (entry.endsWith('.py')) pyFiles.push(entry);
    }
  } catch { /* ignore */ }

  if (pyFiles.length > 0) return { isPython: true, indicator: `${pyFiles.length} .py files` };
  return { isPython: false, indicator: null };
}

function findExistingVenv(workingDir) {
  const venvNames = ['venv', '.venv', 'env', '.env'];
  for (const name of venvNames) {
    const venvPath = path.join(workingDir, name);
    const activatePath = os.platform() === 'win32'
      ? path.join(venvPath, 'Scripts', 'activate.bat')
      : path.join(venvPath, 'bin', 'activate');
    if (fs.existsSync(activatePath)) {
      return { name, path: venvPath, activatePath };
    }
  }
  return null;
}

function checkPythonInstalled(preferredPython) {
  try {
    const { execSync } = require('child_process');
    const result = execSync(`${preferredPython} --version`, { timeout: 5000, encoding: 'utf-8' });
    return { installed: true, version: result.trim() };
  } catch {
    // Try fallback
    const fallback = preferredPython === 'python' ? 'python3' : 'python';
    try {
      const { execSync } = require('child_process');
      const result = execSync(`${fallback} --version`, { timeout: 5000, encoding: 'utf-8' });
      return { installed: true, version: result.trim(), useFallback: fallback };
    } catch {
      return { installed: false, version: null };
    }
  }
}

function hasRequirementsTxt(workingDir) {
  return fs.existsSync(path.join(workingDir, 'requirements.txt'));
}

// ── Notification helper (sends JSON messages to client) ────────────
function sendNotification(ws, type, data) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type, ...data }));
  }
}

// ── WebSocket Connection Handler ───────────────────────────────────
wss.on('connection', (ws, req) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const terminalId = url.searchParams.get('terminalId') || `term_${Date.now()}`;
  const workingDir = url.searchParams.get('cwd') || os.homedir();
  const configParam = url.searchParams.get('config');

  let config = { ...DEFAULT_CONFIG };
  if (configParam) {
    try { config = { ...config, ...JSON.parse(decodeURIComponent(configParam)) }; } catch { /* use defaults */ }
  }

  console.log(`[Terminal] New connection: ${terminalId}, cwd: ${workingDir}`);

  // Resolve working directory
  const cwd = fs.existsSync(workingDir) ? workingDir : os.homedir();

  // Spawn pty process
  const { shell, args } = getShell();
  let ptyProcess;

  try {
    ptyProcess = pty.spawn(shell, args, {
      name: 'xterm-256color',
      cols: 120,
      rows: 30,
      cwd,
      env: {
        ...process.env,
        TERM: 'xterm-256color',
        COLORTERM: 'truecolor',
      },
    });
  } catch (err) {
    console.error(`[Terminal] Failed to spawn pty:`, err);
    sendNotification(ws, 'error', {
      message: `Failed to start terminal: ${err.message}`,
      errorType: 'pty_spawn_failed',
      suggestion: 'Ensure node-pty is properly installed. Try: npm rebuild node-pty',
    });
    ws.close();
    return;
  }

  // Store session state
  const sessionState = {
    pty: ptyProcess,
    ws,
    config,
    cwd,
    terminalId,
    isVenvActive: false,
    venvPath: null,
    pythonExe: null,
    commandHistory: [],
    createdAt: Date.now(),
  };
  sessions.set(terminalId, sessionState);

  // ── PTY → WebSocket (terminal output to client) ──────────────────
  ptyProcess.onData((data) => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'output', data }));
    }
  });

  ptyProcess.onExit(({ exitCode, signal }) => {
    console.log(`[Terminal] Process exited: ${terminalId}, code: ${exitCode}, signal: ${signal}`);
    sendNotification(ws, 'exit', { exitCode, signal });
    sessions.delete(terminalId);
  });

  // ── WebSocket → PTY (client input to terminal) ───────────────────
  ws.on('message', (msg) => {
    let parsed;
    try {
      parsed = JSON.parse(msg.toString());
    } catch {
      // Raw string input
      ptyProcess.write(msg.toString());
      return;
    }

    switch (parsed.type) {
      case 'input':
        ptyProcess.write(parsed.data);
        break;

      case 'resize':
        if (parsed.cols && parsed.rows) {
          try { ptyProcess.resize(parsed.cols, parsed.rows); } catch { /* ignore */ }
        }
        break;

      case 'setup-venv':
        handleVenvSetup(sessionState, parsed.config || config);
        break;

      case 'get-state':
        sendNotification(ws, 'state', {
          isVenvActive: sessionState.isVenvActive,
          venvPath: sessionState.venvPath,
          pythonExe: sessionState.pythonExe,
          cwd: sessionState.cwd,
          config: sessionState.config,
        });
        break;

      case 'update-config':
        sessionState.config = { ...sessionState.config, ...parsed.config };
        sendNotification(ws, 'config-updated', { config: sessionState.config });
        break;

      case 'save-history':
        if (parsed.command) {
          sessionState.commandHistory.push(parsed.command);
          if (sessionState.commandHistory.length > 500) sessionState.commandHistory.shift();
        }
        break;

      default:
        break;
    }
  });

  ws.on('close', () => {
    console.log(`[Terminal] Connection closed: ${terminalId}`);
    try { ptyProcess.kill(); } catch { /* ignore */ }
    sessions.delete(terminalId);
  });

  ws.on('error', (err) => {
    console.error(`[Terminal] WebSocket error for ${terminalId}:`, err.message);
  });

  // ── Auto-setup after connection ──────────────────────────────────
  // Small delay to let the shell initialize
  setTimeout(() => {
    handleVenvSetup(sessionState, config);
  }, 1500);
});

// ── Venv Setup Logic ───────────────────────────────────────────────
async function handleVenvSetup(session, config) {
  const { ws, pty: ptyProcess, cwd } = session;

  // 1. Detect if this is a Python project
  const detection = detectPython(cwd);
  if (!detection.isPython) {
    sendNotification(ws, 'venv-status', {
      status: 'not-python',
      message: 'No Python project detected',
    });
    return;
  }

  sendNotification(ws, 'venv-status', {
    status: 'detected',
    message: `Python project detected (${detection.indicator})`,
  });

  // 2. Check if Python is installed
  const pythonCheck = checkPythonInstalled(config.preferredPython);
  if (!pythonCheck.installed) {
    sendNotification(ws, 'venv-status', {
      status: 'error',
      errorType: 'python_not_installed',
      message: 'Python is not installed on this system',
      suggestion: 'Install Python from https://www.python.org/downloads/',
      installUrl: 'https://www.python.org/downloads/',
    });
    return;
  }

  const pythonCmd = pythonCheck.useFallback || config.preferredPython;
  session.pythonExe = pythonCmd;

  sendNotification(ws, 'venv-status', {
    status: 'python-found',
    message: `${pythonCheck.version} found`,
    pythonCmd,
  });

  // 3. Check for existing venv
  const existingVenv = findExistingVenv(cwd);
  if (existingVenv) {
    sendNotification(ws, 'venv-status', {
      status: 'venv-exists',
      message: `Existing venv found: ${existingVenv.name}`,
      venvName: existingVenv.name,
      venvPath: existingVenv.path,
    });

    if (config.autoActivateVenv) {
      activateVenv(session, existingVenv);
    }
    return;
  }

  // 4. Create new venv if configured
  if (!config.autoCreateVenv) {
    sendNotification(ws, 'venv-status', {
      status: 'skipped',
      message: 'Auto-create venv is disabled',
    });
    return;
  }

  sendNotification(ws, 'venv-status', {
    status: 'creating',
    message: 'Creating virtual environment...',
  });

  // Write the venv creation command to the pty
  const venvName = 'venv';
  const createCmd = os.platform() === 'win32'
    ? `${pythonCmd} -m venv ${venvName}\r`
    : `${pythonCmd} -m venv ${venvName}\n`;

  ptyProcess.write(createCmd);

  // Wait for venv creation to complete, then activate
  const checkInterval = setInterval(() => {
    const venvPath = path.join(cwd, venvName);
    const activatePath = os.platform() === 'win32'
      ? path.join(venvPath, 'Scripts', 'activate.bat')
      : path.join(venvPath, 'bin', 'activate');

    if (fs.existsSync(activatePath)) {
      clearInterval(checkInterval);
      clearTimeout(timeout);

      sendNotification(ws, 'venv-status', {
        status: 'created',
        message: `Virtual environment "${venvName}" created successfully`,
        venvName,
        venvPath,
      });

      if (config.autoActivateVenv) {
        setTimeout(() => {
          activateVenv(session, { name: venvName, path: venvPath, activatePath });
        }, 500);
      }
    }
  }, 1000);

  // Timeout after 30 seconds
  const timeout = setTimeout(() => {
    clearInterval(checkInterval);
    const venvPath = path.join(cwd, venvName);
    if (!fs.existsSync(venvPath)) {
      sendNotification(ws, 'venv-status', {
        status: 'error',
        errorType: 'venv_creation_failed',
        message: 'Failed to create virtual environment',
        suggestion: `Try manually: ${pythonCmd} -m venv ${venvName}`,
      });
    }
  }, 30000);
}

function activateVenv(session, venvInfo) {
  const { ws, pty: ptyProcess, cwd } = session;

  sendNotification(ws, 'venv-status', {
    status: 'activating',
    message: `Activating ${venvInfo.name}...`,
  });

  let activateCmd;
  if (os.platform() === 'win32') {
    activateCmd = `& "${path.join(venvInfo.path, 'Scripts', 'Activate.ps1')}"\r`;
  } else {
    activateCmd = `source "${path.join(venvInfo.path, 'bin', 'activate')}"\n`;
  }

  try {
    ptyProcess.write(activateCmd);

    session.isVenvActive = true;
    session.venvPath = venvInfo.path;

    // Determine python exe inside venv
    session.pythonExe = os.platform() === 'win32'
      ? path.join(venvInfo.path, 'Scripts', 'python.exe')
      : path.join(venvInfo.path, 'bin', 'python');

    sendNotification(ws, 'venv-status', {
      status: 'activated',
      message: `Virtual environment "${venvInfo.name}" activated`,
      venvName: venvInfo.name,
      venvPath: venvInfo.path,
      pythonExe: session.pythonExe,
    });

    // 5. Check for requirements.txt and install
    setTimeout(() => {
      checkAndInstallRequirements(session);
    }, 1000);

  } catch (err) {
    sendNotification(ws, 'venv-status', {
      status: 'error',
      errorType: 'activation_failed',
      message: `Failed to activate venv: ${err.message}`,
      suggestion: os.platform() === 'win32'
        ? `Try manually: .\\${venvInfo.name}\\Scripts\\Activate.ps1`
        : `Try manually: source ${venvInfo.name}/bin/activate`,
    });
  }
}

function checkAndInstallRequirements(session) {
  const { ws, pty: ptyProcess, cwd, config } = session;

  if (!hasRequirementsTxt(cwd)) {
    sendNotification(ws, 'venv-status', {
      status: 'ready',
      message: 'No requirements.txt found — venv is ready',
    });
    return;
  }

  if (config.autoInstallDeps === 'never') {
    sendNotification(ws, 'venv-status', {
      status: 'ready',
      message: 'requirements.txt found but auto-install is disabled',
      hasRequirements: true,
    });
    return;
  }

  if (config.autoInstallDeps === 'ask') {
    sendNotification(ws, 'venv-status', {
      status: 'ask-install',
      message: 'requirements.txt found. Install dependencies?',
      hasRequirements: true,
    });
    return;
  }

  // autoInstallDeps === 'always'
  installRequirements(session);
}

function installRequirements(session) {
  const { ws, pty: ptyProcess } = session;

  sendNotification(ws, 'venv-status', {
    status: 'installing',
    message: 'Installing dependencies from requirements.txt...',
  });

  const installCmd = os.platform() === 'win32'
    ? `pip install -r requirements.txt\r`
    : `pip install -r requirements.txt\n`;

  ptyProcess.write(installCmd);

  // We can't easily detect when pip finishes in a pty, so we send a
  // notification and let the user see the output in the terminal.
  setTimeout(() => {
    sendNotification(ws, 'venv-status', {
      status: 'install-started',
      message: 'pip install running — check terminal output for progress',
    });
  }, 500);
}

// ── REST Endpoints ─────────────────────────────────────────────────
app.use(express.json());

// CORS
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok', activeSessions: sessions.size });
});

app.get('/sessions', (req, res) => {
  const list = [];
  for (const [id, s] of sessions) {
    list.push({
      terminalId: id,
      cwd: s.cwd,
      isVenvActive: s.isVenvActive,
      venvPath: s.venvPath,
      createdAt: s.createdAt,
    });
  }
  res.json({ sessions: list });
});

app.post('/install-requirements', (req, res) => {
  const { terminalId } = req.body;
  const session = sessions.get(terminalId);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  installRequirements(session);
  res.json({ status: 'installing' });
});

// ══════════════════════════════════════════════════════════════════════
// ── REAL FILESYSTEM API ──────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════

// Active workspace root — set when user opens a folder
let workspaceRoot = null;

const FS_EXCLUDED = new Set([
  'node_modules', '.git', '__pycache__', '.pytest_cache',
  '.coverage', 'venv', '.venv', 'env', '.DS_Store',
]);

function safePath(base, rel) {
  const resolved = path.resolve(base, rel);
  if (!resolved.startsWith(base)) {
    return null; // path traversal attempt
  }
  return resolved;
}

function getWorkspace(req) {
  const w = req.query.workspace || req.body?.workspace || workspaceRoot;
  if (!w) return null;
  return path.resolve(w);
}

// ── Set / Get workspace ──────────────────────────────────────────────
app.post('/fs/workspace', (req, res) => {
  const { path: wsPath } = req.body;
  if (!wsPath) return res.status(400).json({ error: 'path is required' });
  const resolved = path.resolve(wsPath);
  if (!fs.existsSync(resolved)) {
    return res.status(404).json({ error: 'Directory does not exist' });
  }
  workspaceRoot = resolved;
  console.log(`[FS] Workspace set to: ${resolved}`);
  res.json({ workspace: resolved });
});

app.get('/fs/workspace', (req, res) => {
  res.json({ workspace: workspaceRoot });
});

// ── Read file ────────────────────────────────────────────────────────
app.get('/fs/read', (req, res) => {
  const ws = getWorkspace(req);
  if (!ws) return res.status(400).json({ error: 'No workspace set' });
  const filePath = req.query.path;
  if (!filePath) return res.status(400).json({ error: 'path query param required' });

  const abs = safePath(ws, filePath);
  if (!abs) return res.status(403).json({ error: 'Path traversal denied' });
  if (!fs.existsSync(abs)) return res.status(404).json({ error: 'File not found' });

  try {
    const stat = fs.statSync(abs);
    if (stat.isDirectory()) return res.status(400).json({ error: 'Path is a directory' });
    // Skip large files (>5MB)
    if (stat.size > 5 * 1024 * 1024) {
      return res.status(413).json({ error: 'File too large (>5MB)' });
    }
    const content = fs.readFileSync(abs, 'utf-8');
    res.json({ success: true, path: filePath, content, size: stat.size });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── Write / Create file ──────────────────────────────────────────────
app.post('/fs/write', (req, res) => {
  const ws = getWorkspace(req);
  if (!ws) return res.status(400).json({ error: 'No workspace set' });
  const { path: filePath, content } = req.body;
  if (!filePath) return res.status(400).json({ error: 'path is required' });

  const abs = safePath(ws, filePath);
  if (!abs) return res.status(403).json({ error: 'Path traversal denied' });

  try {
    // Create parent directories if needed
    const dir = path.dirname(abs);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(abs, content || '', 'utf-8');
    console.log(`[FS] Written: ${filePath}`);
    res.json({ success: true, path: filePath });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── Delete file or directory ─────────────────────────────────────────
app.delete('/fs/delete', (req, res) => {
  const ws = getWorkspace(req);
  if (!ws) return res.status(400).json({ error: 'No workspace set' });
  const filePath = req.query.path || req.body?.path;
  if (!filePath) return res.status(400).json({ error: 'path is required' });

  const abs = safePath(ws, filePath);
  if (!abs) return res.status(403).json({ error: 'Path traversal denied' });
  if (!fs.existsSync(abs)) return res.status(404).json({ error: 'Not found' });

  try {
    const stat = fs.statSync(abs);
    if (stat.isDirectory()) {
      fs.rmSync(abs, { recursive: true, force: true });
    } else {
      fs.unlinkSync(abs);
    }
    console.log(`[FS] Deleted: ${filePath}`);
    res.json({ success: true, path: filePath });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── Rename / Move ────────────────────────────────────────────────────
app.post('/fs/rename', (req, res) => {
  const ws = getWorkspace(req);
  if (!ws) return res.status(400).json({ error: 'No workspace set' });
  const { oldPath, newPath } = req.body;
  if (!oldPath || !newPath) return res.status(400).json({ error: 'oldPath and newPath required' });

  const absOld = safePath(ws, oldPath);
  const absNew = safePath(ws, newPath);
  if (!absOld || !absNew) return res.status(403).json({ error: 'Path traversal denied' });
  if (!fs.existsSync(absOld)) return res.status(404).json({ error: 'Source not found' });

  try {
    const newDir = path.dirname(absNew);
    if (!fs.existsSync(newDir)) fs.mkdirSync(newDir, { recursive: true });
    fs.renameSync(absOld, absNew);
    console.log(`[FS] Renamed: ${oldPath} → ${newPath}`);
    res.json({ success: true, oldPath, newPath });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── Create directory ─────────────────────────────────────────────────
app.post('/fs/mkdir', (req, res) => {
  const ws = getWorkspace(req);
  if (!ws) return res.status(400).json({ error: 'No workspace set' });
  const { path: dirPath } = req.body;
  if (!dirPath) return res.status(400).json({ error: 'path is required' });

  const abs = safePath(ws, dirPath);
  if (!abs) return res.status(403).json({ error: 'Path traversal denied' });

  try {
    fs.mkdirSync(abs, { recursive: true });
    console.log(`[FS] Created dir: ${dirPath}`);
    res.json({ success: true, path: dirPath });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── List directory (flat) ────────────────────────────────────────────
app.get('/fs/list', (req, res) => {
  const ws = getWorkspace(req);
  if (!ws) return res.status(400).json({ error: 'No workspace set' });
  const dirPath = req.query.path || '.';

  const abs = safePath(ws, dirPath);
  if (!abs) return res.status(403).json({ error: 'Path traversal denied' });
  if (!fs.existsSync(abs)) return res.status(404).json({ error: 'Directory not found' });

  try {
    const entries = fs.readdirSync(abs, { withFileTypes: true });
    const items = entries
      .filter(e => !FS_EXCLUDED.has(e.name))
      .map(e => ({
        name: e.name,
        type: e.isDirectory() ? 'folder' : 'file',
        path: dirPath === '.' ? e.name : `${dirPath}/${e.name}`,
      }));
    res.json({ success: true, path: dirPath, items });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── Full tree (recursive) ────────────────────────────────────────────
app.get('/fs/tree', (req, res) => {
  const ws = getWorkspace(req);
  if (!ws) return res.status(400).json({ error: 'No workspace set' });
  const maxDepth = parseInt(req.query.depth) || 4;

  function buildTree(dirAbs, relPath, depth) {
    if (depth > maxDepth) return [];
    let entries;
    try { entries = fs.readdirSync(dirAbs, { withFileTypes: true }); }
    catch { return []; }

    const nodes = [];
    for (const e of entries) {
      if (FS_EXCLUDED.has(e.name)) continue;
      const childRel = relPath ? `${relPath}/${e.name}` : e.name;
      const childAbs = path.join(dirAbs, e.name);

      if (e.isDirectory()) {
        nodes.push({
          id: `dir_${childRel.replace(/[^a-zA-Z0-9]/g, '_')}`,
          name: e.name,
          type: 'folder',
          path: childRel,
          children: buildTree(childAbs, childRel, depth + 1),
        });
      } else {
        let size = 0;
        try { size = fs.statSync(childAbs).size; } catch {}
        nodes.push({
          id: `file_${childRel.replace(/[^a-zA-Z0-9]/g, '_')}`,
          name: e.name,
          type: 'file',
          path: childRel,
          size,
        });
      }
    }
    // Sort: folders first, then alphabetical
    nodes.sort((a, b) => {
      if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    return nodes;
  }

  try {
    const tree = buildTree(ws, '', 0);
    res.json({ success: true, workspace: ws, tree });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── Check if path exists ─────────────────────────────────────────────
app.get('/fs/exists', (req, res) => {
  const ws = getWorkspace(req);
  if (!ws) return res.status(400).json({ error: 'No workspace set' });
  const filePath = req.query.path;
  if (!filePath) return res.status(400).json({ error: 'path required' });

  const abs = safePath(ws, filePath);
  if (!abs) return res.status(403).json({ error: 'Path traversal denied' });

  const exists = fs.existsSync(abs);
  let type = null;
  if (exists) {
    const stat = fs.statSync(abs);
    type = stat.isDirectory() ? 'folder' : 'file';
  }
  res.json({ exists, type, path: filePath });
});

// ── Start Server with EADDRINUSE handling ──────────────────────────
function startServer(port) {
  server.listen(port, () => {
    console.log(`\n  🖥️  ETHOS Terminal Server running on http://localhost:${port}`);
    console.log(`  📡 WebSocket endpoint: ws://localhost:${port}`);
    console.log(`  💻 Platform: ${os.platform()} (${os.arch()})`);
    console.log(`  🐚 Shell: ${getShell().shell}\n`);
  });

  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.log(`\n  ⚠️  Port ${port} is already in use.`);
      console.log(`  🔄 Attempting to kill existing process on port ${port}...`);

      const { execSync } = require('child_process');
      try {
        if (os.platform() === 'win32') {
          // Find and kill process on the port (Windows)
          const result = execSync(`netstat -ano | findstr :${port} | findstr LISTENING`, { encoding: 'utf-8', timeout: 5000 });
          const lines = result.trim().split('\n');
          const pids = new Set();
          for (const line of lines) {
            const parts = line.trim().split(/\s+/);
            const pid = parts[parts.length - 1];
            if (pid && pid !== '0') pids.add(pid);
          }
          for (const pid of pids) {
            try { execSync(`taskkill /PID ${pid} /F`, { timeout: 5000 }); } catch { /* ignore */ }
          }
        } else {
          // Unix: use fuser or lsof
          try { execSync(`fuser -k ${port}/tcp`, { timeout: 5000 }); } catch {
            try { execSync(`lsof -ti:${port} | xargs kill -9`, { timeout: 5000 }); } catch { /* ignore */ }
          }
        }

        console.log(`  ✅ Killed existing process. Retrying in 1 second...\n`);
        setTimeout(() => {
          server.close();
          const newServer = http.createServer(app);
          const newWss = new WebSocket.Server({ server: newServer });
          // Re-attach WebSocket handler
          newWss.on('connection', wss._events.connection);
          newServer.listen(port, () => {
            console.log(`\n  🖥️  ETHOS Terminal Server running on http://localhost:${port}`);
            console.log(`  📡 WebSocket endpoint: ws://localhost:${port}`);
            console.log(`  💻 Platform: ${os.platform()} (${os.arch()})`);
            console.log(`  🐚 Shell: ${getShell().shell}\n`);
          });
          newServer.on('error', (retryErr) => {
            console.error(`\n  ❌ Failed to start server after retry: ${retryErr.message}`);
            console.log(`  💡 Manually kill the process: netstat -ano | findstr :${port}`);
            process.exit(1);
          });
        }, 1500);
      } catch (killErr) {
        console.error(`\n  ❌ Could not kill existing process: ${killErr.message}`);
        console.log(`  💡 Manually kill the process on port ${port}:`);
        if (os.platform() === 'win32') {
          console.log(`     netstat -ano | findstr :${port}`);
          console.log(`     taskkill /PID <PID> /F`);
        } else {
          console.log(`     lsof -ti:${port} | xargs kill -9`);
        }
        process.exit(1);
      }
    } else {
      console.error(`\n  ❌ Server error: ${err.message}`);
      process.exit(1);
    }
  });
}

startServer(PORT);
