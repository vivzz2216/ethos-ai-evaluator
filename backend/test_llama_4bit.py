"""
Test Llama-3-8B with 4-bit quantization on RTX 4050
WARNING: This will be SLOW but will fit in 6GB VRAM
"""
import time
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

def test_llama_4bit(model_name: str = "Orenguteng/Llama-3-8B-Lexi-Uncensored", num_prompts: int = 25):
    """
    Test Llama-3-8B with 4-bit quantization
    
    WARNING: This will be VERY SLOW (10-30 minutes for 25 prompts)
    """
    print("=" * 80)
    print("ETHOS AI Evaluator - Llama-3-8B Testing (4-bit Quantization)")
    print("=" * 80)
    print(f"\nModel: {model_name}")
    print(f"Prompts: {num_prompts}")
    print(f"Quantization: 4-bit (to fit in 6GB VRAM)")
    print("\n⚠️  WARNING: This will be VERY SLOW!")
    print("   Expected time: 10-30 minutes for 25 prompts")
    print("   Quality will be degraded due to 4-bit quantization")
    
    response = input("\nContinue? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled. Consider using a smaller model instead:")
        print("  - microsoft/phi-2 (2.7B, fast)")
        print("  - google/flan-t5-large (780M, very fast)")
        return
    
    # Check dependencies
    print("\n" + "-" * 80)
    print("Checking Dependencies...")
    print("-" * 80)
    
    try:
        import torch
        print(f"✅ PyTorch: {torch.__version__}")
    except ImportError:
        print("❌ PyTorch not installed")
        return
    
    try:
        import transformers
        print(f"✅ Transformers: {transformers.__version__}")
    except ImportError:
        print("❌ Transformers not installed")
        return
    
    try:
        import bitsandbytes
        print(f"✅ bitsandbytes: {bitsandbytes.__version__}")
    except ImportError:
        print("❌ bitsandbytes not installed")
        print("\nInstall with: pip install bitsandbytes accelerate")
        return
    
    try:
        import accelerate
        print(f"✅ accelerate: {accelerate.__version__}")
    except ImportError:
        print("❌ accelerate not installed")
        print("\nInstall with: pip install accelerate")
        return
    
    # Check GPU
    if not torch.cuda.is_available():
        print("\n❌ CUDA not available - cannot run Llama-3-8B")
        return
    
    gpu_name = torch.cuda.get_device_name(0)
    gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"\n✅ GPU: {gpu_name} ({gpu_mem:.1f} GB)")
    
    if gpu_mem < 5:
        print(f"\n❌ Insufficient VRAM: {gpu_mem:.1f} GB")
        print("   Llama-3-8B requires at least 5GB VRAM with 4-bit quantization")
        return
    
    print("\n" + "-" * 80)
    print("Loading Model (this will take several minutes)...")
    print("-" * 80)
    
    start_load = time.time()
    
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
        
        # Configure 4-bit quantization
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4"
        )
        
        print("Loading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        print("Loading model with 4-bit quantization...")
        print("(This may take 5-10 minutes on first download)")
        
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=quantization_config,
            device_map="auto",
            trust_remote_code=True
        )
        
        load_time = time.time() - start_load
        print(f"\n✅ Model loaded in {load_time:.2f} seconds")
        
        # Check memory usage
        allocated = torch.cuda.memory_allocated(0) / 1024**3
        reserved = torch.cuda.memory_reserved(0) / 1024**3
        print(f"GPU Memory Allocated: {allocated:.2f} GB")
        print(f"GPU Memory Reserved: {reserved:.2f} GB")
        
    except Exception as e:
        print(f"\n❌ Failed to load model: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure bitsandbytes is installed: pip install bitsandbytes")
        print("2. Check internet connection (first download)")
        print("3. Ensure enough disk space (~16GB for model)")
        return
    
    print("\n" + "-" * 80)
    print("Loading Test Dataset...")
    print("-" * 80)
    
    try:
        from ethos_testing.datasets import DatasetLoader
        from ethos_testing.evaluator import EthicalEvaluator
        
        dataset_loader = DatasetLoader("data")
        prompts = dataset_loader.load_ethical_dataset(num_samples=num_prompts)
        print(f"✅ Loaded {len(prompts)} ethical prompts")
    except Exception as e:
        print(f"❌ Failed to load dataset: {e}")
        return
    
    print("\n" + "-" * 80)
    print("Generating Responses (THIS WILL BE SLOW)...")
    print("-" * 80)
    
    evaluator = EthicalEvaluator()
    results = []
    
    start_inference = time.time()
    
    for i, prompt_data in enumerate(prompts, 1):
        prompt_text = prompt_data.get("prompt", "")
        category = prompt_data.get("category", "Unknown")
        
        print(f"\n[{i}/{len(prompts)}] Category: {category}")
        print(f"Prompt: {prompt_text[:80]}...")
        
        try:
            # Generate response
            response_start = time.time()
            
            inputs = tokenizer(prompt_text, return_tensors="pt").to("cuda")
            
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=100,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=tokenizer.eos_token_id
                )
            
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Remove prompt from response
            if response.startswith(prompt_text):
                response = response[len(prompt_text):].strip()
            
            response_time = time.time() - response_start
            
            print(f"Response ({response_time:.2f}s): {response[:100]}...")
            
            # Evaluate response
            eval_result = evaluator.evaluate_response(prompt_data, response)
            
            results.append({
                "prompt_id": prompt_data.get("id"),
                "category": category,
                "prompt": prompt_text,
                "response": response,
                "score": eval_result["score"],
                "aligned": eval_result["aligned"],
                "response_time": response_time,
                "evaluation": eval_result
            })
            
            score_emoji = "✅" if eval_result["aligned"] else "❌"
            print(f"{score_emoji} Score: {eval_result['score']:.2f}")
            
            # Estimate remaining time
            elapsed = time.time() - start_inference
            avg_time = elapsed / i
            remaining = avg_time * (len(prompts) - i)
            print(f"⏱️  Estimated time remaining: {remaining/60:.1f} minutes")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({
                "prompt_id": prompt_data.get("id"),
                "category": category,
                "error": str(e)
            })
    
    total_inference_time = time.time() - start_inference
    
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    
    successful = [r for r in results if "error" not in r]
    aligned = [r for r in successful if r.get("aligned", False)]
    
    print(f"\nTotal Prompts: {len(prompts)}")
    print(f"Successful: {len(successful)}")
    print(f"Aligned Responses: {len(aligned)} ({len(aligned)/len(successful)*100:.1f}%)")
    
    if successful:
        avg_score = sum(r["score"] for r in successful) / len(successful)
        avg_time = sum(r["response_time"] for r in successful) / len(successful)
        print(f"Average Score: {avg_score:.3f}")
        print(f"Average Response Time: {avg_time:.2f}s")
        print(f"Total Inference Time: {total_inference_time/60:.2f} minutes")
        print(f"Throughput: {len(successful)/total_inference_time:.3f} prompts/second")
    
    # Save results
    output_file = Path("test_results_llama3_8b_4bit.json")
    with open(output_file, "w") as f:
        json.dump({
            "model": model_name,
            "quantization": "4-bit",
            "num_prompts": len(prompts),
            "results": results,
            "summary": {
                "total": len(prompts),
                "successful": len(successful),
                "aligned": len(aligned),
                "avg_score": avg_score if successful else 0,
                "avg_response_time": avg_time if successful else 0,
                "total_time_minutes": total_inference_time / 60,
                "load_time": load_time
            }
        }, f, indent=2)
    
    print(f"\n✅ Results saved to: {output_file.absolute()}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Llama-3-8B with 4-bit quantization")
    parser.add_argument("--model", type=str, default="Orenguteng/Llama-3-8B-Lexi-Uncensored",
                        help="Llama model name")
    parser.add_argument("--prompts", type=int, default=25,
                        help="Number of prompts to test")
    
    args = parser.parse_args()
    
    test_llama_4bit(model_name=args.model, num_prompts=args.prompts)
