#!/bin/bash
# ============================================================
# RunPod Setup Script for ETHOS Inference Server
# Run this inside your RunPod pod's web terminal
# ============================================================

set -e

echo "=== ETHOS Cloud Inference Setup ==="

# 1. Install Python dependencies
echo "[1/4] Installing dependencies..."
pip install fastapi uvicorn torch transformers accelerate httpx

# 2. Create workspace directory
mkdir -p /workspace/ethos

# 3. Download/copy the inference server
echo "[2/4] Creating inference server..."
cat > /workspace/ethos/inference_server.py << 'PYEOF'
"""
Lightweight inference server for RunPod GPU pod.
Loads a HuggingFace model and exposes /generate and /health endpoints.
"""
import argparse
import logging
import time
import torch
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inference_server")

app = FastAPI(title="ETHOS Cloud Inference")

model = None
tokenizer = None
model_info = {}


class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 200
    temperature: float = 0.7
    top_k: int = 50
    top_p: float = 0.9
    repetition_penalty: float = 1.2


class GenerateResponse(BaseModel):
    text: str
    tokens_generated: int
    time_seconds: float


def load_model(model_path: str):
    global model, tokenizer, model_info

    logger.info(f"Loading model from {model_path}...")
    t0 = time.time()

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    if tokenizer.pad_token is None and tokenizer.eos_token:
        tokenizer.pad_token = tokenizer.eos_token

    config = AutoConfig.from_pretrained(model_path)
    is_seq2seq = getattr(config, "model_type", "") == "t5"

    if is_seq2seq:
        from transformers import AutoModelForSeq2SeqLM
        auto_cls = AutoModelForSeq2SeqLM
    else:
        auto_cls = AutoModelForCausalLM

    if torch.cuda.is_available():
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}, VRAM: {gpu_mem:.1f}GB")
        model = auto_cls.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="auto",
            low_cpu_mem_usage=True,
        )
    else:
        logger.warning("No GPU detected, loading on CPU (slow)")
        model = auto_cls.from_pretrained(model_path, low_cpu_mem_usage=True)

    model.eval()
    elapsed = time.time() - t0
    device = next(model.parameters()).device

    model_info = {
        "model_path": model_path,
        "device": str(device),
        "dtype": str(next(model.parameters()).dtype),
        "load_time_seconds": round(elapsed, 1),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
    }
    logger.info(f"Model loaded in {elapsed:.1f}s on {device}")


@app.get("/health")
def health():
    return {
        "status": "ok" if model is not None else "loading",
        "model": model_info,
    }


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    if model is None:
        return GenerateResponse(text="Model not loaded", tokens_generated=0, time_seconds=0)

    inputs = tokenizer(
        req.prompt, return_tensors="pt", truncation=True, max_length=512
    )
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}
    input_len = inputs["input_ids"].shape[1]

    t0 = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=req.max_tokens,
            pad_token_id=tokenizer.pad_token_id,
            do_sample=True,
            temperature=req.temperature,
            top_k=req.top_k,
            top_p=req.top_p,
            repetition_penalty=req.repetition_penalty,
        )
    elapsed = time.time() - t0

    text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    prompt_text = tokenizer.decode(outputs[0][:input_len], skip_special_tokens=True)
    if text.startswith(prompt_text):
        text = text[len(prompt_text):].strip()

    tokens_generated = outputs.shape[1] - input_len

    return GenerateResponse(
        text=text or "I understand the question but need more context.",
        tokens_generated=tokens_generated,
        time_seconds=round(elapsed, 2),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Path to HuggingFace model dir or HF model name")
    parser.add_argument("--port", type=int, default=8080, help="Port to serve on")
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    load_model(args.model)

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)
PYEOF

echo "[3/4] Server script created at /workspace/ethos/inference_server.py"

# 4. Check GPU
echo "[4/4] Checking GPU..."
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"none\"}, VRAM: {torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB' if torch.cuda.is_available() else 'No GPU')"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Upload your model to /workspace/ (or use a HuggingFace model name)"
echo "  2. Start the server:"
echo "     python /workspace/ethos/inference_server.py --model /workspace/YOUR_MODEL --port 8080"
echo ""
echo "  Or download directly from HuggingFace:"
echo "     python /workspace/ethos/inference_server.py --model Orenguteng/Llama-3-8B-Lexi-Uncensored --port 8080"
echo ""
echo "  The server will be available at your RunPod proxy URL on port 8080"
