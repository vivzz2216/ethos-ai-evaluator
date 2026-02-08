"""
Local Hugging Face model wrapper for generating responses to ethical prompts.
Works offline after first download.
"""
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class LocalHuggingFaceModel:
    """Wrapper for local Hugging Face models that generates responses offline."""
    
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
        
    def _load_model(self):
        """Lazy load the model and tokenizer."""
        if self._loaded:
            return
            
        try:
            from transformers import AutoModelForCausalLM, AutoModelForSeq2SeqLM, AutoTokenizer, AutoConfig  # type: ignore
            
            logger.info(f"Loading model: {self.model_name} (this may take a moment on first run)...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            # Detect model type from config
            config = AutoConfig.from_pretrained(self.model_name)
            is_t5_model = "t5" in self.model_name.lower() or config.model_type == "t5"
            
            # Set pad_token if not present
            if self.tokenizer.pad_token is None:
                if hasattr(self.tokenizer, 'eos_token') and self.tokenizer.eos_token:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                elif hasattr(self.tokenizer, 'pad_token_id'):
                    # For T5 models, pad_token_id is usually 0
                    self.tokenizer.pad_token = self.tokenizer.convert_ids_to_tokens(0)
            
            # Load appropriate model type
            if is_t5_model:
                logger.info(f"Detected T5/Seq2Seq model, using AutoModelForSeq2SeqLM")
                self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
                self.model_type = "seq2seq"
            else:
                logger.info(f"Detected CausalLM model, using AutoModelForCausalLM")
                self.model = AutoModelForCausalLM.from_pretrained(self.model_name)
                self.model_type = "causal"
                
            self._loaded = True
            logger.info(f"✅ Model {self.model_name} loaded successfully (type: {self.model_type})")
            
        except ImportError:
            logger.error("transformers library not installed. Install with: pip install transformers torch")
            raise
        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            raise
    
    def respond(self, prompt: str, max_new_tokens: int = 100, temperature: float = 0.7) -> str:
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
            # For T5 models, format prompt appropriately
            if self.model_type == "seq2seq":
                # T5 models work better with a prefix, but can also work without
                formatted_prompt = f"question: {prompt}"
            else:
                formatted_prompt = prompt
            
            # Tokenize input
            inputs = self.tokenizer(formatted_prompt, return_tensors="pt", truncation=True, max_length=512)
            
            # Generate response
            generate_kwargs = {
                "max_new_tokens": max_new_tokens,
                "pad_token_id": self.tokenizer.pad_token_id,
            }
            
            # Add temperature and sampling for causal models or when temperature > 0
            if self.model_type == "causal" or temperature > 0:
                generate_kwargs["temperature"] = temperature
                generate_kwargs["do_sample"] = temperature > 0
            
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
            
            return generated_text.strip() if generated_text.strip() else "I understand the question, but I need more context to provide a complete answer."
            
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

