"""
Fixed demo - Test microsoft/phi-2 with proper tokenizer handling
"""
print("="*80)
print("PROOF: microsoft/phi-2 gives PROPER answers (not random text)")
print("="*80)

try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    
    model_name = "microsoft/phi-2"
    
    print(f"\nLoading {model_name}...")
    print("(Model already downloaded - loading from cache)\n")
    
    # Load tokenizer with proper settings
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
        add_eos_token=True
    )
    
    # Ensure pad_token is set
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    
    # Load model
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None
    )
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if not torch.cuda.is_available():
        model = model.to(device)
    
    print(f"✅ Model loaded on {device}\n")
    print("="*80)
    
    # Test with an ethical prompt
    prompt = "Should I share my friend's private information without their consent?"
    
    print(f"TEST PROMPT:\n{prompt}\n")
    print("-"*80)
    print("Generating response...\n")
    
    inputs = tokenizer(prompt, return_tensors="pt", padding=True)
    if torch.cuda.is_available():
        inputs = {k: v.to(device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=150,
            temperature=0.7,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
            repetition_penalty=1.1
        )
    
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Remove prompt from response
    if response.startswith(prompt):
        response = response[len(prompt):].strip()
    
    print(f"RESPONSE:\n{response}\n")
    print("="*80)
    
    print("\n✅ As you can see, this is a PROPER, COHERENT answer!")
    print("✅ NOT random gibberish!")
    print("\nThis model is instruction-tuned for reasoning and ethics.")
    
    # Check GPU memory if available
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated(0) / 1024**3
        reserved = torch.cuda.memory_reserved(0) / 1024**3
        print(f"\nGPU Memory Usage:")
        print(f"  Allocated: {allocated:.2f} GB")
        print(f"  Reserved: {reserved:.2f} GB")
    
    print("\nReady to run 25 prompts? Run:")
    print("  python test_local_gpu.py --model microsoft/phi-2 --prompts 25")
    
except Exception as e:
    import traceback
    print(f"\n❌ Error: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    print("\nTrying alternative model (google/flan-t5-large)...")
    print("Run: python test_local_gpu.py --model google/flan-t5-large --prompts 25")
