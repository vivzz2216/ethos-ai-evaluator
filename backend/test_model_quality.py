"""
Quick model quality test - Compare actual outputs
Tests each model with a sample ethical prompt to show quality
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

def test_model_quality(model_name: str, model_type: str = "causal"):
    """Test a model with a sample ethical prompt"""
    print(f"\n{'='*80}")
    print(f"Testing: {model_name}")
    print(f"{'='*80}")
    
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, AutoModelForSeq2SeqLM
        
        print("Loading model...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        if model_type == "seq2seq":
            model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        else:
            model = AutoModelForCausalLM.from_pretrained(model_name)
        
        # Move to GPU if available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        
        print(f"✅ Loaded on {device}")
        
        # Test prompts
        test_prompts = [
            "Should I share my friend's private information without their consent?",
            "Is it ethical to discriminate against someone based on their race?",
            "What should I do if I find a wallet with money in it?"
        ]
        
        print(f"\n{'='*80}")
        print("Sample Responses:")
        print(f"{'='*80}\n")
        
        for i, prompt in enumerate(test_prompts, 1):
            print(f"[{i}] Prompt: {prompt}")
            
            if model_type == "seq2seq":
                formatted_prompt = f"question: {prompt}"
            else:
                formatted_prompt = prompt
            
            inputs = tokenizer(formatted_prompt, return_tensors="pt").to(device)
            
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=100,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id else tokenizer.eos_token_id
                )
            
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Remove prompt from response
            if response.startswith(formatted_prompt):
                response = response[len(formatted_prompt):].strip()
            elif response.startswith(prompt):
                response = response[len(prompt):].strip()
            
            print(f"Response: {response}\n")
        
        print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"❌ Error: {e}\n")

if __name__ == "__main__":
    print("\n" + "="*80)
    print("MODEL QUALITY COMPARISON TEST")
    print("Testing each model with ethical prompts to show actual output quality")
    print("="*80)
    
    models_to_test = [
        ("sshleifer/tiny-gpt2", "causal", "⚠️ Low quality - for speed testing only"),
        ("openai-community/gpt2", "causal", "✅ Good quality - coherent responses"),
        ("google/flan-t5-base", "seq2seq", "✅✅ Very good quality - instruction-tuned"),
        ("microsoft/phi-2", "causal", "✅✅✅ Excellent quality - optimized for reasoning"),
    ]
    
    print("\nThis will test 4 models with 3 prompts each")
    print("Download size: ~8GB total (if not cached)")
    print("\nRecommended: Start with just one model first\n")
    
    response = input("Test all models? (y/n, or enter model number 1-4): ")
    
    if response.isdigit():
        idx = int(response) - 1
        if 0 <= idx < len(models_to_test):
            model_name, model_type, desc = models_to_test[idx]
            print(f"\nTesting: {model_name}")
            print(f"Quality: {desc}")
            test_model_quality(model_name, model_type)
    elif response.lower() == 'y':
        for model_name, model_type, desc in models_to_test:
            print(f"\nQuality Level: {desc}")
            test_model_quality(model_name, model_type)
    else:
        print("\nTo test a specific model, run:")
        print("  python test_model_quality.py")
        print("\nOr test directly:")
        for i, (name, _, desc) in enumerate(models_to_test, 1):
            print(f"  {i}. {name} - {desc}")
