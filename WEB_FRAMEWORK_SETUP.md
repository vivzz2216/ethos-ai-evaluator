# ETHOS Web Framework Support Setup

## 🚀 Overview

ETHOS now supports running Flask, FastAPI, and Django applications with automatic dependency installation and real-time server management!

## ✨ Features

- **Auto-Detection**: Automatically detects Flask, FastAPI, or Django applications
- **Dependency Management**: Installs packages from `requirements.txt` automatically
- **Virtual Environments**: Isolated Python environments per session
- **Real Server Execution**: Actual web servers running on configurable ports
- **Interactive Terminal**: Enhanced terminal with framework-specific commands
- **Session Management**: Multiple isolated development sessions

## 🛠️ Setup Instructions

### 1. Backend Setup

```bash
# Navigate to project root
cd ethos-ai-evaluator

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Start the backend server
python app.py
```

**Or use the provided scripts:**
```bash
# Windows
start_backend_framework.bat

# Cross-platform
python start_backend_framework.py
```

The backend will be available at: `http://localhost:8000`

### 2. Frontend Setup

```bash
# Install frontend dependencies (if not already done)
cd client
npm install

# Start the frontend
npm run dev
```

The frontend will be available at: `http://localhost:3000`

## 🎯 Usage

### 1. Upload Your Project

1. Open the ETHOS Editor
2. Upload your Flask/FastAPI/Django project files
3. The system will automatically detect the framework
4. Dependencies from `requirements.txt` will be installed automatically

### 2. Run Your Application

In the terminal, use these commands:

```bash
# Start the web server
run-server

# Stop the server
stop-server

# Check server status
server-status

# Install dependencies manually
install-deps

# Install a specific package
pip install package-name

# Get framework information
framework-info
```

### 3. Framework-Specific Examples

#### Flask App
```python
# app.py
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello, ETHOS!'

if __name__ == '__main__':
    app.run(debug=True)
```

#### FastAPI App
```python
# main.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "ETHOS"}

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}
```

#### Django App
```python
# manage.py (standard Django structure)
# settings.py
# urls.py
# views.py
```

## 🔧 Backend API Endpoints

### Session Management
- `POST /api/session/create` - Create a new session
- `DELETE /api/session/{session_id}` - Delete a session

### File Management
- `POST /api/session/{session_id}/upload` - Upload files
- `GET /api/session/{session_id}/status` - Get session status

### Code Execution
- `POST /api/session/{session_id}/execute` - Execute Python code
- `POST /api/session/{session_id}/run-server` - Start web server
- `POST /api/session/{session_id}/stop-server` - Stop web server

### Package Management
- `POST /api/session/{session_id}/install` - Install a package
- `GET /api/session/{session_id}/packages` - List installed packages

## 🎨 UI Features

### Framework Detection Badge
- Shows detected framework (Flask/FastAPI/Django) in the top bar
- Framework-specific terminal commands

### Enhanced Terminal
- Framework-specific commands
- Real-time server status
- Package installation progress
- Command history with arrow keys

### File Upload
- Drag & drop support
- Folder structure preservation
- Automatic requirements.txt processing

## 🚨 Troubleshooting

### Backend Connection Issues
1. Ensure backend is running on `http://localhost:8000`
2. Check firewall settings
3. Verify Python dependencies are installed

### Framework Detection Issues
1. Ensure your main file contains framework imports
2. Check that `requirements.txt` includes the framework
3. Verify file structure is correct

### Server Start Issues
1. Check if port 5000 is available
2. Verify all dependencies are installed
3. Check the terminal output for error messages

## 📝 Example Project Structure

```
my-flask-app/
├── app.py
├── requirements.txt
├── templates/
│   └── index.html
└── static/
    └── style.css

my-fastapi-app/
├── main.py
├── requirements.txt
└── models/
    └── user.py

my-django-app/
├── manage.py
├── requirements.txt
├── myproject/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── myapp/
    ├── models.py
    ├── views.py
    └── urls.py
```

## 🔗 API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation.

## 🎉 Ready to Code!

Your ETHOS editor now supports full web framework development with automatic dependency management and real server execution!
