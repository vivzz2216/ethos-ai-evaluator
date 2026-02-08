# RunPod Quick Start Guide

## 🚀 Fastest Way to Deploy

### 1. Create RunPod Pod
```bash
# Visit: https://www.runpod.io/console/pods
# Choose: PyTorch 2.0.1 + CUDA 11.8
# GPU: RTX 3090 or better
# Disk: 20GB minimum
```

### 2. One-Command Setup
Copy and paste this into your RunPod terminal:

```bash
git clone https://github.com/vivzz2216/ethos-ai-evaluator.git && \
cd ethos-ai-evaluator && \
pip install -r backend/requirements.txt && \
npm install && \
cp .env.example .env && \
chmod +x start.sh && \
./start.sh
```

### 3. Access Your App
- Get public URLs from: **Connect → TCP Port Mappings**
- Backend: Port **8000**
- Frontend: Port **5173**

---

## 📝 Manual Setup (If You Prefer)

### Step 1: Clone Repository
```bash
git clone https://github.com/vivzz2216/ethos-ai-evaluator.git
cd ethos-ai-evaluator
```

### Step 2: Install Dependencies
```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ..
npm install
```

### Step 3: Configure Environment
```bash
cp .env.example .env
nano .env  # Add your OPENAI_API_KEY
```

### Step 4: Start Services

**Terminal 1 - Backend:**
```bash
cd backend
python app.py
```

**Terminal 2 - Frontend:**
```bash
npm run dev -- --host 0.0.0.0
```

---

## 🔧 Common Tasks

### Check GPU
```bash
nvidia-smi
```

### View Logs
```bash
# Backend
tail -f /workspace/backend.log

# Frontend
tail -f /workspace/frontend.log
```

### Restart Services
```bash
# Kill existing processes
pkill -f "python app.py"
pkill -f "vite"

# Restart
./start.sh
```

### Test Backend
```bash
curl http://localhost:8000/health
```

---

## 💰 Recommended GPU Options

| GPU | VRAM | Price/hr | Best For |
|-----|------|----------|----------|
| RTX 3090 | 24GB | $0.34 | Testing & Development |
| RTX 4090 | 24GB | $0.69 | Production (small) |
| A6000 | 48GB | $0.79 | Large Models |
| A100 | 80GB | $1.89 | Enterprise |

**💡 Tip**: Use **Spot Instances** for 70-80% savings!

---

## 🐛 Quick Fixes

### Backend Won't Start
```bash
cd backend
pip install -r requirements.txt --upgrade
python app.py
```

### Frontend Won't Start
```bash
rm -rf node_modules package-lock.json
npm install
npm run dev -- --host 0.0.0.0
```

### Port Already in Use
```bash
# Free port 8000
lsof -ti:8000 | xargs kill -9

# Free port 5173
lsof -ti:5173 | xargs kill -9
```

### Out of Memory
```bash
# Clear GPU memory
pkill -f python
nvidia-smi

# Use smaller model in your requests
# Example: "sshleifer/tiny-gpt2" instead of larger models
```

---

## 📦 Docker Deployment (Advanced)

### Build Image
```bash
docker build -f Dockerfile.runpod -t ethos-ai-evaluator .
```

### Run Container
```bash
docker run -d \
  --gpus all \
  -p 8000:8000 \
  -p 5173:5173 \
  -e OPENAI_API_KEY=your-key-here \
  ethos-ai-evaluator
```

---

## 🔗 Useful Links

- **RunPod Console**: https://www.runpod.io/console/pods
- **RunPod Docs**: https://docs.runpod.io
- **Repository**: https://github.com/vivzz2216/ethos-ai-evaluator

---

## 📞 Need Help?

1. Check logs: `tail -f /workspace/backend.log`
2. Verify GPU: `nvidia-smi`
3. Test backend: `curl http://localhost:8000/health`
4. Review full guide: `cat RUNPOD_DEPLOYMENT.md`

---

**✅ That's it! Your ETHOS AI Evaluator should now be running on RunPod with GPU acceleration.**
