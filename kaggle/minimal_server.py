"""
Minimal Kaggle Inference Server
Loads model with 4-bit quantization to save memory
"""

import os
import sys
import time
import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import torch
from transformers import AutoTokenizer, AutoConfig, AutoModelForCausalLM
from pyngrok import ngrok

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
model = None
tokenizer = None
model_info = {}

# Pydantic models
class LoadRequest(BaseModel):
    model_name: str
    load_8bit: bool = False

class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.7
    top_k: int = 50
    top_p: float = 0.9
    repetition_penalty: float = 1.2

class GenerateResponse(BaseModel):
    text: str
    tokens_generated: int
    time_seconds: float

# FastAPI app
app = FastAPI(title="ETHOS Minimal Inference Server")

def _unload():
    """Unload model and free GPU memory."""
    global model, tokenizer, model_info
    if model is not None:
        del model
        del tokenizer
        torch.cuda.empty_cache()
        model = None
        tokenizer = None
        model_info = {}
        logger.info("Model unloaded")

def _do_load(model_name: str, load_4bit: bool = True):
    """Load model with 4-bit quantization to save memory."""
    global model, tokenizer, model_info
    
    _unload()
    
    logger.info(f"Loading model: {model_name} ...")
    t0 = time.time()
    
    try:
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        if tokenizer.pad_token is None and tokenizer.eos_token:
            tokenizer.pad_token = tokenizer.eos_token
        
        # Load model with 4-bit quantization
        if torch.cuda.is_available():
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}, VRAM: {gpu_mem:.1f}GB")
            
            if load_4bit:
                try:
                    from transformers import BitsAndBytesConfig
                    bnb_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.float16,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4"
                    )
                    model = AutoModelForCausalLM.from_pretrained(
                        model_name,
                        quantization_config=bnb_config,
                        device_map="auto",
                        low_cpu_mem_usage=True,
                    )
                    logger.info("Model loaded in 4-bit quantization")
                except ImportError:
                    logger.warning("bitsandbytes not installed, falling back to float16")
                    model = AutoModelForCausalLM.from_pretrained(
                        model_name,
                        torch_dtype=torch.float16,
                        device_map="auto",
                        low_cpu_mem_usage=True,
                    )
            else:
                model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    torch_dtype=torch.float16,
                    device_map="auto",
                    low_cpu_mem_usage=True,
                )
        else:
            logger.warning("No GPU detected")
            model = AutoModelForCausalLM.from_pretrained(model_name, low_cpu_mem_usage=True)
        
        model.eval()
        elapsed = time.time() - t0
        device = next(model.parameters()).device
        
        model_info = {
            "model_name": model_name,
            "device": str(device),
            "dtype": str(next(model.parameters()).dtype),
            "load_time_seconds": round(elapsed, 1),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
            "quantization": "4bit" if load_4bit else "float16",
        }
        
        logger.info(f"Model loaded in {elapsed:.1f}s on {device}")
        
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise

# Endpoints
@app.get("/health")
def health():
    """Check if server is healthy."""
    return {
        "status": "healthy",
        "model_info": model_info
    }

@app.post("/load")
def load_model(req: LoadRequest):
    """Load a model."""
    try:
        _do_load(req.model_name, load_4bit=True)
        return {
            "status": "loaded",
            "model": model_info
        }
    except Exception as e:
        logger.error(f"Load error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    """Generate text."""
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="No model loaded. Call /load first."
        )
    
    try:
        inputs = tokenizer(
            req.prompt, 
            return_tensors="pt", 
            truncation=True, 
            max_length=512
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
    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Start server
if __name__ == "__main__":
    # Start uvicorn in background
    import threading
    
    def run_server():
        uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to start
    time.sleep(5)
    
    # Create ngrok tunnel
    public_url = ngrok.connect(8080, bind_tls=True)
    
    print("\n" + "="*80)
    print("🚀 MINIMAL ETHOS SERVER RUNNING ON KAGGLE")
    print("="*80)
    print(f"\n📡 Public URL: {public_url.public_url}")
    print(f"\n⚠️  COPY THIS URL TO YOUR LOCAL backend/.env FILE:")
    print(f"\n   REMOTE_MODEL_URL={public_url.public_url}")
    print("\n" + "="*80)
    print("\n✅ Server Status:")
    print("   - Model loading: Ready (4-bit quantization)")
    print("   - Inference: Ready")
    print("   - Memory usage: Optimized for Kaggle T4")
    print("\n💡 Keep this notebook running while testing.")
    print("="*80)
