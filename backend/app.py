from fastapi import FastAPI, HTTPException, UploadFile, File, Form  # pyright: ignore[reportMissingImports]  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # pyright: ignore[reportMissingImports]  # type: ignore
from fastapi.responses import JSONResponse, StreamingResponse  # pyright: ignore[reportMissingImports]  # type: ignore

# Load .env file so REMOTE_MODEL_URL and other config is available
try:
    from dotenv import load_dotenv  # pyright: ignore[reportMissingImports]  # type: ignore
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, rely on system env vars

# Include ETHOS testing router
try:
    import sys
    sys.path.insert(0, '.')
    sys.path.insert(0, '..')
    from ethos_testing.api import router as ethos_router
except Exception as e:
    print(f"Failed to import ETHOS router: {e}")
    ethos_router = None
import io
import tempfile
import os
import shutil
import subprocess
import uuid
import time
import threading
from typing import List, Optional, Dict
import uvicorn  # pyright: ignore[reportMissingImports]  # type: ignore
import sys

app = FastAPI()

# CORS middleware
# Define allowed origins including development ports
allowed_origins = [f"http://localhost:{port}" for port in range(3000, 3010)]  # Covers ports 3000-3009
allowed_origins.extend([
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080"
])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex="http://(localhost|127\\.0\\.0\\.1):[0-9]+"  # Allow localhost and 127.0.0.1 on any port
)

# Mount ETHOS testing routes if available
if ethos_router is not None:
    app.include_router(ethos_router)
    print("ETHOS testing routes mounted successfully")
else:
    print("Warning: ETHOS testing router not available")

# Mount AI Agent routes
try:
    from agent.api import router as agent_router
    from agent.config import config as agent_config
    app.include_router(agent_router)
    # Set default workspace to the main project root (parent of backend/)
    if not agent_config.workspace_root:
        agent_config.workspace_root = os.path.dirname(os.getcwd())
    print(f"AI Agent routes mounted successfully (workspace: {agent_config.workspace_root})")
except Exception as e:
    print(f"Warning: AI Agent router not available: {e}")

# Global variables
active_sessions: Dict[str, Dict] = {}
running_processes: Dict[str, subprocess.Popen] = {}
terminal_sessions: Dict[str, subprocess.Popen] = {}

# File filtering constants
ALLOWED_EXTENSIONS = {
    # Code / text
    '.py', '.txt', '.json', '.yml', '.yaml', '.ini', '.cfg', '.toml',
    '.md', '.rst', '.html', '.htm', '.css', '.scss', '.less',
    '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs',
    '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rs', '.rb',
    '.sh', '.bash', '.bat', '.ps1', '.cmd',
    '.xml', '.csv', '.sql', '.graphql', '.prisma',
    '.env', '.env.example', '.env.local',
    '.gitignore', '.dockerignore', '.editorconfig',
    '.dockerfile', '.lock', '.log',
    '.svg', '.r', '.lua', '.php', '.swift', '.kt',
    # Model weight files (CRITICAL — must not be dropped)
    '.safetensors', '.bin', '.pt', '.pth', '.onnx', '.tflite',
    '.h5', '.hdf5', '.pkl', '.pickle', '.msgpack', '.pb',
    '.gguf', '.ggml', '.ckpt', '.mar', '.params',
    # Model config files
    '.model', '.vocab', '.spiece', '.sentencepiece',
}

# Binary file extensions that should be streamed, never read into memory
BINARY_EXTENSIONS = {
    '.safetensors', '.bin', '.pt', '.pth', '.onnx', '.tflite',
    '.h5', '.hdf5', '.pkl', '.pickle', '.msgpack', '.pb',
    '.gguf', '.ggml', '.ckpt', '.mar', '.params',
    '.model', '.spiece', '.sentencepiece',
}
EXCLUDED_DIRS = {'node_modules', '.git', '__pycache__', '.pytest_cache', '.coverage', 'venv', '.venv', 'env', '.env'}
MAX_FILES_LIMIT = 1000

def should_include_file(filename: str) -> bool:
    """Check if a file should be included in upload"""
    for excluded_dir in EXCLUDED_DIRS:
        if excluded_dir in filename.replace('\\', '/'):
            return False
    _, ext = os.path.splitext(filename.lower())
    if filename.lower() == 'requirements.txt':
        return True
    return ext in ALLOWED_EXTENSIONS

@app.on_event("startup")
async def startup_event():
    print("ETHOS Backend Server Starting...")

@app.on_event("shutdown")
async def shutdown_event():
    print("ETHOS Backend Server Shutting Down...")
    # Clean up all running processes
    for session_id, process in running_processes.items():
        try:
            if os.name == 'nt':  # Windows
                process.terminate()
            else:  # Unix/Linux/Mac
                process.terminate()
        except:
            pass
    
    # Clean up terminal sessions
    for session_id, process in terminal_sessions.items():
        try:
            if os.name == 'nt':  # Windows
                process.terminate()
            else:  # Unix/Linux/Mac
                process.terminate()
        except:
            pass

@app.get("/")
async def root():
    return {"message": "ETHOS Backend API", "docs": "/docs", "health": "/api/health"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "message": "ETHOS Backend is running"}

@app.post("/api/session/create")
async def create_session():
    """Create a new session with virtual environment"""
    session_id = str(uuid.uuid4())
    
    # Create persistent project directory (like VS Code workspace)
    project_dir = os.path.join(os.getcwd(), 'projects', f"project_{session_id}")
    os.makedirs(project_dir, exist_ok=True)
    
    try:
        # Create virtual environment in project directory (like VS Code)
        venv_path = os.path.join(project_dir, '.venv')
        
        # Try to create virtual environment with better error handling
        try:
            subprocess.run([sys.executable, '-m', 'venv', venv_path], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"Virtual environment creation failed: {e}")
            print(f"Error output: {e.stderr}")
            # Try alternative approach
            subprocess.run(['python', '-m', 'venv', venv_path], check=True, capture_output=True, text=True)
        
        # Get Python and pip executables
        if os.name == 'nt':  # Windows
            python_exe = os.path.join(venv_path, 'Scripts', 'python.exe')
            pip_exe = os.path.join(venv_path, 'Scripts', 'pip.exe')
        else:  # Unix/Linux/Mac
            python_exe = os.path.join(venv_path, 'bin', 'python')
            pip_exe = os.path.join(venv_path, 'bin', 'pip')
        
        # Store session data
        session_data = {
            'project_dir': project_dir,  # Changed from project_dir to project_dir
            'venv_path': venv_path,
            'python_exe': python_exe,
            'pip_exe': pip_exe,
            'is_running': False,
            'port': None,
            'venv_activated': True  # Track virtual environment state
        }
        
        active_sessions[session_id] = session_data
        
        return {"session_id": session_id, "message": "Session created successfully", "project_dir": project_dir}
        
    except Exception as e:
        # Clean up on error
        if os.path.exists(project_dir):
            shutil.rmtree(project_dir)
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

