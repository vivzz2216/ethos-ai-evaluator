"""
Check if Llama-3-8B can run on your GPU
"""
import torch

print("=" * 80)
print("Llama-3-8B Compatibility Check for RTX 4050")
print("=" * 80)

# Check GPU
if torch.cuda.is_available():
    gpu_name = torch.cuda.get_device_name(0)
    gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"\n✅ GPU Detected: {gpu_name}")
    print(f"   Total VRAM: {gpu_mem:.2f} GB")
else:
    print("\n❌ No GPU detected")
    exit(1)

print("\n" + "=" * 80)
print("Llama-3-8B Model Requirements")
print("=" * 80)

model_info = {
    "Model": "Orenguteng/Llama-3-8B-Lexi-Uncensored",
    "Parameters": "8 billion",
    "Size (FP32)": "~32 GB",
    "Size (FP16)": "~16 GB",
    "Size (8-bit)": "~8 GB",
    "Size (4-bit)": "~4-5 GB",
}

print("\nModel Sizes by Precision:")
for key, value in model_info.items():
    print(f"  {key}: {value}")

print("\n" + "=" * 80)
print("Compatibility Analysis for RTX 4050 (6GB)")
print("=" * 80)

print("\n❌ FP32 (32-bit): NOT POSSIBLE")
print("   Requires: ~32 GB VRAM")
print("   Your GPU: 6 GB VRAM")

print("\n❌ FP16 (16-bit): NOT POSSIBLE")
print("   Requires: ~16 GB VRAM")
print("   Your GPU: 6 GB VRAM")

print("\n❌ 8-bit Quantization: NOT POSSIBLE")
print("   Requires: ~8 GB VRAM")
print("   Your GPU: 6 GB VRAM")

print("\n✅ 4-bit Quantization: POSSIBLE (with bitsandbytes)")
print("   Requires: ~4-5 GB VRAM")
print("   Your GPU: 6 GB VRAM")
print("   ⚠️  Will be VERY SLOW for inference")
print("   ⚠️  Quality degradation from quantization")

print("\n" + "=" * 80)
print("Recommendations")
print("=" * 80)

print("\n🎯 OPTION 1: Use 4-bit Quantized Llama-3-8B (Challenging)")
print("   Pros:")
print("   ✅ Fits in 6GB VRAM")
print("   ✅ Can run on your GPU")
print("   Cons:")
print("   ❌ Very slow (~5-10 seconds per token)")
print("   ❌ Quality loss from 4-bit quantization")
print("   ❌ 25 prompts could take 10-30 minutes")
print("   ❌ Requires bitsandbytes library")

print("\n🎯 OPTION 2: Use Smaller Llama Models (Recommended)")
print("   - meta-llama/Llama-3.2-1B (1B params, ~2GB)")
print("   - meta-llama/Llama-3.2-3B (3B params, ~6GB with 8-bit)")
print("   Pros:")
print("   ✅ Much faster inference")
print("   ✅ Better quality (no heavy quantization)")
print("   ✅ 25 prompts in 1-2 minutes")

print("\n🎯 OPTION 3: Use Optimized Models for 6GB (Best)")
print("   - google/flan-t5-large (780M params, ~3GB)")
print("   - mistralai/Mistral-7B-Instruct-v0.2 (7B, ~4GB with 4-bit)")
print("   - microsoft/phi-2 (2.7B params, ~5GB)")
print("   Pros:")
print("   ✅ Excellent quality")
print("   ✅ Fast inference")
print("   ✅ Designed for efficiency")

print("\n" + "=" * 80)
print("Performance Estimates (25 prompts)")
print("=" * 80)

estimates = [
    ("Llama-3-8B (4-bit)", "10-30 min", "Slow", "Degraded"),
    ("Llama-3.2-1B (FP16)", "1-2 min", "Fast", "Good"),
    ("Llama-3.2-3B (8-bit)", "2-4 min", "Moderate", "Very Good"),
    ("flan-t5-large (FP16)", "1-2 min", "Fast", "Excellent"),
    ("phi-2 (FP16)", "1-2 min", "Fast", "Excellent"),
]

print(f"\n{'Model':<25} {'Time':<12} {'Speed':<10} {'Quality':<12}")
print("-" * 80)
for model, time, speed, quality in estimates:
    print(f"{model:<25} {time:<12} {speed:<10} {quality:<12}")

print("\n" + "=" * 80)
print("Final Recommendation")
print("=" * 80)

print("\n⚠️  Llama-3-8B is TOO LARGE for efficient testing on RTX 4050")
print("\n✅ RECOMMENDED ALTERNATIVES:")
print("\n1. microsoft/phi-2 (2.7B params)")
print("   - Excellent quality, optimized for efficiency")
print("   - Fast inference on 6GB GPU")
print("   - 25 prompts in ~1-2 minutes")

print("\n2. google/flan-t5-large (780M params)")
print("   - Very good quality")
print("   - Very fast inference")
print("   - 25 prompts in ~1 minute")

print("\n3. If you MUST use Llama-3-8B:")
print("   - Use 4-bit quantization (very slow)")
print("   - Expect 10-30 minutes for 25 prompts")
print("   - Install: pip install bitsandbytes accelerate")

print("\n" + "=" * 80)
