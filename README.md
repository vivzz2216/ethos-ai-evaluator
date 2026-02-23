# ETHOS AI Evaluator

A comprehensive AI evaluation platform for testing ethical reasoning, logical consistency, and truthfulness of AI models with GPU acceleration support.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Node](https://img.shields.io/badge/node-18+-green.svg)

## Features

- **🧠 AI Model Evaluation**: Test AI models on ethics, logic, and truthfulness
- **🎯 Multiple Test Categories**:
  - Ethical reasoning evaluation
  - Logical consistency checking
  - Truthfulness assessment
- **🤖 AI Agent Integration**: Built-in AI agent with code analysis capabilities
- **📊 Detailed Reporting**: Comprehensive scoring and feedback
- **🚀 GPU Acceleration**: RunPod integration for fast model inference
- **💾 Local Model Support**: Works with Hugging Face models offline
- **🎨 Modern UI**: Beautiful React-based interface with real-time updates

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **PyTorch** - Deep learning framework
- **Transformers** - Hugging Face model integration
- **Flask** - Additional web framework support

### Frontend
- **React** - UI library
- **TypeScript** - Type-safe JavaScript
- **Vite** - Fast build tool
- **Tailwind CSS** - Utility-first CSS

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Git

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/vivzz2216/ethos-ai-evaluator.git
   cd ethos-ai-evaluator
   ```

2. **Set up Backend**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Set up Frontend**
   ```bash
   npm install
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

5. **Start Services**

   **Terminal 1 - Backend:**
   ```bash
   cd backend
   python app.py
   ```

   **Terminal 2 - Frontend:**
   ```bash
   npm run dev
   ```

6. **Access the Application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## RunPod Deployment

Deploy on RunPod for GPU-accelerated inference:

### Quick Deploy
```bash
git clone https://github.com/vivzz2216/ethos-ai-evaluator.git && \
cd ethos-ai-evaluator && \
pip install -r backend/requirements.txt && \
npm install && \
chmod +x start.sh && \
./start.sh
```

For detailed instructions, see:
- **[RunPod Quick Start Guide](RUNPOD_QUICKSTART.md)** - Fast deployment
- **[RunPod Deployment Guide](RUNPOD_DEPLOYMENT.md)** - Complete documentation

## Project Structure

```
ethos-ai-evaluator/
├── backend/
│   ├── agent/              # AI agent system
│   ├── ethos_testing/      # Evaluation modules
│   ├── model_processing/   # Model adapters
│   ├── data/              # Test datasets
│   ├── app.py             # Main FastAPI application
│   └── requirements.txt   # Python dependencies
├── client/
│   └── src/
│       ├── components/    # React components
│       ├── hooks/         # Custom hooks
│       └── lib/          # Utilities
├── data/                  # Application data
├── .env.example          # Environment template
├── package.json          # Node dependencies
├── Dockerfile.runpod     # RunPod Docker config
├── start.sh             # Startup script
└── README.md            # This file
```

## API Endpoints

### Health Check
```bash
GET /health
```

### ETHOS Testing
```bash
POST /ethos/test/ethical
POST /ethos/test/logical  
POST /ethos/test/truthfulness
POST /ethos/test/full
```

### AI Agent
```bash
POST /agent/chat
GET /agent/history/{chat_id}
```

### Model Processing
```bash
POST /api/session/{session_id}/classify
POST /api/session/{session_id}/convert
```

See full API documentation at: http://localhost:8000/docs

## Supported Models

### Hugging Face Models (Local)
- `sshleifer/tiny-gpt2` - Fast, lightweight (35MB)
- `openai-community/gpt2` - Standard GPT-2 (500MB)
- `google-t5/t5-small` - T5 for reasoning (240MB)
- Any Hugging Face causal language model

### Cloud Models
- GPT-4 Turbo (via OpenAI API)
- GPT-4o (via OpenAI API)
- GPT-3.5 Turbo (via OpenAI API)

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# OpenAI API Key (required for AI agent)
OPENAI_API_KEY=sk-your-key-here

# Optional: Server configuration
PORT=8000
HOST=0.0.0.0
```

### Backend Configuration

Edit `backend/app.py` for port and CORS settings.

### Frontend Configuration

Edit `vite.config.ts` for proxy and build settings.

## Development

### Running Tests
```bash
# Backend tests
cd backend
pytest

# Frontend tests
npm test
```

### Code Formatting
```bash
# Python
black backend/
ruff check backend/

# TypeScript
npm run lint
npm run format
```

### Building for Production
```bash
# Frontend build
npm run build

# Backend (use production server)
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

## GPU Requirements

### Recommended for RunPod:
- **Development**: RTX 3090 (24GB VRAM) - $0.34/hr
- **Production**: RTX 4090 (24GB VRAM) - $0.69/hr
- **Large Models**: A6000 (48GB VRAM) - $0.79/hr

### Local GPU:
- CUDA 11.8+ compatible
- 8GB+ VRAM minimum
- 16GB+ VRAM recommended

## Troubleshooting

### Backend Issues
```bash
# Reinstall dependencies
pip install -r backend/requirements.txt --upgrade

# Check Python version
python --version  # Should be 3.10+

# Test backend
curl http://localhost:8000/health
```

### Frontend Issues
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install

# Check Node version
node --version  # Should be 18+
```

### GPU Issues
```bash
# Check CUDA availability
python -c "import torch; print(torch.cuda.is_available())"

# View GPU info
nvidia-smi
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with FastAPI, React, and PyTorch
- Hugging Face for model infrastructure
- RunPod for GPU compute platform

## Support

For issues and questions:
- Open an issue on GitHub
- Check the documentation in `/docs`
- Review API docs at `/docs` endpoint

---

**Made with ❤️ for AI evaluation and testing**