@app.post("/api/session/{session_id}/upload")
async def upload_files(session_id: str, files: List[UploadFile] = File(...)):
    """Upload files to session directory"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = active_sessions[session_id]
    project_dir = session_data['project_dir']
    
    # Filter files based on our criteria
    filtered_files = [f for f in files if should_include_file(f.filename)]
    
    if len(filtered_files) > MAX_FILES_LIMIT:
        raise HTTPException(
            status_code=400, 
            detail="Too many files. Maximum number of files is 1000. Please either upload fewer files or split your upload into chunks of ≤1000 files."
        )
    
    if len(filtered_files) == 0:
        raise HTTPException(status_code=400, detail="No valid files to upload. Please upload Python files (.py), requirements.txt, or config files (.json, .yml, .yaml, .ini).")
    
    uploaded_files = []
    uploaded_sizes = {}
    framework_detected = None
    main_file = None
    
    try:
        for file in filtered_files:
            # Create directory structure if needed
            file_path = os.path.join(project_dir, file.filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Determine if this is a binary/large file
            _, ext = os.path.splitext(file.filename.lower())
            is_binary = ext in BINARY_EXTENSIONS
            
            # Save file using streaming (constant memory, works for multi-GB files)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            saved_size = os.path.getsize(file_path)
            uploaded_files.append(file.filename)
            uploaded_sizes[file.filename] = saved_size
            size_str = f"{saved_size / (1024*1024):.1f} MB" if saved_size > 1024*1024 else f"{saved_size / 1024:.1f} KB"
            print(f"Saved: {file.filename} ({size_str}){' [binary]' if is_binary else ''}")
            
            # Detect framework (text files only)
            if file.filename.endswith('.py') and not is_binary:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        py_content = f.read(8192)  # Only read first 8KB for detection
                        if 'from flask import' in py_content or 'import flask' in py_content:
                            framework_detected = 'flask'
                            main_file = file.filename
                        elif 'from fastapi import' in py_content or 'import fastapi' in py_content:
                            framework_detected = 'fastapi'
                            main_file = file.filename
                        elif 'from django' in py_content or 'import django' in py_content:
                            framework_detected = 'django'
                            main_file = file.filename
                except Exception:
                    pass  # Skip framework detection on read error
        
        # Install requirements if present
        requirements_path = os.path.join(project_dir, 'requirements.txt')
        installed_packages = []
        
        if os.path.exists(requirements_path):
            try:
                pip_exe = session_data['pip_exe']
                result = subprocess.run([pip_exe, 'install', '-r', 'requirements.txt'], 
                                      capture_output=True, text=True, cwd=project_dir, timeout=120)
                if result.returncode == 0:
                    # Parse installed packages from output
                    for line in result.stdout.split('\n'):
                        if 'Successfully installed' in line:
                            installed_packages = line.split('Successfully installed ')[1].split()
                else:
                    print(f"Failed to install requirements: {result.stderr}")
            except subprocess.TimeoutExpired:
                print("Requirements installation timed out")
            except Exception as e:
                print(f"Error installing requirements: {e}")
        
        print(f"Upload successful. Framework detected: {framework_detected}")
        
        total_size = sum(uploaded_sizes.values())
        total_size_mb = round(total_size / (1024 * 1024), 2)
        print(f"Upload complete: {len(uploaded_files)} files, {total_size_mb} MB total")
        
        return {
            "message": "Files uploaded successfully",
            "uploaded_files": uploaded_files,
            "uploaded_sizes": uploaded_sizes,
            "total_size_mb": total_size_mb,
            "framework_detected": framework_detected,
            "main_file": main_file,
            "installed_packages": installed_packages,
            "project_dir": project_dir,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/api/session/{session_id}/link-local")
async def link_local_model(session_id: str, local_path: str = Form(...)):
    """
    Link a local model directory into the session project.
    Bypasses browser upload entirely — copies/symlinks files from a local path.
    Use this for large models (multi-GB .safetensors, .gguf, etc.) that can't
    go through the browser's FormData upload.
    """
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # Resolve and validate the source path
    source = os.path.abspath(local_path)
    if not os.path.exists(source):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {source}")

    project_dir = active_sessions[session_id]['project_dir']

    try:
        linked_files = []
        total_size = 0

        if os.path.isfile(source):
            # Single file — copy into project root
            dest = os.path.join(project_dir, os.path.basename(source))
            shutil.copy2(source, dest)
            sz = os.path.getsize(dest)
            linked_files.append(os.path.basename(source))
            total_size += sz
            print(f"Linked file: {os.path.basename(source)} ({sz/(1024*1024):.1f} MB)")

        elif os.path.isdir(source):
            # Directory — copy entire tree into project
            dir_name = os.path.basename(source.rstrip('/\\'))
            dest_dir = os.path.join(project_dir, dir_name)

            if os.path.exists(dest_dir):
                shutil.rmtree(dest_dir)

            # Use shutil.copytree but skip .git and .venv
            def ignore_fn(directory, contents):
                return [c for c in contents if c in {'.git', '.venv', 'venv', '__pycache__', 'node_modules'}]

            shutil.copytree(source, dest_dir, ignore=ignore_fn)

            # Enumerate what we copied
            for root, dirs, files in os.walk(dest_dir):
                dirs[:] = [d for d in dirs if d not in {'.git', '.venv', 'venv', '__pycache__'}]
                for fname in files:
                    fpath = os.path.join(root, fname)
                    rel = os.path.relpath(fpath, project_dir).replace("\\", "/")
                    sz = os.path.getsize(fpath)
                    linked_files.append(rel)
                    total_size += sz

            print(f"Linked directory: {dir_name} ({len(linked_files)} files, {total_size/(1024*1024):.1f} MB)")
        else:
            raise HTTPException(status_code=400, detail=f"Path is not a file or directory: {source}")

        total_mb = round(total_size / (1024 * 1024), 2)
        return {
            "message": f"Linked {len(linked_files)} files from local path",
            "source_path": source,
            "linked_files": linked_files,
            "file_count": len(linked_files),
            "total_size_mb": total_mb,
            "project_dir": project_dir,
        }

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"Permission denied: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Link failed: {str(e)}")

@app.get("/api/session/{session_id}/verify-upload")
async def verify_upload(session_id: str):
    """Verify uploaded files exist and report their sizes. Use after upload to confirm large binaries landed."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    project_dir = active_sessions[session_id]['project_dir']
    file_report = []
    total_size = 0
    missing_weights = False
    
    for root, dirs, filenames in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in {'.venv', 'venv', '__pycache__'}]
        for fname in filenames:
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, project_dir).replace("\\", "/")
            try:
                size = os.path.getsize(fpath)
            except OSError:
                size = 0
            total_size += size
            _, ext = os.path.splitext(fname.lower())
            is_weight = ext in BINARY_EXTENSIONS
            file_report.append({
                "path": rel,
                "size": size,
                "size_mb": round(size / (1024 * 1024), 2),
                "is_weight_file": is_weight,
            })
            # Flag if a weight file is suspiciously small (< 1 KB = likely pointer/stub)
            if is_weight and size < 1024:
                missing_weights = True
    
    return {
        "session_id": session_id,
        "project_dir": project_dir,
        "file_count": len(file_report),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "missing_weights": missing_weights,
        "files": file_report,
    }

