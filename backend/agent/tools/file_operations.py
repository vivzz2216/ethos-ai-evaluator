"""
File operation tools for the AI agent.
Create, read, update, delete, rename, move files and directories.
"""
import os
import shutil
from typing import Optional

def _safe_path(workspace_root: str, file_path: str) -> str:
    """Resolve path and ensure it stays within workspace."""
    resolved = os.path.normpath(os.path.join(workspace_root, file_path))
    if not resolved.startswith(os.path.normpath(workspace_root)):
        raise PermissionError(f"Access denied: path '{file_path}' is outside workspace")
    return resolved


def read_file(workspace_root: str, file_path: str) -> dict:
    """Read contents of a file."""
    full = _safe_path(workspace_root, file_path)
    if not os.path.exists(full):
        return {"success": False, "error": f"File not found: {file_path}"}
    if not os.path.isfile(full):
        return {"success": False, "error": f"Not a file: {file_path}"}
    try:
        size = os.path.getsize(full)
        if size > 500_000:
            return {"success": False, "error": f"File too large ({size} bytes). Max 500KB."}
        with open(full, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return {"success": True, "path": file_path, "content": content, "size": size}
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_file(workspace_root: str, file_path: str, content: str) -> dict:
    """Create a new file with content. Creates parent directories if needed."""
    full = _safe_path(workspace_root, file_path)
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        already_exists = os.path.exists(full)
        with open(full, 'w', encoding='utf-8') as f:
            f.write(content)
        return {
            "success": True,
            "path": file_path,
            "action": "overwritten" if already_exists else "created",
            "size": len(content),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def edit_file(workspace_root: str, file_path: str, old_string: str, new_string: str) -> dict:
    """Replace a specific string in a file. old_string must be unique in the file."""
    full = _safe_path(workspace_root, file_path)
    if not os.path.isfile(full):
        return {"success": False, "error": f"File not found: {file_path}"}
    try:
        with open(full, 'r', encoding='utf-8') as f:
            content = f.read()
        count = content.count(old_string)
        if count == 0:
            return {"success": False, "error": "old_string not found in file"}
        if count > 1:
            return {"success": False, "error": f"old_string found {count} times — must be unique. Provide more context."}
        new_content = content.replace(old_string, new_string, 1)
        with open(full, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return {"success": True, "path": file_path, "replacements": 1}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_file(workspace_root: str, file_path: str) -> dict:
    """Delete a file or empty directory."""
    full = _safe_path(workspace_root, file_path)
    if not os.path.exists(full):
        return {"success": False, "error": f"Path not found: {file_path}"}
    try:
        if os.path.isfile(full):
            os.remove(full)
            return {"success": True, "path": file_path, "action": "deleted_file"}
        elif os.path.isdir(full):
            shutil.rmtree(full)
            return {"success": True, "path": file_path, "action": "deleted_directory"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def rename_file(workspace_root: str, old_path: str, new_path: str) -> dict:
    """Rename or move a file/directory."""
    full_old = _safe_path(workspace_root, old_path)
    full_new = _safe_path(workspace_root, new_path)
    if not os.path.exists(full_old):
        return {"success": False, "error": f"Source not found: {old_path}"}
    if os.path.exists(full_new):
        return {"success": False, "error": f"Destination already exists: {new_path}"}
    try:
        os.makedirs(os.path.dirname(full_new), exist_ok=True)
        shutil.move(full_old, full_new)
        return {"success": True, "old_path": old_path, "new_path": new_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


_LIST_IGNORE = {'.venv', 'venv', '.git', '__pycache__', '.pytest_cache',
                'node_modules', '.coverage', 'env', '.DS_Store', '.env'}

def list_directory(workspace_root: str, dir_path: str = '.') -> dict:
    """List files and directories in a path."""
    full = _safe_path(workspace_root, dir_path)
    if not os.path.isdir(full):
        return {"success": False, "error": f"Not a directory: {dir_path}"}
    try:
        entries = []
        for name in sorted(os.listdir(full)):
            if name in _LIST_IGNORE:
                continue
            entry_path = os.path.join(full, name)
            rel = os.path.relpath(entry_path, workspace_root).replace('\\', '/')
            if os.path.isdir(entry_path):
                entries.append({"name": name, "path": rel, "type": "directory"})
            else:
                entries.append({"name": name, "path": rel, "type": "file", "size": os.path.getsize(entry_path)})
        return {"success": True, "path": dir_path, "entries": entries}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_project_tree(workspace_root: str, max_depth: int = 3) -> dict:
    """Get a tree view of the project structure."""
    IGNORE = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env', '.env',
              'dist', 'build', '.next', '.cache', '.tox', 'eggs', '*.egg-info'}

    def walk(path, depth):
        if depth > max_depth:
            return None
        name = os.path.basename(path) or path
        if os.path.isfile(path):
            return {"name": name, "type": "file"}
        items = []
        try:
            for entry in sorted(os.listdir(path)):
                if entry in IGNORE or entry.startswith('.'):
                    continue
                child = walk(os.path.join(path, entry), depth + 1)
                if child:
                    items.append(child)
        except PermissionError:
            pass
        return {"name": name, "type": "directory", "children": items}

    tree = walk(workspace_root, 0)
    return {"success": True, "tree": tree}
