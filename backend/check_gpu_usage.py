"""
GPU Check Script — Verifies RTX GPU is ready for ETHOS AI Evaluator.
All inference runs on NVIDIA RTX GPU (CUDA device 0) only.
"""
import os

# Force only NVIDIA RTX GPU (not Intel UHD)
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import torch

print("=" * 60)
print("ETHOS AI Evaluator — GPU Check")
print("=" * 60)

if not torch.cuda.is_available():
    print("\n❌ CUDA NOT AVAILABLE!")
    print("This platform REQUIRES an NVIDIA RTX GPU.")
    print("Ensure CUDA drivers and torch+cuda are installed.")
    exit(1)

gpu_name = torch.cuda.get_device_name(0)
gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
gpu_free = (torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)) / 1024**3

print(f"\n✅ GPU Found: {gpu_name}")
print(f"   Total VRAM: {gpu_mem:.1f} GB")
print(f"   Free VRAM:  {gpu_free:.1f} GB")
print(f"   CUDA Version: {torch.version.cuda}")
print(f"   PyTorch: {torch.__version__}")
print(f"   Device Count: {torch.cuda.device_count()}")

# Quick GPU computation test
print(f"\n🔧 Running GPU compute test...")
x = torch.randn(1000, 1000, device="cuda:0")
y = torch.randn(1000, 1000, device="cuda:0")
z = torch.matmul(x, y)
torch.cuda.synchronize()
print(f"   ✅ Matrix multiply (1000x1000): OK")
print(f"   Result device: {z.device}")

allocated = torch.cuda.memory_allocated(0) / 1024**3
print(f"   VRAM after test: {allocated:.3f} GB")

# Cleanup
del x, y, z
torch.cuda.empty_cache()

print(f"\n{'=' * 60}")
print(f"🎮 GPU is ready for model inference!")
print(f"   Max model size (FP16): ~{gpu_mem * 0.85:.1f} GB")
print(f"{'=' * 60}")