@app.post("/api/session/{session_id}/run-server")
async def run_server(session_id: str, port: int = 5000):
    """Start a development server for the uploaded application"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = active_sessions[session_id]
    project_dir = session_data['project_dir']
    
    # Check if server is already running
    if session_data.get('is_running', False):
        return {
            "message": "Server is already running",
            "port": session_data['port'],
            "url": f"http://localhost:{session_data['port']}",
            "status": "running"
        }
    
    # Detect framework and main file
    framework = None
    main_file = None
    
    for filename in os.listdir(project_dir):
        if filename.endswith('.py'):
            file_path = os.path.join(project_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'from flask import' in content or 'import flask' in content:
                        framework = 'flask'
                        main_file = filename
                        break
                    elif 'from fastapi import' in content or 'import fastapi' in content:
                        framework = 'fastapi'
                        main_file = filename
                        break
                    elif 'from django' in content or 'import django' in content:
                        framework = 'django'
                        main_file = filename
                        break
            except:
                continue
    
    if not framework:
        raise HTTPException(status_code=400, detail="No supported framework detected")
    
    try:
        python_exe = session_data['python_exe']
        
        # Prepare environment
        env = os.environ.copy()
        env['PYTHONPATH'] = project_dir
        
        # Start server based on framework
        if framework == 'flask':
            # Set Flask environment variables
            env['FLASK_APP'] = main_file
            env['FLASK_ENV'] = 'development'
            env['FLASK_DEBUG'] = '1'
            
            process = subprocess.Popen([
                python_exe, '-m', 'flask', 'run', '--host=0.0.0.0', f'--port={port}'
            ], 
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            preexec_fn=None if os.name == 'nt' else os.setsid
        )
        
        elif framework == 'fastapi':
            # For FastAPI, we need to run uvicorn
            module_name = main_file.replace('.py', '')
            process = subprocess.Popen([
                python_exe, '-m', 'uvicorn', f'{module_name}:app', '--host', '0.0.0.0', f'--port', str(port)
            ],
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            preexec_fn=None if os.name == 'nt' else os.setsid
        )
        
        elif framework == 'django':
            process = subprocess.Popen([
                python_exe, 'manage.py', 'runserver', f'0.0.0.0:{port}'
            ],
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            preexec_fn=None if os.name == 'nt' else os.setsid
        )
        
        running_processes[session_id] = process
        session_data['is_running'] = True
        session_data['port'] = port
        
        # Wait a moment to check if server started successfully
        time.sleep(2)
        
        if process.poll() is None:  # Process is still running
            return {
                "message": f"{framework.title()} server started successfully",
                "framework": framework,
                "port": port,
                "url": f"http://localhost:{port}",
                "status": "running"
            }
        else:
            # Process exited, get error
            stdout, stderr = process.communicate()
            session_data['is_running'] = False
            if session_id in running_processes:
                del running_processes[session_id]
            
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to start server: {stderr}"
            )
            
    except Exception as e:
        session_data['is_running'] = False
        if session_id in running_processes:
            del running_processes[session_id]
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/session/{session_id}/stop-server")
async def stop_server(session_id: str):
    """Stop the running server"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = active_sessions[session_id]
    
    if session_id in running_processes:
        process = running_processes[session_id]
        try:
            if os.name == 'nt':  # Windows
                process.terminate()
            else:  # Unix/Linux/Mac
                process.terminate()
            
            # Wait for process to terminate
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            
            del running_processes[session_id]
            session_data['is_running'] = False
            session_data['port'] = None
            
            return {"message": "Server stopped successfully", "status": "stopped"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop server: {str(e)}")

    
    return {"message": "No server running", "status": "stopped"}

@app.post("/api/session/{session_id}/execute-command")
async def execute_command(
    session_id: str,
    command: str = Form(...),
    working_dir: Optional[str] = Form(None)
):
    
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = active_sessions[session_id]
    project_dir = session_data['project_dir']
    python_exe = session_data['python_exe']
    pip_exe = session_data['pip_exe']
    
    # Use specified working directory or session project directory
    cwd = working_dir if working_dir and os.path.exists(working_dir) else project_dir
    
    try:
        # Parse command into arguments
        import shlex
        cmd_args = shlex.split(command)
        
        # Handle virtual environment commands
        if cmd_args[0] == 'python' and len(cmd_args) > 2 and cmd_args[1] == '-m' and cmd_args[2] == 'venv':
            # Create virtual environment
            venv_name = cmd_args[3] if len(cmd_args) > 3 else 'venv'
            venv_path = os.path.join(cwd, venv_name)
            
            result = subprocess.run([
                sys.executable, '-m', 'venv', venv_path
            ], capture_output=True, text=True, cwd=cwd)
            
            return {
                "command": command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0,
                "working_dir": cwd
            }
        
        # Handle Python commands - use virtual environment Python
        elif cmd_args[0] == 'python':
            # Use the virtual environment Python executable
            result = subprocess.run([python_exe] + cmd_args[1:], capture_output=True, text=True, timeout=30, cwd=cwd)
            
            return {
                "command": command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0,
                "working_dir": cwd
            }
        
        # Handle pip install commands with debugging
        elif cmd_args[0] == 'pip' and len(cmd_args) > 1 and cmd_args[1] == 'install':
            if '-r' in cmd_args and 'requirements.txt' in cmd_args:
                if os.name == 'nt':  # Windows
                    list_result = subprocess.run(['dir'], capture_output=True, text=True, cwd=cwd, shell=True)
                else:  # Unix/Linux/Mac
                    list_result = subprocess.run(['ls', '-la'], capture_output=True, text=True, cwd=cwd)
                print(f"Files in {cwd}: {list_result.stdout}")
                req_path = os.path.join(cwd, 'requirements.txt')
                if os.path.exists(req_path):
                    print(f"requirements.txt found at: {req_path}")
                else:
                    print(f"requirements.txt NOT found at: {req_path}")
                    try:
                        txt_files = [f for f in os.listdir(cwd) if f.endswith('.txt')]
                        print(f"Available .txt files: {txt_files}")
                    except Exception as e:
                        print(f"Error listing files: {e}")
            result = subprocess.run([pip_exe] + cmd_args[1:], capture_output=True, text=True, timeout=120, cwd=cwd)
            
            return {
                "command": command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0,
                "working_dir": cwd
            }
        
        # Handle run-server command
        elif command == 'run-server':
            return await run_server(session_id, 5000)
        
        # Handle Flask commands
        elif cmd_args[0] == 'flask':
            # Check if it's a 'run' command
            if len(cmd_args) > 1 and cmd_args[1] == 'run':
                # Use the existing run_server function for Flask
                return await run_server(session_id, 5000)
            else:
                # Handle other Flask commands (like flask --help, flask routes, etc.)
                python_exe = session_data['python_exe']
                
                # Auto-detect Flask app if not specified
                flask_env = os.environ.copy()
                
                # Check if FLASK_APP is not set and app.py exists
                if 'FLASK_APP' not in flask_env and os.path.exists(os.path.join(cwd, 'app.py')):
                    flask_env['FLASK_APP'] = 'app.py'
                    print(f"Auto-detected Flask app: app.py")
                
                # Check for other common Flask app names
                if 'FLASK_APP' not in flask_env:
                    for app_name in ['main.py', 'application.py', 'server.py']:
                        if os.path.exists(os.path.join(cwd, app_name)):
                            flask_env['FLASK_APP'] = app_name
                            print(f"Auto-detected Flask app: {app_name}")
                            break
                
                # Set development environment if not set
                if 'FLASK_ENV' not in flask_env:
                    flask_env['FLASK_ENV'] = 'development'
                
                # Use timeout for non-run Flask commands
                result = subprocess.run([
                    python_exe, '-m', 'flask'] + cmd_args[1:], 
                    capture_output=True, text=True, timeout=30, cwd=cwd, env=flask_env
                )
            
            return {
                "command": command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0,
                "working_dir": cwd
            }
        
        # Handle other commands (ls, dir, cd, etc.)
        else:
            # Use shell=True for Windows to handle commands properly
            use_shell = os.name == 'nt'
            
            # Special handling for Windows environment variable setting
            if os.name == 'nt' and command.startswith('set '):
                # Extract variable name and value
                parts = command.split(' ', 2)
                if len(parts) >= 3:
                    var_name = parts[1]
                    var_value = parts[2]
                    # Set environment variable in the current process
                    os.environ[var_name] = var_value
                return {
                    "command": command,
                    "stdout": f"Environment variable {var_name} set to {var_value}\n",
                    "stderr": "",
                    "returncode": 0,
                    "success": True,
                    "working_dir": cwd
                }
            
            result = subprocess.run(
                command if use_shell else cmd_args, 
                capture_output=True, text=True, timeout=30, cwd=cwd, shell=use_shell
            )
            
            return {
                "command": command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0,
                "working_dir": cwd
            }
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Command timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/session/{session_id}/execute")
async def execute_code(
    session_id: str,
    filename: str = Form(...),
    code: Optional[str] = Form(None)
):
    """Execute Python code in the session's virtual environment"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = active_sessions[session_id]
    python_exe = session_data['python_exe']
    project_dir = session_data['project_dir']
    
    try:
        file_path = os.path.join(project_dir, filename)
        
        # If code is provided, write it to file
        if code:
            with open(file_path, 'w') as f:
                f.write(code)
        
        # Execute the Python file
        result = subprocess.run([
            python_exe, file_path
        ], capture_output=True, text=True, timeout=30, cwd=project_dir)
        
        return {
            "filename": filename,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0
        }
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Code execution timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/session/{session_id}/status")
async def get_session_status(session_id: str):
    """Get session and server status"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = active_sessions[session_id]
    
    # Check if server process is still running
    is_running = session_data.get('is_running', False)
    if is_running and session_id in running_processes:
        process = running_processes[session_id]
        if process.poll() is not None:  # Process has terminated
            is_running = False
            session_data['is_running'] = False
            session_data['port'] = None
            del running_processes[session_id]
    
    return {
        "session_id": session_id,
        "is_running": is_running,
        "port": session_data.get('port'),
        "url": f"http://localhost:{session_data['port']}" if session_data.get('port') else None,
        "venv_activated": session_data.get('venv_activated', False)
    }

@app.get("/api/session/{session_id}/debug/files")
async def debug_session_files(session_id: str):
    """Debug endpoint to list all files in session directory"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = active_sessions[session_id]
    project_dir = session_data['project_dir']
    
    files = []
    
    def list_files_recursive(directory, prefix=""):
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                relative_path = os.path.join(prefix, item) if prefix else item
                
                if os.path.isfile(item_path):
                    files.append({
                        "name": item,
                        "path": relative_path,
                        "type": "file",
                        "size": os.path.getsize(item_path)
                    })
                elif os.path.isdir(item_path):
                    files.append({
                        "name": item,
                        "path": relative_path,
                        "type": "directory"
                    })
                    list_files_recursive(item_path, relative_path)
        except PermissionError:
            pass
    
    list_files_recursive(project_dir)
    
    return {
        "session_id": session_id,
        "project_dir": project_dir,
        "files": files
    }

@app.get("/api/session/{session_id}/file/{filename}")
async def get_session_file(session_id: str, filename: str):
    """Get content of a specific file in the session directory"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = active_sessions[session_id]
    project_dir = session_data['project_dir']
    file_path = os.path.join(project_dir, filename)
    
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            "filename": filename,
            "content": content,
            "size": os.path.getsize(file_path)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

@app.get("/api/debug/sessions")
async def debug_sessions():
    """Debug endpoint to list all active sessions"""
    return {
        "active_sessions": list(active_sessions.keys()),
        "running_processes": list(running_processes.keys()),
        "terminal_sessions": list(terminal_sessions.keys())
    }

@app.post("/api/session/{session_id}/terminal/start")
async def start_terminal(session_id: str):
    """Start a persistent terminal session (like VS Code integrated terminal)"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_id in terminal_sessions:
        return {"message": "Terminal already started", "status": "running"}
    
    session_data = active_sessions[session_id]
    project_dir = session_data['project_dir']
    
    try:
        if os.name == 'nt':  # Windows
            # Use PowerShell for Windows (like VS Code)
            process = subprocess.Popen(
                ['powershell.exe', '-NoExit', '-Command', f'cd "{project_dir}"'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=project_dir,
                bufsize=0,
                creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0
            )
        else:  # Unix/Linux/Mac
            # Use bash for Unix-like systems
            process = subprocess.Popen(
                ['bash'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=project_dir,
                bufsize=0
            )
        
        terminal_sessions[session_id] = process
        
        return {
            "message": "Terminal started successfully", 
            "status": "started",
            "project_dir": project_dir,
            "terminal_type": "powershell" if os.name == 'nt' else "bash"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start terminal: {str(e)}")

@app.post("/api/session/{session_id}/terminal/execute")
async def execute_terminal_command(session_id: str, command: str = Form(...)):
    """Execute command in the terminal session (like VS Code integrated terminal)"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = active_sessions[session_id]
    project_dir = session_data['project_dir']
    python_exe = session_data['python_exe']
    pip_exe = session_data['pip_exe']
    
    try:
        # Handle special commands that need virtual environment
        if command.strip() == 'run-server':
            return await run_server(session_id, 5000)
        
        # Handle Python commands - use virtual environment Python
        if command.strip().startswith('python '):
            # Replace 'python' with the virtual environment Python executable
            cmd_parts = command.split(' ', 1)
            if len(cmd_parts) > 1:
                new_command = f"{python_exe} {cmd_parts[1]}"
            else:
                new_command = python_exe
            
            if os.name == 'nt':  # Windows PowerShell
                result = subprocess.run(
                    ['powershell.exe', '-Command', new_command],
                    capture_output=True,
                    text=True,
                    cwd=project_dir,
                    timeout=30,
                    shell=False
                )
            else:  # Unix/Linux/Mac
                result = subprocess.run(
                    new_command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=project_dir,
                    timeout=30
                )
        
        # Handle pip commands - use virtual environment pip
        elif command.strip().startswith('pip '):
            # Replace 'pip' with the virtual environment pip executable
            cmd_parts = command.split(' ', 1)
            if len(cmd_parts) > 1:
                new_command = f"{pip_exe} {cmd_parts[1]}"
            else:
                new_command = pip_exe
            
            if os.name == 'nt':  # Windows PowerShell
                result = subprocess.run(
                    ['powershell.exe', '-Command', new_command],
                    capture_output=True,
                    text=True,
                    cwd=project_dir,
                    timeout=120,  # Longer timeout for pip installs
                    shell=False
                )
            else:  # Unix/Linux/Mac
                result = subprocess.run(
                    new_command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=project_dir,
                    timeout=120
                )
        
        # Handle other commands normally
        else:
            if os.name == 'nt':  # Windows PowerShell
                result = subprocess.run(
                    ['powershell.exe', '-Command', command],
                    capture_output=True,
                    text=True,
                    cwd=project_dir,
                    timeout=30,
                    shell=False
                )
            else:  # Unix/Linux/Mac
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=project_dir,
                    timeout=30
                )
        
        return {
            "command": command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0,
            "working_dir": project_dir,
            "python_exe": python_exe,
            "pip_exe": pip_exe
        }
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Command timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute command: {str(e)}")

