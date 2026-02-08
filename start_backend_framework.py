#!/usr/bin/env python3
"""
ETHOS Web Framework Backend Starter
This script starts the FastAPI backend server for web framework support.
"""

import subprocess
import sys
import os
import time
from pathlib import Path

def main():
    print("🚀 Starting ETHOS Web Framework Backend...")
    print("=" * 50)
    
    # Change to backend directory
    backend_dir = Path(__file__).parent / "backend"
    if not backend_dir.exists():
        print("❌ Backend directory not found!")
        return 1
    
    os.chdir(backend_dir)
    print(f"📁 Working directory: {backend_dir}")
    
    # Check if requirements.txt exists
    requirements_file = backend_dir / "requirements.txt"
    if not requirements_file.exists():
        print("❌ requirements.txt not found!")
        return 1
    
    # Install dependencies
    print("📦 Installing Python dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True, capture_output=True, text=True)
        print("✅ Dependencies installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        print(f"Error output: {e.stderr}")
        return 1
    
    print()
    print("🌐 Starting FastAPI server...")
    print("📍 Server will be available at: http://localhost:8000")
    print("📚 API documentation at: http://localhost:8000/docs")
    print("🔧 Health check at: http://localhost:8000/api/health")
    print()
    print("💡 Supported Frameworks:")
    print("   • Flask")
    print("   • FastAPI") 
    print("   • Django")
    print()
    print("⚡ Features:")
    print("   • Auto-dependency installation")
    print("   • Virtual environment isolation")
    print("   • Real-time server management")
    print("   • Session-based file handling")
    print()
    print("=" * 50)
    print("🔄 Starting server... (Press Ctrl+C to stop)")
    print("=" * 50)
    
    # Start the FastAPI server
    try:
        subprocess.run([sys.executable, "app.py"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Server failed to start: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
