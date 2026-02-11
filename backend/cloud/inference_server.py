"""
Dynamic inference server for RunPod GPU pod.
Supports loading/swapping models on demand via /load endpoint.
One model at a time — previous model is unloaded before loading a new one.

Usage on RunPod:
    pip install fastapi uvicorn torch transformers accelerate
    python inference_server.py --port 8080
    python inference_server.py --model Orenguteng/Llama-3-8B-Lexi-Uncensored --port 8080
"""
import argparse
import gc
import json
import logging
import os
import shutil
import threading
import time
import uuid
import torch
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inference_server")

app = FastAPI(title="ETHOS Cloud Inference")

model = None
tokenizer = None
model_info = {}
_loading = False
_adapter_loaded = False
_adapter_path = None
_base_model_ref = None

_train_job = {
    "id": None,
    "thread": None,
    "status": "idle",
    "error": None,
}


class LoadRequest(BaseModel):
    model_name: str
    load_in_8bit: bool = False


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
    """Free the current model from GPU/CPU memory."""
    global model, tokenizer, model_info
    if model is not None:
        logger.info(f"Unloading model: {model_info.get('model_name', '?')}")
        del model
        model = None
    if tokenizer is not None:
        del tokenizer
        tokenizer = None
    model_info = {}
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    logger.info("Model unloaded, memory freed")


def _do_load(model_name: str, load_8bit: bool = False):
    """Download (if needed) and load a model onto the GPU."""
    global model, tokenizer, model_info, _loading, _adapter_loaded, _adapter_path, _base_model_ref
    _loading = True

    try:
        _unload()

        logger.info(f"Loading model: {model_name} ...")
        t0 = time.time()

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        if tokenizer.pad_token is None and tokenizer.eos_token:
            tokenizer.pad_token = tokenizer.eos_token

        config = AutoConfig.from_pretrained(model_name)
        is_seq2seq = getattr(config, "model_type", "") == "t5"

        if is_seq2seq:
            from transformers import AutoModelForSeq2SeqLM
            auto_cls = AutoModelForSeq2SeqLM
        else:
            auto_cls = AutoModelForCausalLM

        if torch.cuda.is_available():
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}, VRAM: {gpu_mem:.1f}GB")

            if load_8bit:
                try:
                    from transformers import BitsAndBytesConfig
                    bnb_config = BitsAndBytesConfig(load_in_8bit=True, llm_int8_threshold=6.0)
                    model = auto_cls.from_pretrained(
                        model_name,
                        quantization_config=bnb_config,
                        device_map="auto",
                        low_cpu_mem_usage=True,
                    )
                    logger.info("Model loaded in 8-bit quantization")
                except ImportError:
                    logger.warning("bitsandbytes not installed, falling back to float16")
                    model = auto_cls.from_pretrained(
                        model_name,
                        torch_dtype=torch.float16,
                        device_map="auto",
                        low_cpu_mem_usage=True,
                    )
            else:
                model = auto_cls.from_pretrained(
                    model_name,
                    torch_dtype=torch.float16,
                    device_map="auto",
                    low_cpu_mem_usage=True,
                )
        else:
            logger.warning("No GPU detected, loading on CPU (slow)")
            model = auto_cls.from_pretrained(model_name, low_cpu_mem_usage=True)

        model.eval()
        elapsed = time.time() - t0
        device = next(model.parameters()).device

        _adapter_loaded = False
        _adapter_path = None
        _base_model_ref = None

        model_info = {
            "model_name": model_name,
            "device": str(device),
            "dtype": str(next(model.parameters()).dtype),
            "load_time_seconds": round(elapsed, 1),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
            "quantization": "8bit" if load_8bit else "float16",
            "adapter": None,
        }
        logger.info(f"Model loaded in {elapsed:.1f}s on {device}")
    finally:
        _loading = False


@app.get("/health")
def health():
    if _loading:
        status = "loading"
    elif model is not None:
        status = "ok"
    else:
        status = "no_model"
    return {"status": status, "model": model_info}


@app.post("/load")
def load_model_endpoint(req: LoadRequest):
    """Load a new model (unloads previous one first). Accepts HF name or local path."""
    current = model_info.get("model_name", "")
    if current == req.model_name and model is not None:
        return {"status": "already_loaded", "model": model_info}

    try:
        _do_load(req.model_name, load_8bit=req.load_in_8bit)
        return {"status": "loaded", "model": model_info}
    except Exception as e:
        logger.error(f"Failed to load {req.model_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/unload")
def unload_model_endpoint():
    """Unload the current model and free GPU memory."""
    _unload()
    return {"status": "unloaded"}


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="No model loaded. Call /load first with a model name.",
        )

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


# ═══════════════════════════════════════════════════════════════════════════
# LoRA ADAPTER ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


class LoadAdapterRequest(BaseModel):
    adapter_path: str


class TrainRequest(BaseModel):
    base_model: str
    dataset_path: str = "/workspace/ethics_patch.jsonl"
    output_dir: str = "/workspace/adapters/round_1"
    epochs: int = 3
    lr: float = 2e-4
    batch_size: int = 4
    lora_r: int = 8
    lora_alpha: int = 32