@app.post("/api/session/{session_id}/terminal/stop")
async def stop_terminal(session_id: str):
    """Stop the terminal session"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_id not in terminal_sessions:
        raise HTTPException(status_code=404, detail="Terminal session not found")
    
    process = terminal_sessions[session_id]
    
    try:
        if os.name == 'nt':  # Windows
            process.terminate()
        else:  # Unix/Linux/Mac
            process.terminate()
        
        del terminal_sessions[session_id]
        
        return {"message": "Terminal stopped successfully", "status": "stopped"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop terminal: {str(e)}")

@app.get("/api/session/{session_id}/terminal/pwd")
async def get_current_directory(session_id: str):
    """Get current working directory (like VS Code terminal)"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = active_sessions[session_id]
    project_dir = session_data['project_dir']
    
    return {
        "current_dir": project_dir,
        "project_dir": project_dir,
        "session_id": session_id
    }

@app.get("/api/session/{session_id}/terminal/ls")
async def list_directory_contents(session_id: str, path: str = ""):
    """List directory contents (like VS Code file explorer)"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = active_sessions[session_id]
    project_dir = session_data['project_dir']
    
    # Use the provided path or default to project directory
    target_path = os.path.join(project_dir, path) if path else project_dir
    
    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        items = []
        for item in os.listdir(target_path):
            item_path = os.path.join(target_path, item)
            items.append({
                "name": item,
                "path": os.path.relpath(item_path, project_dir),
                "type": "directory" if os.path.isdir(item_path) else "file",
                "size": os.path.getsize(item_path) if os.path.isfile(item_path) else None
            })
        
        return {
            "path": target_path,
            "relative_path": path,
            "items": sorted(items, key=lambda x: (x["type"] == "file", x["name"].lower()))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list directory: {str(e)}")

@app.get("/api/debug/terminal")
async def debug_terminal():
    """Debug endpoint to check terminal status"""
    return {
        "terminal_sessions": list(terminal_sessions.keys()),
        "active_sessions": list(active_sessions.keys())
    }

# ═══════════════════════════════════════════════════════════════════════
# MODEL PROCESSING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

# Store processing results per session
model_processing_results: Dict[str, Dict] = {}

@app.post("/api/model/{session_id}/classify")
async def classify_model(session_id: str):
    """Classify the uploaded model type from file structure."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    from model_processing.classifier import ModelClassifier
    classifier = ModelClassifier()
    project_dir = active_sessions[session_id]['project_dir']
    # Debug: show exactly what we're scanning
    print(f"[classify] session={session_id}, project_dir={project_dir}, exists={os.path.isdir(project_dir)}")
    if os.path.isdir(project_dir):
        top = [f for f in os.listdir(project_dir) if f != '.venv']
        print(f"[classify] top-level contents (excl .venv): {top}")
    result = classifier.classify(project_dir)

    # Store in session
    active_sessions[session_id]['classification'] = result.to_dict()

    return result.to_dict()

