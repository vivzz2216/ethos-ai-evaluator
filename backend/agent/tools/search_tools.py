"""
Search tools for the AI agent.
Grep patterns, find files by name/extension, search code.
"""
import os
import re
import fnmatch
from typing import List, Optional


def grep_search(workspace_root: str, pattern: str, file_glob: str = '*', max_results: int = 50) -> dict:
    """Search for a regex/text pattern across files in the workspace."""
    IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.next', '.cache'}
    results = []
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        regex = re.compile(re.escape(pattern), re.IGNORECASE)

    for root, dirs, files in os.walk(workspace_root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        for fname in files:
            if not fnmatch.fnmatch(fname, file_glob):
                continue
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, workspace_root).replace('\\', '/')
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append({
                                "file": rel,
                                "line": i,
                                "content": line.rstrip()[:200],
                            })
                            if len(results) >= max_results:
                                return {"success": True, "matches": results, "truncated": True}
            except (PermissionError, OSError):
                continue
    return {"success": True, "matches": results, "truncated": False}


def find_files(workspace_root: str, pattern: str = '*', file_type: str = 'any', max_depth: int = 10) -> dict:
    """Find files/directories matching a glob pattern."""
    IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.next', '.cache'}
    results = []
    for root, dirs, files in os.walk(workspace_root):
        depth = root.replace(workspace_root, '').count(os.sep)
        if depth >= max_depth:
            dirs.clear()
            continue
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        if file_type in ('any', 'directory'):
            for d in dirs:
                if fnmatch.fnmatch(d, pattern):
                    rel = os.path.relpath(os.path.join(root, d), workspace_root).replace('\\', '/')
                    results.append({"name": d, "path": rel, "type": "directory"})
        if file_type in ('any', 'file'):
            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    fpath = os.path.join(root, f)
                    rel = os.path.relpath(fpath, workspace_root).replace('\\', '/')
                    results.append({"name": f, "path": rel, "type": "file", "size": os.path.getsize(fpath)})
        if len(results) >= 100:
            break
    return {"success": True, "results": results[:100]}


def find_by_extension(workspace_root: str, extensions: List[str]) -> dict:
    """Find all files with given extensions (e.g., ['py', 'ts', 'tsx'])."""
    ext_set = set('.' + e.lstrip('.') for e in extensions)
    return find_files(workspace_root, pattern='*', file_type='file')
    # Filter by extension after
    IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build'}
    results = []
    for root, dirs, files in os.walk(workspace_root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        for f in files:
            if os.path.splitext(f)[1] in ext_set:
                fpath = os.path.join(root, f)
                rel = os.path.relpath(fpath, workspace_root).replace('\\', '/')
                results.append({"name": f, "path": rel, "size": os.path.getsize(fpath)})
                if len(results) >= 100:
                    return {"success": True, "files": results}
    return {"success": True, "files": results}
