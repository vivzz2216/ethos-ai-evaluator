# RunPod Cloud Inference Setup

## Architecture
```
Your PC (local)                       RunPod Pod (cloud GPU)
┌──────────────────┐    HTTP API    ┌──────────────────────┐
│ Frontend (React) │ ◄──────────► │ inference_server.py   │
│ Backend (app.py) │               │ Dynamic model loading │
│                  │               │ /load → /generate     │
│ User types HF    │               │ 24GB+ VRAM            │
│ model name       │               │                       │
└──────────────────┘               └──────────────────────┘
```

Users type a HuggingFace model name in the frontend → backend tells RunPod to
download & load it → ethics tests run on cloud GPU. One model at a time, swap on demand.

## Step 1: Open RunPod Web Terminal

Go to your RunPod pod → click **"Open web terminal"** (port 19123)

## Step 2: Install Dependencies

```bash
pip install fastapi uvicorn torch transformers accelerate httpx
```

## Step 3: Create the Inference Server

Paste this entire block into the terminal:

```bash
cat > /workspace/inference_server.py << 'PYEOF'
import argparse, gc, logging, time, torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inference_server")
app = FastAPI(title="ETHOS Cloud Inference")
model = None
tokenizer = None
model_info = {}
_loading = False

class LoadRequest(BaseModel):
    model_name: str

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

def _unload():
    global model, tokenizer, model_info
    if model is not None:
        logger.info(f"Unloading: {model_info.get('model_name','?')}")
        del model
        model = None
    if tokenizer is not None:
        del tokenizer
        tokenizer = None
    model_info = {}
    gc.collect()
    if torch.cuda.is_available(): torch.cuda.empty_cache()

def _do_load(model_name):
    global model, tokenizer, model_info, _loading
    _loading = True
    try:
        _unload()
        logger.info(f"Loading: {model_name} ...")
        t0 = time.time()
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        if tokenizer.pad_token is None and tokenizer.eos_token:
            tokenizer.pad_token = tokenizer.eos_token
        auto_cls = AutoModelForCausalLM
        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_properties(0).total_memory/1e9
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}, VRAM: {gpu:.1f}GB")
            model = auto_cls.from_pretrained(model_name, torch_dtype=torch.float16, device_map="auto", low_cpu_mem_usage=True)
        else:
            model = auto_cls.from_pretrained(model_name, low_cpu_mem_usage=True)
        model.eval()
        elapsed = time.time() - t0
        device = next(model.parameters()).device
        model_info = {"model_name": model_name, "device": str(device), "dtype": str(next(model.parameters()).dtype), "load_time_seconds": round(elapsed,1), "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"}
        logger.info(f"Loaded in {elapsed:.1f}s on {device}")
    finally:
        _loading = False

@app.get("/health")
def health():
    s = "loading" if _loading else ("ok" if model else "no_model")
    return {"status": s, "model": model_info}

@app.post("/load")
def load_ep(req: LoadRequest):
    cur = model_info.get("model_name","")
    if cur == req.model_name and model is not None:
        return {"status": "already_loaded", "model": model_info}
    try:
        _do_load(req.model_name)
        return {"status": "loaded", "model": model_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/unload")
def unload_ep():
    _unload()
    return {"status": "unloaded"}

@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    if model is None:
        raise HTTPException(503, "No model loaded. Call /load first.")
    inputs = tokenizer(req.prompt, return_tensors="pt", truncation=True, max_length=512)
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}
    input_len = inputs["input_ids"].shape[1]
    t0 = time.time()
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=req.max_tokens, pad_token_id=tokenizer.pad_token_id, do_sample=True, temperature=req.temperature, top_k=req.top_k, top_p=req.top_p, repetition_penalty=req.repetition_penalty)
    elapsed = time.time() - t0
    text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    prompt_text = tokenizer.decode(outputs[0][:input_len], skip_special_tokens=True)
    if text.startswith(prompt_text): text = text[len(prompt_text):].strip()
    return GenerateResponse(text=text or "No response.", tokens_generated=outputs.shape[1]-input_len, time_seconds=round(elapsed,2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None, help="Optional: preload a model")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    if args.model: _do_load(args.model)
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)
PYEOF
```

## Step 4: Start the Server

```bash
# Start empty (models loaded on demand via /load endpoint):
python /workspace/inference_server.py --port 8080

# Or preload a model on startup:
python /workspace/inference_server.py --model Orenguteng/Llama-3-8B-Lexi-Uncensored --port 8080
```

## Step 5: Expose Port 8080

In RunPod dashboard → your pod → **Edit Pod** → add `8080` to "Expose HTTP Ports" → Save.

Your URL: `https://{POD_ID}-8080.proxy.runpod.net`

Find it under: Pod → Connect → HTTP Services → Port 8080

## Step 6: Start Local Backend

```powershell
$env:REMOTE_MODEL_URL = "https://fkmfgye99lt9oq-8080.proxy.runpod.net/"
cd C:\Users\ACER\Desktop\ethos-ai-evaluator-main\backend
python app.py
```

## Step 7: Test

1. Open ETHOS frontend
2. Enter a HuggingFace model name (e.g. `Orenguteng/Llama-3-8B-Lexi-Uncensored`)
3. Click "Test Model"
4. Backend tells RunPod to download & load the model (~30s on first use)
5. Ethics tests run on cloud GPU (~2-5 min for 25 prompts)

To test a different model, just enter a new name — the server unloads the old one and loads the new one automatically.

## API Endpoints (on RunPod)

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Server status + loaded model info |
| `/load` | POST | Load a model: `{"model_name": "org/model", "load_in_8bit": false}` |
| `/unload` | POST | Unload current model, free GPU |
| `/generate` | POST | Generate text from prompt |
| `/upload_patch` | POST | Upload `ethics_patch.jsonl` (multipart file) |
| `/load_adapter` | POST | Load LoRA adapter: `{"adapter_path": "/workspace/adapters/round_1/adapter"}` |
| `/unload_adapter` | POST | Remove adapter, revert to base model |
| `/train` | POST | Start LoRA training job (background thread) |
| `/train_status` | GET | Poll training progress (epoch, loss, status) |

## LoRA Training Setup (additional dependencies)

```bash
pip install peft bitsandbytes accelerate datasets trl
```

Copy `train_lora.py` to `/workspace/` on the RunPod pod (it's imported by the inference server's `/train` endpoint).

## Troubleshooting

- **Port 8080 not showing?** Edit Pod → add 8080 to HTTP ports
- **Health check:** Visit `https://{POD_ID}-8080.proxy.runpod.net/health`
- **Model too large?** Use a pod with more VRAM (A100 80GB for 70B models)
- **Training fails?** Check `/train_status` for error details. Ensure `bitsandbytes` is installed.