@app.get("/api/model/{session_id}/classification")
async def get_classification(session_id: str):
    """Get stored classification for a session."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    classification = active_sessions[session_id].get('classification')
    if not classification:
        raise HTTPException(status_code=404, detail="Model not yet classified")
    return classification

@app.post("/api/model/{session_id}/scan")
async def scan_model(session_id: str):
    """Scan uploaded files without classification."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    from model_processing.scanner import FileScanner
    scanner = FileScanner()
    project_dir = active_sessions[session_id]['project_dir']
    # Debug: show exactly what we're scanning
    print(f"[scan] session={session_id}, project_dir={project_dir}, exists={os.path.isdir(project_dir)}")
    if os.path.isdir(project_dir):
        top = [f for f in os.listdir(project_dir) if f != '.venv']
        print(f"[scan] top-level contents (excl .venv): {top}")
    result = scanner.scan(project_dir)
    print(f"[scan] result: {result.file_count} files, {result.dir_count} dirs, {result.total_size/(1024*1024):.1f} MB")
    return result.to_dict()

@app.post("/api/model/{session_id}/test")
async def test_model(session_id: str, max_prompts: int = 25, hf_model_name: Optional[str] = None):
    """Run the full model processing pipeline: classify → install → test → score → fix."""
    # Fix: Frontend adds spaces around slash, strip them
    if hf_model_name:
        hf_model_name = hf_model_name.replace(" / ", "/").replace("/ ", "/").replace(" /", "/").strip()
    
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    from model_processing.state_machine import ModelProcessingStateMachine

    session_data = active_sessions[session_id]
    project_dir = session_data['project_dir']
    pip_exe = session_data.get('pip_exe')
    python_exe = session_data.get('python_exe')

    sm = ModelProcessingStateMachine(
        project_dir=project_dir,
        session_id=session_id,
        pip_exe=pip_exe,
        python_exe=python_exe,
        hf_model_name=hf_model_name,
        max_test_prompts=max_prompts,
    )

    result = sm.process()

    # Store result
    model_processing_results[session_id] = result
    active_sessions[session_id]['processing_state'] = sm.get_state()
    active_sessions[session_id]['processing_result'] = result
    if hf_model_name:
        active_sessions[session_id]['hf_model_name'] = hf_model_name

    return result

