"""
Quick model downloader for ETHOS AI Evaluator
Pre-downloads models to avoid waiting during testing
"""
import sys
from pathlib import Path

def download_model(model_name: str, model_type: str = "causal"):
    """
    Download and cache a Hugging Face model
    
    Args:
        model_name: Hugging Face model identifier
        model_type: "causal" for GPT-style, "seq2seq" for T5-style
    """
    print(f"\n{'='*60}")
    print(f"Downloading: {model_name}")
    print(f"Type: {model_type}")
    print(f"{'='*60}\n")
    
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM, AutoModelForSeq2SeqLM
        import torch
        
        # Check GPU
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Device: {device}")
        
        if device == "cuda":
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"GPU: {gpu_name} ({gpu_mem:.1f} GB)\n")
        
        # Download tokenizer
        print("Downloading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        print("✅ Tokenizer downloaded")
        
        # Download model
        print(f"\nDownloading model (this may take a few minutes)...")
        if model_type == "seq2seq":
            model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        else:
            model = AutoModelForCausalLM.from_pretrained(model_name)
        
        print("✅ Model downloaded")
        
        # Test inference
        print("\nTesting model...")
        test_prompt = "Hello, how are you?"
        inputs = tokenizer(test_prompt, return_tensors="pt")
        
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=10)
        
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print(f"Test response: {response}")
        
        # Get model size
        param_count = sum(p.numel() for p in model.parameters())
        print(f"\n✅ Model ready!")
        print(f"Parameters: {param_count:,} ({param_count/1e6:.1f}M)")
        
        # Estimate VRAM usage
        if device == "cuda":
            model = model.to(device)
            allocated = torch.cuda.memory_allocated(0) / 1024**3
            print(f"Estimated VRAM usage: {allocated:.2f} GB")
        
        print(f"\n{'='*60}")
        print(f"✅ {model_name} is ready for testing!")
        print(f"{'='*60}\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check internet connection")
        print("2. Ensure enough disk space")
        print("3. Try a smaller model first")
        return False

def download_recommended_models():
    """Download all recommended models for RTX 4050"""
    models = [
        ("sshleifer/tiny-gpt2", "causal"),
        ("distilgpt2", "causal"),
        ("openai-community/gpt2", "causal"),
        ("google/flan-t5-base", "seq2seq"),
    ]
    
    print("\n" + "="*60)
    print("Downloading Recommended Models for RTX 4050 (6GB)")
    print("="*60)
    print("\nThis will download ~2GB of models")
    print("Models will be cached for offline use\n")
    
    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled")
        return
    
    success_count = 0
    for model_name, model_type in models:
        if download_model(model_name, model_type):
            success_count += 1
        print("\n" + "-"*60 + "\n")
    
    print(f"\n✅ Downloaded {success_count}/{len(models)} models successfully")
    print("\nYou can now run tests offline with:")
    print("  python test_local_gpu.py --model openai-community/gpt2 --prompts 25")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Download models for ETHOS AI Evaluator")
    parser.add_argument("--model", type=str, help="Specific model to download")
    parser.add_argument("--type", type=str, default="causal", choices=["causal", "seq2seq"],
                        help="Model type (causal for GPT, seq2seq for T5)")
    parser.add_argument("--all", action="store_true", help="Download all recommended models")
    
    args = parser.parse_args()
    
    if args.all:
        download_recommended_models()
    elif args.model:
        download_model(args.model, args.type)
    else:
        print("ETHOS AI Evaluator - Model Downloader")
        print("\nUsage:")
        print("  Download specific model:")
        print("    python download_models.py --model openai-community/gpt2")
        print("\n  Download all recommended models:")
        print("    python download_models.py --all")
        print("\nRecommended models for RTX 4050:")
        print("  - sshleifer/tiny-gpt2 (35MB, very fast)")
        print("  - distilgpt2 (350MB, fast)")
        print("  - openai-community/gpt2 (500MB, good quality)")
        print("  - google/flan-t5-base (1GB, very good quality)")
