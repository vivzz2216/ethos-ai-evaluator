# 🔑 Where to Get RunPod Credentials - Visual Guide

This is a **step-by-step visual guide** showing exactly where to find your RunPod API credentials.

---

## 📋 Quick Summary

You need **2 things** from RunPod:

1. **API Key** - From your account settings
2. **Endpoint ID** - From your serverless endpoint (if using serverless)

---

## 🎯 Option 1: Just Running on RunPod (No API Key Needed!)

If you're **deploying your app ON RunPod** (most common use case):

### ✅ You DON'T need any RunPod API credentials!

Just:
1. Create a Pod
2. Clone your repo
3. Run `./start.sh`
4. Access via TCP Port Mappings

**Skip the rest of this guide!**

---

## 🔌 Option 2: Using RunPod API from Local Machine

If you want to **run your app locally** but use RunPod's GPUs remotely:

---

## Step 1: Get Your RunPod API Key

### 1.1 Sign In
- Go to: **https://www.runpod.io**
- Click "Sign In" or "Sign Up"

### 1.2 Navigate to Settings
```
Click your profile picture (top right) 
    ↓
Click "Settings"
    ↓
Scroll to "API Keys" section
```

### 1.3 Create API Key
```
Click "+ API Key" button
    ↓
Enter a name (e.g., "ETHOS-API")
    ↓
Click "Create"
    ↓
⚠️ COPY THE KEY IMMEDIATELY! ⚠️
(You won't see it again)
```

### 1.4 What It Looks Like
```
Format: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
Example: A1B2C3D4-E5F6-G7H8-I9J0-K1L2M3N4O5P6
```

### 1.5 Add to Your `.env` File
```env
RUNPOD_API_KEY=A1B2C3D4-E5F6-G7H8-I9J0-K1L2M3N4O5P6
```

---

## Step 2: Get Your Endpoint ID (For Serverless)

### 2.1 Navigate to Serverless
```
RunPod Console
    ↓
Click "Serverless" in left sidebar
    ↓
You'll see: https://www.runpod.io/console/serverless
```

### 2.2 Create an Endpoint (If You Don't Have One)

#### Option A: Use a Template
```
Click "New Endpoint"
    ↓
Choose a template:
  - vLLM (recommended for Llama, Mistral)
  - Text Generation Inference
  - Custom
    ↓
Select GPU type (e.g., A100)
    ↓
Configure settings
    ↓
Click "Deploy"
```

#### Option B: Quick Templates
Popular choices:
- **vLLM**: For Llama-2, Llama-3, Mistral, etc.
- **Transformers**: For any Hugging Face model
- **Custom**: Upload your own Docker image

### 2.3 Find Your Endpoint ID

Once deployed, you'll see your endpoint in the list:

```
Endpoint Name: my-llama-endpoint
Status: ● Running
Endpoint ID: abc123def456ghi789  ← THIS IS WHAT YOU NEED!
```

### 2.4 Copy the Endpoint ID

Click on your endpoint, and you'll see:
```
Endpoint Details
├── Name: my-llama-endpoint
├── ID: abc123def456ghi789  ← COPY THIS
├── Status: Running
└── URL: https://api.runpod.ai/v2/abc123def456ghi789
```

### 2.5 Add to Your `.env` File
```env
RUNPOD_ENDPOINT_ID=abc123def456ghi789
```

---

## Step 3: Complete `.env` Configuration

Your final `.env` file should look like this:

```env
# OpenAI API Key (for AI agent features)
OPENAI_API_KEY=sk-proj-your-openai-key-here

# RunPod API Configuration
RUNPOD_API_KEY=A1B2C3D4-E5F6-G7H8-I9J0-K1L2M3N4O5P6
RUNPOD_ENDPOINT_ID=abc123def456ghi789
RUNPOD_API_URL=https://api.runpod.ai/v2

# Use RunPod for inference
INFERENCE_PROVIDER=runpod
```

---

## 🧪 Step 4: Test Your Connection

### 4.1 Create Test File

Create `test_runpod.py`:

```python
import os
from dotenv import load_dotenv
import requests

load_dotenv()

api_key = os.getenv('RUNPOD_API_KEY')
endpoint_id = os.getenv('RUNPOD_ENDPOINT_ID')

print(f"API Key: {api_key[:10]}..." if api_key else "❌ Missing")
print(f"Endpoint ID: {endpoint_id}" if endpoint_id else "❌ Missing")

if api_key and endpoint_id:
    url = f"https://api.runpod.ai/v2/{endpoint_id}/health"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        response = requests.get(url, headers=headers)
        print(f"✅ Connection successful! Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
```

### 4.2 Run Test
```bash
python test_runpod.py
```

Expected output:
```
API Key: A1B2C3D4E5...
Endpoint ID: abc123def456ghi789
✅ Connection successful! Status: 200
```

---

## 📍 Direct Links

### Quick Access URLs:

1. **API Keys**: https://www.runpod.io/console/user/settings
2. **Serverless Endpoints**: https://www.runpod.io/console/serverless
3. **GPU Pods**: https://www.runpod.io/console/pods
4. **Billing**: https://www.runpod.io/console/user/billing

---

## 🎯 What Each Credential Does

| Credential | Purpose | Required For |
|------------|---------|--------------|
| **API Key** | Authenticates your requests | All API calls |
| **Endpoint ID** | Identifies which model/endpoint to use | Serverless inference |
| **API URL** | Base URL for RunPod API | All API calls (usually default) |

---

## 💡 Common Scenarios

### Scenario A: I Just Want to Deploy My App
- **What you need**: Nothing! Just create a Pod and deploy
- **No API credentials required**

### Scenario B: I Want to Use RunPod GPU from My Local Machine
- **What you need**: 
  - ✅ API Key (from Settings)
  - ✅ Endpoint ID (from Serverless)
  - ✅ Update `.env` file

### Scenario C: I Want to Use Both
- **What you need**:
  - Deploy app on RunPod (no credentials)
  - Also set up API for local testing (credentials needed)

---

## 🔒 Security Best Practices

### ✅ DO:
- Keep your API key secret
- Add `.env` to `.gitignore` (already done)
- Regenerate keys if compromised
- Use different keys for dev/prod

### ❌ DON'T:
- Commit `.env` to git
- Share API keys publicly
- Use the same key across multiple projects
- Hardcode keys in your code

---

## 🐛 Troubleshooting

### "API Key not found"
```bash
# Check if .env file exists
ls -la .env

# Check if key is set
cat .env | grep RUNPOD_API_KEY

# Reload environment
source .env  # Linux/Mac
# or restart your terminal
```

### "Invalid API Key"
- Regenerate key in RunPod settings
- Check for extra spaces in `.env`
- Ensure key is complete (no truncation)

### "Endpoint not found"
- Verify endpoint is deployed and running
- Check endpoint ID is correct
- Try accessing endpoint URL in browser

---

## 📞 Need Help?

- **RunPod Docs**: https://docs.runpod.io
- **RunPod Discord**: https://discord.gg/runpod
- **Support**: support@runpod.io

---

## ✅ Checklist

Before you start, make sure you have:

- [ ] RunPod account created
- [ ] API key generated and copied
- [ ] Serverless endpoint created (if needed)
- [ ] Endpoint ID copied
- [ ] `.env` file updated
- [ ] Connection tested successfully

---

**🎉 You're all set! Your RunPod credentials are configured correctly.**