@app.get("/api/model/{session_id}/test-results")
async def get_test_results(session_id: str):
    """Get stored test results for a session."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    result = model_processing_results.get(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="No test results available")
    return result

@app.get("/api/model/{session_id}/report")
async def download_report(session_id: str):
    """Download a PDF ethics report for a session."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    result = model_processing_results.get(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="No test results available. Run tests first.")

    from model_processing.report_generator import generate_report_pdf
    try:
        pdf_bytes = generate_report_pdf(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="ethos_report_{session_id[:8]}.pdf"'},
    )

@app.get("/api/model/{session_id}/status")
async def get_model_status(session_id: str):
    """Get lightweight processing status for polling."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = active_sessions[session_id]
    result = model_processing_results.get(session_id)

    return {
        "session_id": session_id,
        "processing_state": session_data.get('processing_state', 'IDLE'),
        "classification": session_data.get('classification'),
        "verdict": result.get('context', {}).get('verdict') if result else None,
        "has_results": result is not None,
    }

@app.post("/api/model/{session_id}/purify")
async def purify_model(session_id: str):
    """Apply purification to a model that failed ethics tests."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    result = model_processing_results.get(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run tests first")

    from model_processing.purification import ModelPurifier
    from model_processing.scoring import ViolationScorer, TestRecord
    from model_processing.adapters import FallbackAdapter

    purifier = ModelPurifier()
    adapter = FallbackAdapter()

    # Reconstruct test records from stored results
    test_data = result.get('context', {}).get('test_summary', {})
    records_data = test_data.get('records', [])

    # Create a safety-wrapped adapter
    purified = purifier.create_safety_wrapper(adapter)

    return {
        "message": "Safety wrapper applied",
        "purified": True,
        "adapter_info": purified.get_info(),
    }

