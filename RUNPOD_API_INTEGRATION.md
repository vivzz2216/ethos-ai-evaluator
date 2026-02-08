# RunPod API Integration Guide

This guide shows you how to connect your **local** ETHOS AI Evaluator to RunPod's Serverless GPU API for remote model inference.

## When to Use This

- ✅ You want to run your app **locally** but use RunPod's GPUs for inference
- ✅ You don't have a local GPU
- ✅ You want to use larger models without local hardware

## Getting RunPod API Credentials

### Step 1: Get Your RunPod API Key

1. **Sign in to RunPod**: https://www.runpod.io
2. **Go to Settings**: Click your profile → "Settings"
3. **API Keys Section**: Scroll to "API Keys"
4. **Create New Key**:
   - Click "+ API Key"
   - Name it (e.g., "ETHOS-API")
   - Copy the key (starts with something like `XXXXXX-XXXXXXXXXX`)
   - ⚠️ **Save it immediately** - you won't see it again!

### Step 2: Get Your Endpoint ID (for Serverless)

1. **Go to Serverless**: https://www.runpod.io/console/serverless
2. **Create an Endpoint** (if you don't have one):
   - Click "New Endpoint"
   - Choose a template (e.g., "vLLM", "Text Generation")
   - Select GPU type
   - Deploy
3. **Copy Endpoint ID**: 
   - Click on your endpoint
   - Copy the Endpoint ID (looks like: `abc123def456`)

---

## Environment Variables Setup

### Update Your `.env` File

Add these variables to your `.env` file:

```env
# OpenAI API Key (for AI agent features)
OPENAI_API_KEY=sk-your-openai-key-here

# RunPod API Configuration
RUNPOD_API_KEY=your-runpod-api-key-here
RUNPOD_ENDPOINT_ID=your-endpoint-id-here
RUNPOD_API_URL=https://api.runpod.ai/v2

# Optional: Choose inference provider
INFERENCE_PROVIDER=runpod  # Options: local, runpod, openai
```

### Example `.env` File

```env
OPENAI_API_KEY=sk-proj-abc123...
RUNPOD_API_KEY=ABCD1234-EFGH5678-IJKL9012
RUNPOD_ENDPOINT_ID=abc123def456
RUNPOD_API_URL=https://api.runpod.ai/v2
INFERENCE_PROVIDER=runpod
```

---

## Code Integration

### Option 1: Create RunPod Adapter (Recommended)

Create a new file: `backend/ethos_testing/runpod_model.py`

```python
import os
import requests
from typing import Optional

class RunPodModel:
    """
    Adapter for RunPod Serverless API
    """
    def __init__(self, endpoint_id: Optional[str] = None):
        self.api_key = os.getenv('RUNPOD_API_KEY')
        self.endpoint_id = endpoint_id or os.getenv('RUNPOD_ENDPOINT_ID')
        self.base_url = os.getenv('RUNPOD_API_URL', 'https://api.runpod.ai/v2')
        
        if not self.api_key:
            raise ValueError("RUNPOD_API_KEY not found in environment")
        if not self.endpoint_id:
            raise ValueError("RUNPOD_ENDPOINT_ID not found in environment")
    
    def generate(self, prompt: str, max_tokens: int = 100) -> str:
        """
        Generate text using RunPod endpoint
        """
        url = f"{self.base_url}/{self.endpoint_id}/runsync"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "input": {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            
            # Extract generated text (format depends on your endpoint)
            if 'output' in result:
                return result['output'].get('text', '')
            elif 'choices' in result:
                return result['choices'][0].get('text', '')
            else:
                return str(result)
                
        except requests.exceptions.RequestException as e:
            print(f"RunPod API error: {e}")
            return ""

# Singleton instance
_runpod_model = None

def get_runpod_model(endpoint_id: Optional[str] = None) -> RunPodModel:
    """Get or create RunPod model instance"""
    global _runpod_model
    if _runpod_model is None:
        _runpod_model = RunPodModel(endpoint_id)
    return _runpod_model
```

### Option 2: Update Existing Local Model

Update `backend/ethos_testing/local_model.py` to support RunPod:

```python
import os
from typing import Optional

def get_model(model_name: Optional[str] = None):
    """
    Get model based on INFERENCE_PROVIDER setting
    """
    provider = os.getenv('INFERENCE_PROVIDER', 'local')
    
    if provider == 'runpod':
        from .runpod_model import get_runpod_model
        return get_runpod_model()
    elif provider == 'local':
        # Existing local model code
        return LocalHuggingFaceModel(model_name)
    else:
        raise ValueError(f"Unknown inference provider: {provider}")
```

---

## Testing the Connection

### Test Script

Create `test_runpod_connection.py`:

```python
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_runpod_connection():
    """Test RunPod API connection"""
    api_key = os.getenv('RUNPOD_API_KEY')
    endpoint_id = os.getenv('RUNPOD_ENDPOINT_ID')
    
    print("🔍 Checking RunPod Configuration...")
    print(f"API Key: {'✅ Found' if api_key else '❌ Missing'}")
    print(f"Endpoint ID: {'✅ Found' if endpoint_id else '❌ Missing'}")
    
    if not api_key or not endpoint_id:
        print("\n❌ Missing credentials. Please update your .env file.")
        return False
    
    print(f"\nAPI Key (first 10 chars): {api_key[:10]}...")
    print(f"Endpoint ID: {endpoint_id}")
    
    # Test API call
    try:
        from backend.ethos_testing.runpod_model import RunPodModel
        
        print("\n🚀 Testing RunPod API...")
        model = RunPodModel()
        response = model.generate("Hello, world!", max_tokens=20)
        
        print(f"✅ Success! Response: {response}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_runpod_connection()
```

Run the test:
```bash
python test_runpod_connection.py
```

---

## Using RunPod in Your Application

### In API Endpoints

Update `backend/ethos_testing/api.py`:

```python
import os
from .runpod_model import get_runpod_model
from .local_model import get_model as get_local_model

@router.post("/ethos/test/ethical")
async def test_ethical(request: TestRequest):
    # Check which provider to use
    provider = os.getenv('INFERENCE_PROVIDER', 'local')
    
    if provider == 'runpod':
        model = get_runpod_model()
    else:
        model = get_local_model(request.model_name)
    
    # Generate responses
    responses = []
    for prompt in prompts:
        response = model.generate(prompt['prompt'])
        responses.append(response)
    
    # Rest of your evaluation logic...
```

---

## RunPod Serverless Endpoints

### Popular Templates:

1. **vLLM** - Fast inference for Llama, Mistral, etc.
2. **Text Generation Inference** - Hugging Face models
3. **Custom Models** - Deploy your own

### Creating a Custom Endpoint:

1. Go to: https://www.runpod.io/console/serverless
2. Click "New Endpoint"
3. Choose template or upload custom Docker image
4. Configure:
   - GPU type (A100, H100, etc.)
   - Max workers
   - Timeout settings
5. Deploy and copy Endpoint ID

---

## Pricing

### RunPod Serverless Pricing:

- **Pay per second** of GPU usage
- **No idle costs** when not running
- Typical costs:
  - RTX 4090: ~$0.0004/sec
  - A100 40GB: ~$0.0010/sec
  - H100: ~$0.0020/sec

### Cost Optimization:

```python
# Use smaller max_tokens to reduce costs
response = model.generate(prompt, max_tokens=50)  # Instead of 500

# Batch requests when possible
responses = model.generate_batch(prompts)  # More efficient
```

---

## Troubleshooting

### Error: "Invalid API Key"
- Check your API key in RunPod settings
- Ensure no extra spaces in `.env` file
- Regenerate key if needed

### Error: "Endpoint not found"
- Verify Endpoint ID is correct
- Check endpoint is deployed and running
- Try endpoint URL in browser: `https://api.runpod.ai/v2/{endpoint_id}/health`

### Error: "Timeout"
- Increase timeout in requests: `timeout=120`
- Check endpoint has available workers
- Try smaller model or reduce max_tokens

### Error: "Rate limit exceeded"
- Add delays between requests
- Upgrade RunPod plan
- Use batch processing

---

## Complete Example

Here's a complete working example:

```python
# backend/ethos_testing/runpod_integration.py

import os
import requests
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

class RunPodInference:
    def __init__(self):
        self.api_key = os.getenv('RUNPOD_API_KEY')
        self.endpoint_id = os.getenv('RUNPOD_ENDPOINT_ID')
        self.base_url = "https://api.runpod.ai/v2"
        
    def generate_response(self, prompt: str) -> str:
        """Generate a single response"""
        url = f"{self.base_url}/{self.endpoint_id}/runsync"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "input": {
                "prompt": prompt,
                "max_new_tokens": 100,
                "temperature": 0.7,
                "top_p": 0.9,
            }
        }
        
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        return response.json()['output']['text']
    
    def generate_batch(self, prompts: List[str]) -> List[str]:
        """Generate multiple responses"""
        return [self.generate_response(p) for p in prompts]

# Usage
if __name__ == "__main__":
    inference = RunPodInference()
    result = inference.generate_response("What is the meaning of life?")
    print(result)
```

---

## Summary

### Quick Setup Checklist:

- [ ] Get RunPod API Key from Settings
- [ ] Create Serverless Endpoint
- [ ] Copy Endpoint ID
- [ ] Add to `.env` file:
  ```env
  RUNPOD_API_KEY=your-key
  RUNPOD_ENDPOINT_ID=your-endpoint-id
  INFERENCE_PROVIDER=runpod
  ```
- [ ] Create `runpod_model.py` adapter
- [ ] Test connection
- [ ] Update API endpoints to use RunPod

---

**🎉 You're now ready to use RunPod's GPU infrastructure from your local application!**