@app.post("/upload_patch")
async def upload_patch(file: UploadFile = File(...)):
    """Receive an ethics_patch.jsonl file from the local backend."""
    dest = "/workspace/ethics_patch.jsonl"
    try:
        os.makedirs("/workspace", exist_ok=True)
        content = await file.read()
        with open(dest, "wb") as f:
            f.write(content)
        line_count = content.decode("utf-8", errors="ignore").strip().count("\n") + 1
        logger.info(f"Received patch file: {dest} ({line_count} entries, {len(content)} bytes)")
        return {"status": "uploaded", "path": dest, "entries": line_count, "bytes": len(content)}
    except Exception as e:
        logger.error(f"Failed to save patch file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/load_adapter")
def load_adapter_endpoint(req: LoadAdapterRequest):
    """Load a PEFT LoRA adapter on top of the current base model."""
    global model, _adapter_loaded, _adapter_path, _base_model_ref, model_info

    if model is None:
        raise HTTPException(status_code=400, detail="No base model loaded. Call /load first.")

    if not os.path.exists(req.adapter_path):
        raise HTTPException(status_code=404, detail=f"Adapter not found: {req.adapter_path}")

    try:
        from peft import PeftModel

        if _adapter_loaded and _base_model_ref is not None:
            logger.info("Unloading previous adapter, reverting to base model")
            model = _base_model_ref
            _adapter_loaded = False

        _base_model_ref = model

        logger.info(f"Loading LoRA adapter from {req.adapter_path}")
        t0 = time.time()
        model = PeftModel.from_pretrained(_base_model_ref, req.adapter_path)
        model.eval()
        elapsed = time.time() - t0

        _adapter_loaded = True
        _adapter_path = req.adapter_path
        model_info["adapter"] = req.adapter_path
        model_info["adapter_load_time"] = round(elapsed, 1)

        logger.info(f"Adapter loaded in {elapsed:.1f}s")
        return {
            "status": "adapter_loaded",
            "adapter_path": req.adapter_path,
            "load_time_seconds": round(elapsed, 1),
            "model": model_info,
        }
    except ImportError:
        raise HTTPException(status_code=500, detail="peft not installed. Run: pip install peft")
    except Exception as e:
        logger.error(f"Failed to load adapter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/unload_adapter")
def unload_adapter_endpoint():
    """Remove the LoRA adapter, revert to base model."""
    global model, _adapter_loaded, _adapter_path, _base_model_ref, model_info

    if not _adapter_loaded:
        return {"status": "no_adapter", "message": "No adapter is currently loaded"}

    if _base_model_ref is not None:
        model = _base_model_ref
        _base_model_ref = None
    _adapter_loaded = False
    _adapter_path = None
    model_info["adapter"] = None

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    logger.info("Adapter unloaded, reverted to base model")
    return {"status": "adapter_unloaded", "model": model_info}


def _run_training(job_id: str, req: TrainRequest):
    """Background thread for LoRA training."""
    global _train_job
    try:
        _train_job["status"] = "running"
        logger.info(f"Training job {job_id} started")

        from train_lora import train
        result = train(
            base_model=req.base_model,
            dataset_path=req.dataset_path,
            output_dir=req.output_dir,
            epochs=req.epochs,
            lr=req.lr,
            batch_size=req.batch_size,
            lora_r=req.lora_r,
            lora_alpha=req.lora_alpha,
        )

        _train_job["status"] = "completed"
        _train_job["result"] = result
        logger.info(f"Training job {job_id} completed: loss={result.get('train_loss')}")
    except Exception as e:
        _train_job["status"] = "failed"
        _train_job["error"] = str(e)
        logger.error(f"Training job {job_id} failed: {e}")


@app.post("/train")
def start_training(req: TrainRequest):
    """Start a LoRA training job in a background thread."""
    global _train_job

    if _train_job["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail=f"Training job {_train_job['id']} is already running"
        )

    if not os.path.exists(req.dataset_path):
        raise HTTPException(
            status_code=404,
            detail=f"Dataset not found: {req.dataset_path}. Upload it via /upload_patch first."
        )

    job_id = str(uuid.uuid4())[:8]
    _train_job = {
        "id": job_id,
        "status": "starting",
        "error": None,
        "result": None,
        "config": req.model_dump(),
    }

    thread = threading.Thread(target=_run_training, args=(job_id, req), daemon=True)
    thread.start()
    _train_job["thread"] = thread

    logger.info(f"Training job {job_id} queued")
    return {"status": "started", "job_id": job_id, "config": req.model_dump()}


@app.get("/train_status")
def train_status():
    """Poll training job progress."""
    disk_status = {}
    status_file = "/workspace/train_status.json"
    if os.path.exists(status_file):
        try:
            with open(status_file, "r") as f:
                disk_status = json.load(f)
        except Exception:
            pass

    return {
        "job_id": _train_job.get("id"),
        "status": _train_job.get("status", "idle"),
        "error": _train_job.get("error"),
        "result": _train_job.get("result"),
        "progress": disk_status,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None, help="Optional: preload a model on startup")
    parser.add_argument("--port", type=int, default=8080, help="Port to serve on")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--8bit", dest="load_8bit", action="store_true", help="Load model in 8-bit")
    args = parser.parse_args()

    if args.model:
        _do_load(args.model, load_8bit=args.load_8bit)

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)
