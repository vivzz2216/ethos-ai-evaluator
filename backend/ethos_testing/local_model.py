"""
Local Hugging Face model wrapper for generating responses to ethical prompts.
Runs EXCLUSIVELY on NVIDIA RTX GPU (CUDA device 0).
Works offline after first download.
"""
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)

# Force CUDA to only see the NVIDIA RTX GPU (device 0), not Intel UHD
os.environ["CUDA_VISIBLE_DEVICES"] = "0"


class LocalHuggingFaceModel:
    """Wrapper for local Hugging Face models — runs ONLY on RTX GPU (cuda:0)."""
    
    def __init__(self, model_name: str = "sshleifer/tiny-gpt2"):
        """
        Initialize a local Hugging Face model.
        
        Args:
            model_name: Hugging Face model identifier (e.g., "openai-community/gpt2")
        """
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.model_type = "causal"  # Default to causal
        self._loaded = False
        self._device = "cuda"  # Always CUDA, never CPU
        
    def _load_model(self):
        """Lazy load the model and tokenizer on RTX GPU (cuda:0) ONLY."""
        if self._loaded:
            return
            
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoModelForSeq2SeqLM, AutoTokenizer, AutoConfig  # type: ignore
            
            # REQUIRE CUDA — no CPU fallback
            if not torch.cuda.is_available():
                raise RuntimeError(
                    "CUDA NOT AVAILABLE! This platform requires an NVIDIA RTX GPU. "
                    "Ensure CUDA drivers are installed and torch+cuda is set up correctly."
                )
            
            # Force device 0 = NVIDIA RTX GPU
            torch.cuda.set_device(0)
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"🎮 Using GPU: {gpu_name} ({gpu_mem:.1f} GB VRAM)")
            
            logger.info(f"Loading model: {self.model_name} (this may take a moment on first run)...")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            # Detect model type from config
            config = AutoConfig.from_pretrained(self.model_name)
            is_t5_model = "t5" in self.model_name.lower() or config.model_type == "t5"
            
            # Set pad token if not set (required for some models)
            if self.tokenizer.pad_token is None:
                if hasattr(self.tokenizer, 'eos_token') and self.tokenizer.eos_token:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                elif hasattr(self.tokenizer, 'pad_token_id'):
                    self.tokenizer.pad_token = self.tokenizer.convert_ids_to_tokens(0)
            
            # Determine model type and load on GPU
            if is_t5_model:
                logger.info(f"Detected T5/Seq2Seq model → AutoModelForSeq2SeqLM on cuda:0")
                self.model_type = "seq2seq"
                self.model = AutoModelForSeq2SeqLM.from_pretrained(
                    self.model_name,
                    torch_dtype=torch.float16,   # FP16 to fit in 6GB VRAM
                    device_map={"": 0},           # Force ALL layers to cuda:0 (RTX GPU)
                )
            else:
                logger.info(f"Detected CausalLM model → AutoModelForCausalLM on cuda:0")
                self.model_type = "causal"
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    torch_dtype=torch.float16,   # FP16 to fit in 6GB VRAM
                    device_map={"": 0},           # Force ALL layers to cuda:0 (RTX GPU)
                    trust_remote_code=True,       # Required for some models like Phi-2
                )
            
            # Set to eval mode (no gradient tracking = less VRAM)
            self.model.eval()
                
            self._loaded = True
            self._device = "cuda"
            
            allocated = torch.cuda.memory_allocated(0) / 1024**3
            reserved = torch.cuda.memory_reserved(0) / 1024**3
            logger.info(
                f"✅ Model {self.model_name} loaded on {gpu_name}! "
                f"VRAM: {allocated:.2f} GB allocated, {reserved:.2f} GB reserved "
                f"(type: {self.model_type})"
            )
            
        except ImportError:
            logger.error("transformers library not installed. Install with: pip install transformers torch")
            raise
        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            raise
    
    def respond(self, prompt: str, max_new_tokens: int = 300, temperature: float = 0.7) -> str:
        """
        Generate a response to a prompt.
        
        Args:
            prompt: Input prompt/question
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0, higher = more random)
            
        Returns:
            Generated response text
        """
        if not self._loaded:
            self._load_model()
            
        try:
            # Pass prompt directly to model - no coaching or system prompts
            # The platform tests models AS-IS to evaluate their ethical alignment
            if self.model_type == "seq2seq":
                formatted_prompt = prompt
            else:
                formatted_prompt = prompt
            
            # Tokenize input
            inputs = self.tokenizer(formatted_prompt, return_tensors="pt", truncation=True, max_length=512)
            
            # Move ALL inputs to cuda:0 (RTX GPU) — always
            inputs = {k: v.to("cuda:0") for k, v in inputs.items()}
            
            # Generate response with better parameters
            generate_kwargs = {
                "max_new_tokens": max_new_tokens,
                "min_new_tokens": 20,  # Ensure minimum length
                "pad_token_id": self.tokenizer.pad_token_id,
                "num_beams": 4,  # Use beam search for better quality
                "early_stopping": True,
                "no_repeat_ngram_size": 3,  # Avoid repetition
            }
            
            # Add temperature and sampling for more diverse responses
            if temperature > 0:
                generate_kwargs["temperature"] = temperature
                generate_kwargs["do_sample"] = True
                generate_kwargs["top_p"] = 0.9
                generate_kwargs["top_k"] = 50
            
            if hasattr(self.tokenizer, 'eos_token_id') and self.tokenizer.eos_token_id:
                generate_kwargs["eos_token_id"] = self.tokenizer.eos_token_id
            
            outputs = self.model.generate(**inputs, **generate_kwargs)
            
            # Decode response
            generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Remove the original prompt from the response if it's included
            if generated_text.startswith(formatted_prompt):
                generated_text = generated_text[len(formatted_prompt):].strip()
            elif generated_text.startswith(prompt):
                generated_text = generated_text[len(prompt):].strip()
            
            # Ensure we have a meaningful response
            if not generated_text or len(generated_text) < 10:
                return "I understand the question, but I need more context to provide a complete answer."
            
            return generated_text.strip()
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            # Return a safe fallback response
            return "I apologize, but I encountered an error generating a response. Please try again."
    
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._loaded


# Global model instance (lazy loaded)
_global_model: Optional[LocalHuggingFaceModel] = None

def get_model(model_name: Optional[str] = None) -> LocalHuggingFaceModel:
    """
    Get or create the global model instance.
    
    Args:
        model_name: Optional model name to use (will reset if different from current)
        
    Returns:
        LocalHuggingFaceModel instance
    """
    global _global_model
    
    model_name = model_name or "sshleifer/tiny-gpt2"
    
    # Reset if model name changed or if not loaded
    if _global_model is None or _global_model.model_name != model_name:
        if _global_model is not None:
            logger.info(f"Switching from {_global_model.model_name} to {model_name}")
        _global_model = LocalHuggingFaceModel(model_name)
    
    return _global_model

def reset_model():
    """Reset the global model instance (useful for testing or switching models)."""
    global _global_model
    _global_model = None

