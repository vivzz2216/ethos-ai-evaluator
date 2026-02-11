# Kaggle GPU Setup - Complete Guide

## 🎯 What This Does

**All GPU operations run on Kaggle's FREE T4 GPUs:**
- ✅ Model loading (8-bit quantization)
- ✅ Inference/generation (all prompts)
- ✅ LoRA training
- ✅ Adapter loading

**Your local machine only runs:**
- Backend API (coordinates everything)
- Frontend UI (browser interface)

---

## 🚀 Quick Setup (5 Minutes)

### Step 1: Get ngrok Token (One-Time)
1. Sign up: https://ngrok.com (free)
2. Get token: https://dashboard.ngrok.com/get-started/your-authtoken
3. Copy and save it

### Step 2: Upload to Kaggle
1. Go to: https://www.kaggle.com/code
2. Click: **"New Notebook" → "Upload Notebook"**
3. Upload: `ethos_kaggle_server.ipynb` (from this folder)

### Step 3: Configure Kaggle
1. Click **"⚙️ Settings"** (right sidebar)
2. **Accelerator** → Select **"GPU T4 x2"** ✅
3. **Internet** → Toggle **"On"** ✅
4. Click **"Save"**

### Step 4: Run Notebook
1. Click **"Run All"** (or Shift+Enter on each cell)
2. When prompted, paste your ngrok token
3. Wait 2-3 minutes for server to start
4. **Copy the URL** from output:
   ```
   📡 Public URL: https://abc123.ngrok-free.app
   ```

### Step 5: Update Local Backend
Edit `backend/.env`:
```bash
REMOTE_MODEL_URL=https://abc123.ngrok-free.app
```

Save and restart backend:
```bash
cd backend
python app.py
```

### Step 6: Test It! 🎉
1. Open frontend: http://localhost:3000
2. Upload model: `Orenguteng/Llama-3-8B-Lexi-Uncensored`
3. Run test → Wait for verdict
4. Click **"Train & Fix Model"**
5. Watch training happen in Kaggle notebook output

---

## 📊 What You Get

| Resource | Kaggle | Cost |
|----------|--------|------|
| **GPU** | 2× NVIDIA T4 | FREE |
| **VRAM** | 32GB total | FREE |
| **Hours/Week** | 30 hours | FREE |
| **Session** | 12 hours max | FREE |

**Your LoRA training needs ~14GB VRAM** → Kaggle's 32GB is perfect!

---

## ⚠️ Important Notes

### URL Changes on Restart
Every time you restart the Kaggle notebook, the ngrok URL changes:
1. Copy new URL from Kaggle output
2. Update `backend/.env`
3. Restart local backend

**Tip:** Keep Kaggle notebook running during your entire testing session.

### Session Limits
- **30 GPU hours/week** (resets every Monday)
- **12-hour max session** (auto-stops after 12 hours)
- **Solution:** Just restart the notebook when it stops

### Saving Adapters
Trained adapters are saved in `/kaggle/working/adapters/`

**To download:**
1. In Kaggle, click **"📁 Output"** (right sidebar)
2. Navigate to `adapters/round_X/adapter/`
3. Right-click files → Download

---

## 🔧 Troubleshooting

### Backend Can't Connect
**Check:**
- Is Kaggle notebook still running?
- Did you copy the full ngrok URL (starts with `https://`)?
- Did you restart backend after updating `.env`?

**Fix:**
```bash
# Verify .env
cat backend/.env

# Restart backend
cd backend
python app.py
```

### "Tunnel Limit Exceeded"
**Cause:** ngrok free tier = 1 tunnel at a time

**Fix:**
1. Close any old Kaggle notebooks
2. Go to: https://dashboard.ngrok.com/tunnels/agents
3. Kill active tunnels
4. Restart Kaggle notebook

### Training Fails
**Check Kaggle notebook output** for error messages.

Common issues:
- Out of memory → Reduce `batch_size` to 2
- Dataset not found → Re-upload patch file
- Model not loaded → Check `/health` endpoint

### Session Expired (After 12 Hours)
**Expected behavior** - Kaggle auto-stops notebooks.

**Fix:**
1. Go to Kaggle
2. Click **"Run All"** again
3. Copy new ngrok URL
4. Update `backend/.env`
5. Restart backend

---

## 💰 Cost Comparison

| Service | Weekly Cost | GPU | VRAM |
|---------|-------------|-----|------|
| **Kaggle** | **$0.00** | 2× T4 | 32GB |
| RunPod | ~$23.70 | 1× A6000 | 48GB |
| Colab Pro | $9.99 | 1× T4 | 16GB |

**Annual savings vs RunPod:** ~$1,232 🎉

---

## 📚 How It Works

```
┌─────────────────┐
│  Your Computer  │
│                 │
│  ┌───────────┐  │
│  │ Frontend  │  │ ← You interact here
│  │(Browser)  │  │
│  └─────┬─────┘  │
│        │        │
│  ┌─────▼─────┐  │
│  │  Backend  │  │ ← Coordinates everything
│  │   (API)   │  │
│  └─────┬─────┘  │
└────────┼────────┘
         │
         │ HTTP requests via ngrok
         │
┌────────▼────────────────────────┐
│       Kaggle Notebook           │
│                                 │
│  ┌──────────────────────────┐  │
│  │   Inference Server       │  │
│  │   (FastAPI + ngrok)      │  │
│  └────────┬─────────────────┘  │
│           │                     │
│  ┌────────▼─────────────────┐  │
│  │  Model (Llama-3-8B)      │  │ ← Loaded in 8-bit
│  │  Running on T4 GPU       │  │
│  └──────────────────────────┘  │
│                                 │
│  ┌──────────────────────────┐  │
│  │  LoRA Training           │  │ ← Happens here
│  │  (train_lora.py)         │  │
│  └──────────────────────────┘  │
└─────────────────────────────────┘
```

---

## 🎯 Next Steps

1. ✅ Upload `ethos_kaggle_server.ipynb` to Kaggle
2. ✅ Enable GPU T4 x2 and Internet
3. ✅ Run notebook and get ngrok URL
4. ✅ Update `backend/.env`
5. ✅ Test the full LoRA repair flow

**You're now running on FREE GPUs!** 🚀

---

## 📖 Additional Resources

- **Kaggle Docs:** https://www.kaggle.com/docs/notebooks
- **ngrok Docs:** https://ngrok.com/docs
- **PEFT Library:** https://huggingface.co/docs/peft

---

## ❓ Need Help?

Check the Kaggle notebook output for detailed logs. All operations (loading, inference, training) are logged there.
