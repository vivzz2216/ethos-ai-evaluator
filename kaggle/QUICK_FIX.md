# Quick Fix for Kaggle Notebook

## Issue
The ngrok URL is printing as an object instead of a string.

## Fix
In the last cell of the Kaggle notebook, change this line:

**OLD:**
```python
print(f"\n📡 Public URL: {public_url}")
```

**NEW:**
```python
print(f"\n📡 Public URL: {public_url.public_url}")
```

And change this line:

**OLD:**
```python
print(f"\n   REMOTE_MODEL_URL={public_url}")
```

**NEW:**
```python
print(f"\n   REMOTE_MODEL_URL={public_url.public_url}")
```

## Complete Fixed Cell

Replace the entire "Start the inference server" cell with:

```python
# Start the inference server with ngrok tunnel
import sys
sys.path.append('/kaggle/working')

import threading
import uvicorn
from pyngrok import ngrok
import time

# Import the app
from inference_server import app

# Start uvicorn in background
def run_server():
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

# Wait for server to start
time.sleep(5)

# Create ngrok tunnel
public_url = ngrok.connect(8080, bind_tls=True)

print("\n" + "="*80)
print("🚀 ETHOS INFERENCE SERVER RUNNING ON KAGGLE")
print("="*80)
print(f"\n📡 Public URL: {public_url.public_url}")
print(f"\n⚠️  COPY THIS URL TO YOUR LOCAL backend/.env FILE:")
print(f"\n   REMOTE_MODEL_URL={public_url.public_url}")
print("\n" + "="*80)
print("\n✅ Server Status:")
print("   - Model loading: Ready (call /load endpoint)")
print("   - Inference: Ready (call /generate endpoint)")
print("   - LoRA Training: Ready (call /train endpoint)")
print("\n💡 Keep this notebook running while testing.")
print("   Session will auto-stop after 12 hours.\n")
print("="*80)
```

## After Fixing

1. Re-run the cell in Kaggle
2. Copy the correct URL (should be just `https://...ngrok-free.dev`)
3. Update your `backend/.env`
4. **Restart your backend server** (this is critical!)

```bash
# Stop backend (Ctrl+C in the terminal)
# Then restart:
cd backend
python app.py
```

The backend will now use the Kaggle GPU for all operations.
