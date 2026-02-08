"""Direct test: find a loading strategy that works on RTX 4050 (6.4GB VRAM)."""
import os, sys, time, gc
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig, BitsAndBytesConfig

MODEL_PATH = r"C:\Llama-3-8B-Lexi-Uncensored"

def free():
    gc.collect()
    torch.cuda.empty_cache()

def vram():
    f, t = torch.cuda.mem_get_info()
    return f"{f/1e9:.1f}/{t/1e9:.1f}GB"

def test_generate(model, tok):
    prompt = "What is 2 + 2? Answer in one sentence."
    inputs = tok(prompt, return_tensors="pt", truncation=True, max_length=512)
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(
            **inputs, max_new_tokens=60, pad_token_id=tok.pad_token_id,
            do_sample=True, temperature=0.7, top_k=50, top_p=0.9,
            repetition_penalty=1.2,
        )
    elapsed = time.time() - t0
    resp = tok.decode(out[0], skip_special_tokens=True)
    if resp.startswith(prompt):
        resp = resp[len(prompt):].strip()
    return resp, elapsed

print(f"VRAM: {vram()}")
tok = AutoTokenizer.from_pretrained(MODEL_PATH)
if tok.pad_token is None and tok.eos_token:
    tok.pad_token = tok.eos_token

# Strategy A: 4-bit with CPU offload flag
print("\n=== Strategy A: 4-bit NF4 + cpu_offload flag ===")
free()
try:
    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        llm_int8_enable_fp32_cpu_offload=True,
    )
    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH, quantization_config=quant, device_map="auto",
        low_cpu_mem_usage=True,
    )
    print(f"Loaded in {time.time()-t0:.1f}s, VRAM: {vram()}")
    print(f"Device map: {model.hf_device_map}")
    resp, dur = test_generate(model, tok)
    print(f"Generated in {dur:.1f}s: {resp[:200]}")
    del model; free()
    print("=== SUCCESS ===")
    sys.exit(0)
except Exception as e:
    print(f"FAILED: {e}")
    free()

# Strategy B: 4-bit with custom device_map (lm_head on CPU)
print("\n=== Strategy B: 4-bit NF4 + custom device_map ===")
free()
try:
    from accelerate import infer_auto_device_map, init_empty_weights
    config = AutoConfig.from_pretrained(MODEL_PATH)
    with init_empty_weights():
        empty = AutoModelForCausalLM.from_config(config)
    # Compute device map, let most go to GPU
    device_map = infer_auto_device_map(
        empty,
        max_memory={0: "5GiB", "cpu": "16GiB"},
        no_split_module_classes=["LlamaDecoderLayer"],
    )
    # Ensure lm_head is on cpu (non-quantized, fp16)
    if "lm_head" in device_map:
        device_map["lm_head"] = "cpu"
    print(f"Custom device_map lm_head={device_map.get('lm_head')}")
    del empty

    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        llm_int8_enable_fp32_cpu_offload=True,
    )
    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH, quantization_config=quant, device_map=device_map,
        low_cpu_mem_usage=True,
    )
    print(f"Loaded in {time.time()-t0:.1f}s, VRAM: {vram()}")
    resp, dur = test_generate(model, tok)
    print(f"Generated in {dur:.1f}s: {resp[:200]}")
    del model; free()
    print("=== SUCCESS ===")
    sys.exit(0)
except Exception as e:
    print(f"FAILED: {e}")
    free()

# Strategy C: 8-bit with CPU offload
print("\n=== Strategy C: 8-bit Int8 + CPU offload ===")
free()
try:
    quant = BitsAndBytesConfig(
        load_in_8bit=True,
        llm_int8_enable_fp32_cpu_offload=True,
    )
    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH, quantization_config=quant, device_map="auto",
        low_cpu_mem_usage=True,
    )
    print(f"Loaded in {time.time()-t0:.1f}s, VRAM: {vram()}")
    resp, dur = test_generate(model, tok)
    print(f"Generated in {dur:.1f}s: {resp[:200]}")
    del model; free()
    print("=== SUCCESS ===")
    sys.exit(0)
except Exception as e:
    print(f"FAILED: {e}")

print("\nAll strategies failed!")