@app.post("/api/model/{session_id}/approve")
async def approve_model(session_id: str):
    """Manually approve a model."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    active_sessions[session_id]['processing_state'] = 'APPROVED'
    active_sessions[session_id]['manually_approved'] = True
    return {"message": "Model manually approved", "session_id": session_id}

@app.post("/api/model/{session_id}/reject")
async def reject_model(session_id: str, reason: str = "Manual rejection"):
    """Manually reject a model."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    active_sessions[session_id]['processing_state'] = 'REJECTED'
    active_sessions[session_id]['rejection_reason'] = reason
    return {"message": "Model manually rejected", "session_id": session_id, "reason": reason}

# ═══════════════════════════════════════════════════════════════════════════
# LoRA REPAIR ENDPOINTS (Manual trigger from frontend)
# ═══════════════════════════════════════════════════════════════════════════

# Background repair jobs: { session_id: { status, progress, result, error, thread } }
_repair_jobs: Dict[str, Dict] = {}


@app.post("/api/model/{session_id}/repair")
async def start_repair(session_id: str):
    """Start LoRA repair training on LOCAL GPU. Runs in background."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    result = model_processing_results.get(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="No test results. Run tests first.")

    verdict = result.get("context", {}).get("verdict", {}).get("verdict")
    if verdict not in ("REJECT", "NEEDS_FIX"):
        raise HTTPException(status_code=400, detail=f"Model verdict is '{verdict}', repair only for REJECT/NEEDS_FIX")

    if session_id in _repair_jobs and _repair_jobs[session_id].get("status") == "running":
        return {"status": "already_running", "progress": _repair_jobs[session_id].get("progress", {})}

    hf_model = active_sessions[session_id].get("hf_model_name", "")
    if not hf_model:
        hf_model = result.get("context", {}).get("hf_model_name", "")
    if not hf_model:
        raise HTTPException(status_code=400, detail="HuggingFace model name not found for this session")

    _repair_jobs[session_id] = {
        "status": "running",
        "progress": {"stage": "starting", "round": 0},
        "result": None,
        "error": None,
    }

    def _run_repair():
        import logging
        logger = logging.getLogger("ethos.repair")
        try:
            from model_processing.local_lora_trainer import LocalLoRATrainer
            from model_processing.patch_generator import PatchGenerator
            from model_processing.scoring import ViolationScorer, TestRecord
            from model_processing.adversarial_prompts import get_split
            from model_processing.purification import ModelPurifier

            _repair_jobs[session_id]["progress"] = {"stage": "loading_model", "round": 0}

            # ── Step 1: Load (or reuse) the model on local GPU ──
            from ethos_testing.local_model import get_model
            model = get_model(hf_model)

            _repair_jobs[session_id]["progress"] = {"stage": "collecting_train_data", "round": 0}

            # ── Step 2: Run TRAIN split to collect pass/fail data ──
            scorer = ViolationScorer()
            train_prompts = get_split("train")
            train_records = []
            for i, prompt_data in enumerate(train_prompts):
                _repair_jobs[session_id]["progress"] = {
                    "stage": "collecting_train_data",
                    "current": i + 1,
                    "total": len(train_prompts),
                }
                response = model.respond(prompt_data["prompt"])
                scores = scorer.score_response(
                    prompt_data["prompt"], response, prompt_data.get("category", "harm")
                )
                record = TestRecord(
                    test_id=prompt_data.get("id", f"train_{i}"),
                    model_id=hf_model,
                    category=prompt_data.get("category", "unknown"),
                    prompt=prompt_data["prompt"],
                    response=response,
                    scores=scores,
                )
                train_records.append(record)

            # ── Steps 3–5: Multi-round repair loop (max 3 rounds) ──────────────
            MAX_ROUNDS = 3
            round_history = []
            previous_pass_rate = -1.0
            patch_gen = PatchGenerator()
            purifier = ModelPurifier()
            from model_processing.adapters import FallbackAdapter
            import tempfile

            # Accumulate current records — start with the initial train sweep
            current_train_records = list(train_records)

            for repair_round in range(1, MAX_ROUNDS + 1):
                logger.info(f"═══ Repair Round {repair_round}/{MAX_ROUNDS} ═══")

                # 3a. Generate balanced patch from current failures
                _repair_jobs[session_id]["progress"] = {
                    "stage": "generating_balanced_data",
                    "round": repair_round,
                }
                balanced_patches = patch_gen.generate_balanced_patch(
                    current_train_records, target_ratio=0.5
                )

                output_dir = os.path.join(
                    tempfile.gettempdir(), "ethos_lora", session_id, f"round_{repair_round}"
                )
                paths = patch_gen.save_split_jsonl(balanced_patches, output_dir)

                # 3b. Apply safety wrapper
                _repair_jobs[session_id]["progress"] = {
                    "stage": "applying_safety_wrapper",
                    "round": repair_round,
                }
                adapter = FallbackAdapter(hf_model)
                purified = purifier.create_safety_wrapper(adapter)

                # 3c. Re-test on TEST split
                test_prompts = get_split("test")
                retest_records = []
                pass_count = 0
                fail_count = 0

                for i, prompt_data in enumerate(test_prompts):
                    _repair_jobs[session_id]["progress"] = {
                        "stage": "retesting",
                        "current": i + 1,
                        "total": len(test_prompts),
                        "round": repair_round,
                    }
                    response = purified.generate(prompt_data["prompt"])
                    scores = scorer.score_response(
                        prompt_data["prompt"], response, prompt_data.get("category", "harm")
                    )
                    record = TestRecord(
                        test_id=prompt_data.get("id", f"r{repair_round}_test_{i}"),
                        model_id=hf_model,
                        category=prompt_data.get("category", "unknown"),
                        prompt=prompt_data["prompt"],
                        response=response,
                        scores=scores,
                    )
                    retest_records.append(record)
                    if record.verdict == "PASS":
                        pass_count += 1
                    else:
                        fail_count += 1

                total = pass_count + fail_count
                pass_rate = pass_count / max(total, 1) * 100
                round_verdict = scorer.make_verdict(retest_records)

                logger.info(
                    f"Round {repair_round} result: {pass_count}/{total} passed "
                    f"({pass_rate:.1f}%) — verdict: {round_verdict['verdict']}"
                )

                round_history.append({
                    "round": repair_round,
                    "pass_count": pass_count,
                    "fail_count": fail_count,
                    "total_tests": total,
                    "pass_rate": round(pass_rate, 1),
                    "verdict": round_verdict["verdict"],
                    "patches_generated": len(balanced_patches),
                })

                # Update status mid-repair so frontend shows live progress
                _repair_jobs[session_id]["result"] = {
                    "outcome": "IN_PROGRESS",
                    "final_pass_rate": round(pass_rate, 1),
                    "rounds_completed": repair_round,
                    "round_history": list(round_history),
                }

                # ── Early exit conditions ────────────────────────────────────
                # 1. Model passed strict verdict → accept immediately
                if round_verdict["verdict"] in ["APPROVE", "WARN"]:
                    logger.info(f"✅ Model passed ethics verdict at round {repair_round}. Stopping.")
                    break

                # 2. No improvement vs previous round → plateau, stop wasting GPU
                if pass_rate <= previous_pass_rate:
                    logger.info(
                        f"⚠️ No improvement: {pass_rate:.1f}% <= {previous_pass_rate:.1f}%. Stopping."
                    )
                    break

                previous_pass_rate = pass_rate

                # 3. Prepare next round: re-score train split to get fresh fail records
                # Re-use the test failures to focus next patch on remaining problems
                if repair_round < MAX_ROUNDS:
                    _repair_jobs[session_id]["progress"] = {
                        "stage": "collecting_train_data",
                        "round": repair_round + 1,
                    }
                    # Collect fresh train records using current model state
                    fresh_train_records = []
                    for j, prompt_data in enumerate(train_prompts):
                        _repair_jobs[session_id]["progress"] = {
                            "stage": "collecting_train_data",
                            "current": j + 1,
                            "total": len(train_prompts),
                            "round": repair_round + 1,
                        }
                        fresh_response = purified.generate(prompt_data["prompt"])
                        fresh_scores = scorer.score_response(
                            prompt_data["prompt"], fresh_response, prompt_data.get("category", "harm")
                        )
                        fresh_record = TestRecord(
                            test_id=prompt_data.get("id", f"r{repair_round + 1}_train_{j}"),
                            model_id=hf_model,
                            category=prompt_data.get("category", "unknown"),
                            prompt=prompt_data["prompt"],
                            response=fresh_response,
                            scores=fresh_scores,
                        )
                        fresh_train_records.append(fresh_record)
                    current_train_records = fresh_train_records

            # ── Final aggregation after loop ─────────────────────────────────
            best_round = max(round_history, key=lambda r: r["pass_rate"])
            final_verdict = scorer.make_verdict(retest_records)
            is_accepted = final_verdict["verdict"] in ["APPROVE", "WARN"]

            repair_result = {
                "outcome": "ACCEPTED" if is_accepted else "REJECTED",
                "reason": final_verdict["reason"],
                "final_pass_rate": round(pass_rate, 1),
                "best_pass_rate": best_round["pass_rate"],
                "best_round": best_round["round"],
                "rounds_completed": len(round_history),
                "balanced_patches_generated": len(balanced_patches),
                "train_jsonl_path": paths.get("combined", ""),
                "round_history": round_history,
            }

            _repair_jobs[session_id]["status"] = "completed"
            _repair_jobs[session_id]["result"] = repair_result

            # Update session state
            if repair_result["outcome"] == "ACCEPTED":
                active_sessions[session_id]["processing_state"] = "APPROVED"
                if session_id in model_processing_results:
                    model_processing_results[session_id]["state"] = "APPROVED"
                    model_processing_results[session_id]["context"]["purification_result"] = {
                        "passed": True,
                        "outcome": "ACCEPTED",
                        "fix_rate": repair_result["final_pass_rate"],
                        "total_retested": total,
                        "still_failing": fail_count,
                        "fixed": pass_count,
                        "rounds_completed": len(round_history),
                    }
            else:
                active_sessions[session_id]["processing_state"] = "REJECTED"

        except Exception as e:
            import traceback
            traceback.print_exc()
            _repair_jobs[session_id]["status"] = "failed"
            _repair_jobs[session_id]["error"] = str(e)

    t = threading.Thread(target=_run_repair, daemon=True)
    t.start()
    _repair_jobs[session_id]["thread"] = t

    return {
        "status": "started",
        "message": "LoRA repair training started on LOCAL GPU",
        "session_id": session_id,
        "model": hf_model,
        "device": "local_gpu",
    }


@app.get("/api/model/{session_id}/repair-status")
async def get_repair_status(session_id: str):
    """Poll LoRA repair training progress."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    job = _repair_jobs.get(session_id)
    if not job:
        return {"status": "idle", "message": "No repair job started"}

    return {
        "status": job.get("status", "idle"),
        "progress": job.get("progress", {}),
        "result": job.get("result"),
        "error": job.get("error"),
    }


@app.get("/api/models")
async def list_all_models():
    """List all uploaded models with their status."""
    models = []
    for sid, data in active_sessions.items():
        models.append({
            "session_id": sid,
            "project_dir": data.get('project_dir', ''),
            "processing_state": data.get('processing_state', 'IDLE'),
            "classification": data.get('classification'),
            "has_results": sid in model_processing_results,
        })
    return {"models": models, "total": len(models)}

@app.get("/api/prompts/adversarial")
async def get_adversarial_prompts(category: Optional[str] = None):
    """Get adversarial test prompts."""
    from model_processing.adversarial_prompts import get_all_prompts, get_prompts_by_category, get_prompt_count
    if category:
        return {"prompts": get_prompts_by_category(category), "category": category}
    return {"prompts": get_all_prompts(), "counts": get_prompt_count()}

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        # Large uploads: increase header size limit and keep-alive timeout
        h11_max_incomplete_event_size=1024 * 1024,  # 1 MB header limit
        timeout_keep_alive=300,  # 5 min keep-alive for large file transfers
    )