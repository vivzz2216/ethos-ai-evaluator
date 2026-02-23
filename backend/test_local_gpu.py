"""
Local Model Testing Script for ETHOS AI Evaluator
Tests 25 prompts with a locally downloaded model on GPU
"""
import time
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from ethos_testing.local_model import get_model
from ethos_testing.datasets import DatasetLoader
from ethos_testing.evaluator import EthicalEvaluator

def test_local_model_gpu(model_name: str = "openai-community/gpt2", num_prompts: int = 25):
    """
    Test a local model with ethical prompts on GPU
    
    Args:
        model_name: Hugging Face model identifier (will be downloaded if not cached)
        num_prompts: Number of prompts to test (default: 25)
    """
    print("=" * 80)
    print(f"ETHOS AI Evaluator - Local GPU Testing")
    print("=" * 80)
    print(f"\nModel: {model_name}")
    print(f"Prompts: {num_prompts}")
    print(f"Device: GPU (CUDA)")
    
    # Check GPU availability
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"GPU: {gpu_name} ({gpu_mem:.1f} GB)")
        else:
            print("⚠️  Warning: CUDA not available, will use CPU")
    except ImportError:
        print("⚠️  Warning: PyTorch not installed")
    
    print("\n" + "-" * 80)
    print("Step 1: Loading Model...")
    print("-" * 80)
    
    start_load = time.time()
    try:
        model = get_model(model_name)
        # Force model load
        _ = model.respond("test", max_new_tokens=5)
        load_time = time.time() - start_load
        print(f"✅ Model loaded in {load_time:.2f} seconds")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        print("\nTroubleshooting:")
        print("1. Check internet connection (first download)")
        print("2. Ensure enough disk space for model cache")
        print("3. Try a smaller model: sshleifer/tiny-gpt2")
        return
    
    print("\n" + "-" * 80)
    print("Step 2: Loading Test Dataset...")
    print("-" * 80)
    
    try:
        dataset_loader = DatasetLoader("data")
        prompts = dataset_loader.load_ethical_dataset(num_samples=num_prompts)
        print(f"✅ Loaded {len(prompts)} ethical prompts")
    except Exception as e:
        print(f"❌ Failed to load dataset: {e}")
        return
    
    print("\n" + "-" * 80)
    print("Step 3: Generating Responses...")
    print("-" * 80)
    
    responses = []
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
            response = model.respond(prompt_text, max_new_tokens=300, temperature=0.7)
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
            print(f"{score_emoji} Score: {eval_result['score']:.2f} - {eval_result['explanation'][:80]}...")
            
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
        print(f"Total Inference Time: {total_inference_time:.2f}s")
        print(f"Throughput: {len(successful)/total_inference_time:.2f} prompts/second")
    
    # Performance metrics
    print("\n" + "-" * 80)
    print("PERFORMANCE METRICS")
    print("-" * 80)
    print(f"Model Load Time: {load_time:.2f}s")
    print(f"Total Test Time: {time.time() - start_load:.2f}s")
    
    try:
        import torch
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated(0) / 1024**3
            reserved = torch.cuda.memory_reserved(0) / 1024**3
            print(f"GPU Memory Allocated: {allocated:.2f} GB")
            print(f"GPU Memory Reserved: {reserved:.2f} GB")
    except:
        pass
    
    # Save results
    output_file = Path("test_results_local_gpu.json")
    with open(output_file, "w") as f:
        json.dump({
            "model": model_name,
            "num_prompts": len(prompts),
            "results": results,
            "summary": {
                "total": len(prompts),
                "successful": len(successful),
                "aligned": len(aligned),
                "avg_score": avg_score if successful else 0,
                "avg_response_time": avg_time if successful else 0,
                "total_time": total_inference_time,
                "load_time": load_time
            }
        }, f, indent=2)
    
    print(f"\n✅ Results saved to: {output_file.absolute()}")
    
    return results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test ETHOS AI Evaluator with local GPU model")
    parser.add_argument("--model", type=str, default="openai-community/gpt2",
                        help="Hugging Face model name (default: openai-community/gpt2)")
    parser.add_argument("--prompts", type=int, default=25,
                        help="Number of prompts to test (default: 25)")
    
    args = parser.parse_args()
    
    test_local_model_gpu(model_name=args.model, num_prompts=args.prompts)
