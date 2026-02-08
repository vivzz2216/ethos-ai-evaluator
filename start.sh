#!/bin/bash

# ETHOS AI Evaluator - RunPod Startup Script
# This script starts both backend and frontend services

set -e

echo "=========================================="
echo "Starting ETHOS AI Evaluator on RunPod"
echo "=========================================="

# Navigate to project directory
cd /workspace/ethos-ai-evaluator

# Check for .env file
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found. Creating from example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env file. Please update with your API keys."
    fi
fi

# Display GPU information
echo ""
echo "📊 GPU Information:"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader

# Start backend
echo ""
echo "🚀 Starting Backend (Port 8000)..."
cd /workspace/ethos-ai-evaluator/backend
python app.py > /workspace/backend.log 2>&1 &
BACKEND_PID=$!
echo "✅ Backend started with PID: $BACKEND_PID"

# Wait for backend to be ready
echo "⏳ Waiting for backend to start..."
sleep 5

# Check if backend is running
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Backend is healthy!"
else
    echo "⚠️  Warning: Backend health check failed. Check logs at /workspace/backend.log"
fi

# Start frontend
echo ""
echo "🎨 Starting Frontend (Port 5173)..."
cd /workspace/ethos-ai-evaluator
npm run dev -- --host 0.0.0.0 > /workspace/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "✅ Frontend started with PID: $FRONTEND_PID"

# Display access information
echo ""
echo "=========================================="
echo "✅ ETHOS AI Evaluator is running!"
echo "=========================================="
echo ""
echo "Access your application:"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo ""
echo "RunPod users: Use TCP Port Mappings to get public URLs"
echo ""
echo "Logs:"
echo "  Backend:  tail -f /workspace/backend.log"
echo "  Frontend: tail -f /workspace/frontend.log"
echo ""
echo "GPU Monitoring: watch -n 1 nvidia-smi"
echo ""
echo "=========================================="

# Function to handle shutdown
shutdown() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "✅ Services stopped"
    exit 0
}

# Trap termination signals
trap shutdown SIGTERM SIGINT

# Keep the script running and monitor processes
while true; do
    # Check if backend is still running
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "❌ Backend crashed! Check /workspace/backend.log"
        shutdown
    fi
    
    # Check if frontend is still running
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo "❌ Frontend crashed! Check /workspace/frontend.log"
        shutdown
    fi
    
    sleep 10
done
