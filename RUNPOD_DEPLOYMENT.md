# RunPod Deployment Guide for ETHOS AI Evaluator

This guide explains how to deploy the ETHOS AI Evaluator on RunPod for GPU-accelerated AI model inference.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Detailed Setup](#detailed-setup)
4. [Configuration](#configuration)
5. [Accessing Your Application](#accessing-your-application)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- RunPod account ([sign up here](https://runpod.io))
- GPU credits in your RunPod account
- Your OpenAI API key (optional, for AI agent features)

---

## Quick Start

### Option 1: Deploy Using RunPod Web Terminal

1. **Create a Pod on RunPod:**
   - Go to [RunPod Console](https://www.runpod.io/console/pods)
   - Click "Deploy" → "GPU Pods"
   - Choose a GPU (recommended: **RTX 3090**, **RTX 4090**, or **A4000**)
   - Select a PyTorch template (e.g., `runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel`)
   - Set disk space to at least **20GB**
   - Deploy the pod

2. **Connect to Your Pod:**
   - Click "Connect" → "Start Web Terminal" or use SSH

3. **Clone and Setup:**
   ```bash
   # Clone your repository
   git clone https://github.com/vivzz2216/ethos-ai-evaluator.git
   cd ethos-ai-evaluator

   # Install backend dependencies
   cd backend
   pip install -r requirements.txt

   # Install frontend dependencies
   cd ..
   npm install

   # Setup environment variables
   cp .env.example .env
   nano .env  # Add your OPENAI_API_KEY
   ```

4. **Start the Application:**
   ```bash
   # Terminal 1: Start backend (in backend directory)
   cd backend
   python app.py

   # Terminal 2: Start frontend (in root directory)
   npm run dev
   ```

5. **Expose Ports:**
   - Backend: Port **8000**
   - Frontend: Port **5173** (Vite default)
   - In RunPod, click "Connect" → "TCP Port Mappings" to expose these ports

---

## Detailed Setup

### Step 1: Create RunPod Dockerfile (Automated Deployment)

Create a `Dockerfile.runpod` in your project root:

```dockerfile
FROM runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel

# Set working directory
WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    curl \\
    git \\
    && rm -rf /var/lib/apt/lists/*

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \\
    apt-get install -y nodejs

# Copy project files
COPY . /workspace/ethos-ai-evaluator
WORKDIR /workspace/ethos-ai-evaluator

# Install Python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

# Install Node dependencies
RUN npm install

# Expose ports
EXPOSE 8000 5173

# Start script
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
```

### Step 2: Create Start Script

Create `start.sh` in your project root:

```bash
#!/bin/bash

# Start backend
cd /workspace/ethos-ai-evaluator/backend
python app.py &

# Start frontend
cd /workspace/ethos-ai-evaluator
npm run dev -- --host 0.0.0.0 &

# Keep container running
wait
```

### Step 3: Deploy to RunPod

Upload your repository to RunPod or build a custom Docker image.

---

## Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
# OpenAI API Key for AI Agent
OPENAI_API_KEY=sk-your-actual-key-here

# Optional: RunPod specific settings
PORT=8000
HOST=0.0.0.0
```

### Backend Configuration

The backend (`backend/app.py`) runs on port **8000** by default. Update if needed:

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Frontend Configuration

Update `vite.config.ts` to proxy API requests and bind to all interfaces:

```typescript
export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ethos': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

---

## Accessing Your Application

### Using RunPod Port Forwarding

1. In RunPod console, go to your pod
2. Click "Connect" → "TCP Port Mappings"
3. Note the public URLs for:
   - **Backend**: `https://xxxxx-8000.proxy.runpod.net`
   - **Frontend**: `https://xxxxx-5173.proxy.runpod.net`

### Update Frontend API Configuration

Update the frontend to use the RunPod backend URL:

```typescript
// In your API configuration file
const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';
```

Set environment variable in RunPod:
```bash
export VITE_API_URL=https://xxxxx-8000.proxy.runpod.net
```

---

## Running Models on GPU

### Using Local Models with GPU

Your project already supports Hugging Face models. On RunPod with GPU:

1. **Install CUDA-enabled PyTorch** (usually pre-installed):
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```

2. **Verify GPU availability:**
   ```python
   import torch
   print(f"CUDA available: {torch.cuda.is_available()}")
   print(f"GPU: {torch.cuda.get_device_name(0)}")
   ```

3. **Your models will automatically use GPU** via the existing code in `backend/ethos_testing/local_model.py`

### Loading Larger Models

For larger models (e.g., Llama-3, GPT-NeoX):

```python
# In backend/ethos_testing/local_model.py
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,  # Use FP16 for faster inference
    device_map="auto",  # Automatically use GPU
    low_cpu_mem_usage=True
)
```

---

## Monitoring and Performance

### Check GPU Usage

```bash
# In RunPod terminal
nvidia-smi

# Watch GPU usage in real-time
watch -n 1 nvidia-smi
```

### View Logs

```bash
# Backend logs
cd /workspace/ethos-ai-evaluator/backend
tail -f app.log

# Check running processes
ps aux | grep python
ps aux | grep node
```

---

## Troubleshooting

### Issue: Module Not Found Errors

**Solution:**
```bash
cd /workspace/ethos-ai-evaluator/backend
pip install -r requirements.txt --upgrade
```

### Issue: Port Already in Use

**Solution:**
```bash
# Kill processes on port 8000
lsof -ti:8000 | xargs kill -9

# Kill processes on port 5173
lsof -ti:5173 | xargs kill -9
```

### Issue: Frontend Can't Connect to Backend

**Solution:**
1. Check backend is running: `curl http://localhost:8000/health`
2. Update CORS settings in `backend/app.py`:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],  # Allow all origins on RunPod
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

### Issue: Out of GPU Memory

**Solution:**
```python
# Use smaller models or quantization
from transformers import AutoModelForCausalLM, BitsAndBytesConfig

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16
)

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    quantization_config=quantization_config,
    device_map="auto"
)
```

---

## Cost Optimization

### Tips to Reduce RunPod Costs:

1. **Use Spot Instances**: 70-80% cheaper than on-demand
2. **Auto-stop**: Stop pod when not in use
3. **Choose Right GPU**:
   - Development: RTX 3090 ($0.34/hr)
   - Production: RTX 4090 or A6000 ($0.79/hr)
4. **Use Smaller Models**: Start with `sshleifer/tiny-gpt2` for testing

---

## Production Deployment

### Using Docker Hub

1. **Build and push image:**
   ```bash
   docker build -f Dockerfile.runpod -t yourusername/ethos-ai-evaluator .
   docker push yourusername/ethos-ai-evaluator
   ```

2. **Deploy on RunPod:**
   - Select "Custom Template"
   - Enter your Docker image: `yourusername/ethos-ai-evaluator`
   - Set environment variables
   - Deploy

### Persistent Storage

Mount a network volume in RunPod to persist:
- Model weights
- User data
- Session information

```bash
# In RunPod, add network volume at /workspace/data
# Update your application to use /workspace/data for storage
```

---

## Support

For issues:
- Check RunPod documentation: https://docs.runpod.io
- Review application logs
- Monitor GPU usage with `nvidia-smi`

---

## Quick Reference Commands

```bash
# Start backend
cd backend && python app.py

# Start frontend  
npm run dev -- --host 0.0.0.0

# Check GPU
nvidia-smi

# View processes
ps aux | grep python

# Kill all Python processes
pkill -f python

# Restart services
systemctl restart app
```

---

**🚀 Your ETHOS AI Evaluator is now ready to run on RunPod with GPU acceleration!**
