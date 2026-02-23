"""
Code analysis tools for the AI agent.
Analyze code structure, find definitions, understand projects.
"""
import os
import re
import json
from typing import List, Optional


def analyze_file(workspace_root: str, file_path: str) -> dict:
    """Analyze a code file and extract its structure (functions, classes, imports)."""
    full = os.path.normpath(os.path.join(workspace_root, file_path))
    if not os.path.isfile(full):
        return {"success": False, "error": f"File not found: {file_path}"}
    try:
        with open(full, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        return {"success": False, "error": str(e)}

    ext = os.path.splitext(file_path)[1].lower()
    lines = content.split('\n')
    result = {
        "success": True,
        "path": file_path,
        "lines": len(lines),
        "size": len(content),
        "language": _detect_language(ext),
        "imports": [],
        "functions": [],
        "classes": [],
        "exports": [],
    }

    if ext in ('.py',):
        result["imports"] = _extract_python_imports(lines)
        result["functions"] = _extract_python_functions(lines)
        result["classes"] = _extract_python_classes(lines)
    elif ext in ('.ts', '.tsx', '.js', '.jsx'):
        result["imports"] = _extract_js_imports(lines)
        result["functions"] = _extract_js_functions(lines)
        result["classes"] = _extract_js_classes(lines)
        result["exports"] = _extract_js_exports(lines)

    return result


def analyze_project(workspace_root: str) -> dict:
    """Analyze the overall project structure, tech stack, and dependencies."""
    info = {
        "success": True,
        "project_type": "unknown",
        "languages": [],
        "frameworks": [],
        "dependencies": {},
        "entry_points": [],
        "config_files": [],
    }

    # Check for package.json (Node.js)
    pkg_json = os.path.join(workspace_root, 'package.json')
    if os.path.exists(pkg_json):
        try:
            with open(pkg_json, 'r') as f:
                pkg = json.load(f)
            info["project_type"] = "node"
            info["languages"].append("javascript/typescript")
            deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
            info["dependencies"]["npm"] = list(deps.keys())[:50]
            if 'react' in deps:
                info["frameworks"].append("react")
            if 'next' in deps:
                info["frameworks"].append("nextjs")
            if 'vite' in deps or '@vitejs/plugin-react' in deps:
                info["frameworks"].append("vite")
            if 'express' in deps:
                info["frameworks"].append("express")
            scripts = pkg.get('scripts', {})
            info["entry_points"] = [f"npm run {k}" for k in scripts.keys()][:10]
        except Exception:
            pass

    # Check for requirements.txt / pyproject.toml (Python)
    req_txt = os.path.join(workspace_root, 'requirements.txt')
    pyproject = os.path.join(workspace_root, 'pyproject.toml')
    if os.path.exists(req_txt):
        info["languages"].append("python")
        try:
            with open(req_txt, 'r') as f:
                info["dependencies"]["pip"] = [l.strip().split('==')[0].split('>=')[0]
                                                for l in f if l.strip() and not l.startswith('#')][:50]
        except Exception:
            pass
    if os.path.exists(pyproject):
        info["languages"].append("python")
        info["config_files"].append("pyproject.toml")

    # Check for common config files
    for cfg in ['tsconfig.json', 'vite.config.ts', '.eslintrc', 'tailwind.config.js',
                'tailwind.config.ts', 'Dockerfile', 'docker-compose.yml', '.env.example',
                'Makefile', 'setup.py', 'setup.cfg']:
        if os.path.exists(os.path.join(workspace_root, cfg)):
            info["config_files"].append(cfg)

    # Detect backend frameworks
    app_py = os.path.join(workspace_root, 'backend', 'app.py')
    if os.path.exists(app_py):
        try:
            with open(app_py, 'r') as f:
                c = f.read(2000)
            if 'FastAPI' in c:
                info["frameworks"].append("fastapi")
            elif 'Flask' in c:
                info["frameworks"].append("flask")
            elif 'Django' in c:
                info["frameworks"].append("django")
        except Exception:
            pass

    return info


# ── Internal helpers ────────────────────────────────────────────────

def _detect_language(ext: str) -> str:
    return {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
        '.tsx': 'typescriptreact', '.jsx': 'javascriptreact',
        '.html': 'html', '.css': 'css', '.json': 'json',
        '.md': 'markdown', '.yaml': 'yaml', '.yml': 'yaml',
        '.sh': 'shell', '.bash': 'shell', '.sql': 'sql',
        '.rs': 'rust', '.go': 'go', '.java': 'java',
        '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.hpp': 'cpp',
    }.get(ext, 'plaintext')


def _extract_python_imports(lines: List[str]) -> List[dict]:
    results = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            results.append({"line": i + 1, "statement": stripped})
    return results[:30]


def _extract_python_functions(lines: List[str]) -> List[dict]:
    results = []
    for i, line in enumerate(lines):
        m = re.match(r'^(\s*)def\s+(\w+)\s*\(', line)
        if m:
            indent = len(m.group(1))
            results.append({"name": m.group(2), "line": i + 1, "indent": indent})
    return results[:50]


def _extract_python_classes(lines: List[str]) -> List[dict]:
    results = []
    for i, line in enumerate(lines):
        m = re.match(r'^class\s+(\w+)', line)
        if m:
            results.append({"name": m.group(1), "line": i + 1})
    return results[:30]


def _extract_js_imports(lines: List[str]) -> List[dict]:
    results = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('import ') or (stripped.startswith('const ') and 'require(' in stripped):
            results.append({"line": i + 1, "statement": stripped[:150]})
    return results[:30]


def _extract_js_functions(lines: List[str]) -> List[dict]:
    results = []
    for i, line in enumerate(lines):
        # function declarations
        m = re.match(r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)', line)
        if m:
            results.append({"name": m.group(1), "line": i + 1})
            continue
        # arrow functions assigned to const/let/var
        m = re.match(r'^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(', line)
        if m:
            results.append({"name": m.group(1), "line": i + 1})
    return results[:50]


def _extract_js_classes(lines: List[str]) -> List[dict]:
    results = []
    for i, line in enumerate(lines):
        m = re.match(r'^\s*(?:export\s+)?class\s+(\w+)', line)
        if m:
            results.append({"name": m.group(1), "line": i + 1})
    return results[:30]


def _extract_js_exports(lines: List[str]) -> List[dict]:
    results = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('export '):
            results.append({"line": i + 1, "statement": stripped[:150]})
    return results[:30]
