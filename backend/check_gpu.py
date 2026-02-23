"""
GPU and PyTorch capability checker for ETHOS AI Evaluator
"""
import sys

def check_gpu():
    print("=" * 60)
    print("ETHOS AI Evaluator - GPU Capability Check")
    print("=" * 60)
    
    # Check PyTorch
    try:
        import torch
        print(f"\n✅ PyTorch installed: {torch.__version__}")
        
        # Check CUDA
        cuda_available = torch.cuda.is_available()
        print(f"CUDA available: {cuda_available}")
        
        if cuda_available:
            print(f"CUDA version: {torch.version.cuda}")
            print(f"GPU count: {torch.cuda.device_count()}")
            
            for i in range(torch.cuda.device_count()):
                print(f"\nGPU {i}: {torch.cuda.get_device_name(i)}")
                props = torch.cuda.get_device_properties(i)
                print(f"  Total Memory: {props.total_memory / 1024**3:.2f} GB")
                print(f"  Compute Capability: {props.major}.{props.minor}")
                
                # Check current memory usage
                allocated = torch.cuda.memory_allocated(i) / 1024**3
                reserved = torch.cuda.memory_reserved(i) / 1024**3
                print(f"  Memory Allocated: {allocated:.2f} GB")
                print(f"  Memory Reserved: {reserved:.2f} GB")
                print(f"  Memory Free: {(props.total_memory / 1024**3) - reserved:.2f} GB")
        else:
            print("\n⚠️  No CUDA GPU detected - will use CPU (slower)")
            
    except ImportError:
        print("\n❌ PyTorch not installed")
        print("Install with: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")
        return False
    
    # Check Transformers
    try:
        import transformers
        print(f"\n✅ Transformers installed: {transformers.__version__}")
    except ImportError:
        print("\n❌ Transformers not installed")
        print("Install with: pip install transformers")
        return False
    
    # Estimate model requirements
    print("\n" + "=" * 60)
    print("Recommended Models for Local Testing")
    print("=" * 60)
    
    if cuda_available:
        total_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"\nYour GPU has {total_mem:.2f} GB VRAM")
        
        if total_mem >= 24:
            print("\n✅ Excellent! You can run large models:")
            print("  - meta-llama/Llama-2-7b-chat-hf (7B params, ~14GB)")
            print("  - mistralai/Mistral-7B-Instruct-v0.2 (7B params, ~14GB)")
            print("  - google/flan-t5-large (780M params, ~3GB)")
        elif total_mem >= 12:
            print("\n✅ Good! You can run medium models:")
            print("  - google/flan-t5-large (780M params, ~3GB)")
            print("  - openai-community/gpt2-medium (355M params, ~1.5GB)")
            print("  - facebook/opt-1.3b (1.3B params, ~5GB)")
        elif total_mem >= 6:
            print("\n✅ You can run small-medium models:")
            print("  - google/flan-t5-base (250M params, ~1GB)")
            print("  - openai-community/gpt2 (124M params, ~500MB)")
            print("  - distilgpt2 (82M params, ~350MB)")
        else:
            print("\n⚠️  Limited VRAM - use tiny models:")
            print("  - sshleifer/tiny-gpt2 (~35MB)")
            print("  - distilgpt2 (82M params, ~350MB)")
    else:
        print("\nCPU-only mode - recommended models:")
        print("  - sshleifer/tiny-gpt2 (fast, ~35MB)")
        print("  - distilgpt2 (moderate, 82M params)")
        print("  - openai-community/gpt2 (slower, 124M params)")
    
    print("\n" + "=" * 60)
    print("Testing Configuration")
    print("=" * 60)
    print("\nFor 25 prompt testing:")
    print("  - Estimated time (GPU): 30 seconds - 2 minutes")
    print("  - Estimated time (CPU): 2-5 minutes")
    print("  - Memory required: Model size + 1-2GB overhead")
    
    return True

if __name__ == "__main__":
    check_gpu()
