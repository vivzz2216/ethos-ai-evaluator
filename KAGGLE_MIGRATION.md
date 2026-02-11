# Kaggle Setup - FREE GPU for Everything

## Why Kaggle?

- **Kaggle**: FREE 30 GPU hours/week with 2× T4 GPUs (32GB VRAM)
- **RunPod**: ~$0.79/hour (paid)

**All GPU operations run on Kaggle:**
- ✅ Model loading (8-bit quantization)
- ✅ Inference/generation (all prompts processed on GPU)
- ✅ LoRA training
- ✅ Adapter loading

Your local machine only runs the backend API and frontend UI.

---

## Quick Start (5 Minutes)

### 1. Setup Kaggle Notebook

```bash
# Go to Kaggle
https://www.kaggle.com/code

# Upload the notebook
Upload: kaggle/ethos_kaggle_server.ipynb

# Enable GPU
Settings → Accelerator → GPU T4 x2

# Enable Internet
Settings → Internet → On
```

### 2. Get ngrok Token

```bash
# Sign up (free)
https://ngrok.com

# Get your authtoken
https://dashboard.ngrok.com/get-started/your-authtoken
```

### 3. Run Kaggle Notebook

1. Click **"Run All"** in Kaggle
2. Paste your ngrok authtoken when prompted
3. Wait 2-3 minutes for server to start
4. **Copy the ngrok URL** from output:
   ```
   📡 Public URL: https://abc123.ngrok-free.app
   ```

### 4. Update Local Backend

Edit `backend/.env`:

```bash
# Comment out RunPod (keep for reference)
# REMOTE_MODEL_URL=https://ouc6bf3k5hzv6t-8080.proxy.runpod.net

# Add Kaggle ngrok URL
REMOTE_MODEL_URL=https://abc123.ngrok-free.app
```

Save and restart backend:

```bash
cd backend
python app.py
```

### 5. Test It

1. Open frontend (http://localhost:3000)
2. Upload model: `Orenguteng/Llama-3-8B-Lexi-Uncensored`
3. Run test → Wait for REJECTED
4. Click **"Train & Fix Model"**
5. Watch training in Kaggle notebook output

---

## What Changed in the Code

### ✅ No Backend Code Changes Needed!

The backend already works with any inference server URL. You just change the `.env` file.

### ✅ Kaggle Notebook Includes Everything

The `kaggle/ethos_inference_server.ipynb` notebook contains:

1. **inference_server.py** - Same API as RunPod
2. **train_lora.py** - Fixed version (no `set_submodule` error)
3. **ngrok tunnel** - Makes Kaggle publicly accessible
4. **Auto-install** - All dependencies installed automatically

---

## Important Differences

| Feature | RunPod | Kaggle |
|---------|--------|--------|
| **URL** | Persistent | Changes on restart |
| **Cost** | $0.79/hr | FREE |
| **Session** | Unlimited | 12 hours max |
| **Setup** | SSH + manual | Jupyter notebook |
| **Storage** | Ephemeral | Can persist between sessions |

### Handling URL Changes

**Every time you restart the Kaggle notebook**, the ngrok URL changes:

1. Copy new URL from Kaggle output
2. Update `backend/.env`
3. Restart local backend

**Tip**: Keep the Kaggle notebook running during your entire testing session to avoid URL changes.

---

## File Structure

```
ethos-ai-evaluator-main/
├── backend/
│   ├── .env                          # Update REMOTE_MODEL_URL here
│   ├── .env.example                  # Template with Kaggle setup
│   └── cloud/                        # RunPod files (commented out, kept for reference)
│       ├── inference_server.py       # OLD - RunPod version
│       ├── train_lora.py             # OLD - RunPod version
│       └── RUNPOD_SETUP.md           # OLD - RunPod instructions
├── kaggle/                           # NEW - Kaggle setup
│   ├── ethos_inference_server.ipynb  # Upload this to Kaggle
│   ├── KAGGLE_SETUP.md               # Detailed Kaggle instructions
│   └── README.md                     # Quick reference
└── KAGGLE_MIGRATION.md               # This file
```

---

## Troubleshooting

### Backend can't connect to Kaggle

**Check:**
1. Is the Kaggle notebook still running? (Check Kaggle tab)
2. Did you copy the full ngrok URL? (Should start with `https://`)
3. Did you restart the backend after updating `.env`?

**Fix:**
```bash
# Verify .env has correct URL
cat backend/.env

# Restart backend
cd backend
python app.py
```

### ngrok URL expired

**Cause**: Kaggle notebook was restarted or stopped

**Fix:**
1. Go to Kaggle notebook
2. Run all cells again
3. Copy new ngrok URL
4. Update `backend/.env`
5. Restart backend

### "Tunnel limit exceeded" error

**Cause**: ngrok free tier allows only 1 tunnel at a time

**Fix:**
1. Close any old Kaggle notebooks
2. Go to https://dashboard.ngrok.com/tunnels/agents
3. Kill any active tunnels
4. Restart Kaggle notebook

### Training fails with "set_submodule" error

**Cause**: Old version of `train_lora.py` in Kaggle

**Fix:**
The notebook includes the fixed version. If you see this error:
1. Re-upload `kaggle/ethos_inference_server.ipynb` to Kaggle
2. Run all cells again

### Session timeout after 12 hours

**Expected behavior**: Kaggle auto-stops notebooks after 12 hours

**Fix:**
1. Restart the Kaggle notebook
2. Copy new ngrok URL
3. Update `backend/.env`
4. Restart backend
5. Continue testing

---

## Cost Savings

### Before (RunPod)
- 1 hour of testing: **$0.79**
- 10 hours of development: **$7.90**
- 30 hours/week: **$23.70**

### After (Kaggle)
- 30 hours/week: **$0.00** ✅

**Annual savings**: ~$1,232

---

## Reverting to RunPod (If Needed)

If you ever want to go back to RunPod:

1. Edit `backend/.env`:
   ```bash
   # Comment out Kaggle
   # REMOTE_MODEL_URL=https://abc123.ngrok-free.app
   
   # Uncomment RunPod
   REMOTE_MODEL_URL=https://ouc6bf3k5hzv6t-8080.proxy.runpod.net
   ```

2. Restart backend

3. Make sure RunPod pod is running

---

## Next Steps

1. ✅ Upload notebook to Kaggle
2. ✅ Get ngrok authtoken
3. ✅ Run notebook and copy URL
4. ✅ Update `backend/.env`
5. ✅ Restart backend
6. ✅ Test the full LoRA repair flow

**You're now running on FREE GPUs!** 🎉

For detailed instructions, see: `kaggle/KAGGLE_SETUP.md`
