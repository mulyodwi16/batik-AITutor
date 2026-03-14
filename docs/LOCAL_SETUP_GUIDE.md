# 🚀 Local Setup Guide - Batik AI-Tutor

**Platform**: Windows / macOS / Linux  
**No Docker required** - Pure local setup with Ollama + Flask  
**Status**: Ready to deploy 🎉

---

## 📋 Prerequisites

- **Python 3.10+** (tested on 3.13)
- **Ollama** (free, local LLM engine)
- **Git** (optional, for cloning)
- **~8GB RAM** (recommended for embeddings + LLM)
- **2GB disk space** (for models + artifacts)

---

## 🎯 Step 1: Install Ollama

### On Windows
```powershell
# Download & install from:
https://ollama.ai

# Or use chocolatey:
choco install ollama

# Verify installation:
ollama --version
```

### On macOS
```bash
# Using Homebrew:
brew install ollama

# Or download from:
https://ollama.ai
```

### On Linux (Ubuntu/Debian)
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Verify Ollama running:**
```bash
ollama serve
# Server should start on http://localhost:11434
```

---

## 🎯 Step 2: Pull Ollama Model

In a NEW terminal/PowerShell (keep ollama serve running):

```bash
# Pull the model (first time only, ~5-10 min):
ollama pull gpt-oss:20b

# Verify:
ollama list
# Should show: gpt-oss:20b   <latest>

# Test model:
ollama run gpt-oss:20b "Siapa pencetus batik?"
```

If pulling fails, use alternative:
```bash
# Try smaller/faster model:
ollama pull llama2
# Then update OLLAMA_MODEL in app.py (line 84) from "gpt-oss:20b" to "llama2"
```

---

## 🎯 Step 3: Prepare Python Environment

### Clone/Navigate to Project
```powershell
cd "c:\Users\LENOVO\OneDrive - Politeknik Elektronika Negeri Surabaya (1)\Riset-KAIT2026\AI-Tutor"
```

### Activate Virtual Environment
```powershell
# If not already created:
python -m venv .venv

# Activate:
.venv\Scripts\Activate.ps1
```

### Install Dependencies
```powershell
pip install -r requirements.txt
```

**If issues with specific packages:**
```powershell
pip install flask flask-cors numpy sentence-transformers faiss-cpu torch PyYAML requests
```

---

## 🎯 Step 4: Verify Setup

### Check Artifacts
```powershell
# Should exist:
dir artifacts/

# You should see:
# - chunks.json (54 chunks with metadata)
# - embeddings.npy (54x384 vectors)
# - faiss.index (search index)
```

**If artifacts missing:**
```powershell
# Generate them:
python setup-artifacts-new.py
```

### Check Ollama Connection
```powershell
python -c "
import requests
try:
    r = requests.get('http://localhost:11434/api/tags', timeout=5)
    print('✅ Ollama connected:', r.json()['models'][0]['name'])
except:
    print('❌ Ollama not running! Start with: ollama serve')
"
```

---

## 🎯 Step 5: Run Application

### Start Flask Server
```powershell
python app.py
```

**Expected output:**
```
================================================================================
🚀 Batik AI-Tutor Starting Up
================================================================================
✅ Chunks loaded: 54
✅ FAISS index: Ready
✅ Embedder model: Loaded
✅ Ollama model: gpt-oss:20b
✅ Model status: 🟢 FULL RAG+LLM

🌐 Starting server on http://0.0.0.0:5000
================================================================================
```

---

## 🌐 Step 6: Access Application

### Web Interface
```
http://localhost:5000
```

Open in browser → Chat interface loads ✅

### API Health Check
```bash
# Check system status:
curl http://localhost:5000/api/health

# Response:
{
  "status": "ok",
  "model_ready": true,
  "chunks_loaded": 54,
  "faiss_ready": true,
  "embedder_ready": true,
  "llm_ready": true,
  "ollama_model": "gpt-oss:20b",
  "inventory": {
    "total": 12,
    "jetis": 6,
    "surabaya": 6
  }
}
```

### API Chat Endpoint
```bash
# Test RAG chat:
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Apa itu motif Liris?"}'

# Response:
{
  "reply": "Liris motif represents steadfastness...",
  "timestamp": "2026-03-14T...",
  "metadata": {
    "retrieved_chunks": [0, 2, 5],
    "retrieval_scores": [0.45, 0.42, 0.38],
    "model_used": "RAG+LLM",
    "has_context": true
  }
}
```

### Debug Retrieval (test FAISS only)
```bash
# See which chunks are retrieved for a query:
curl "http://localhost:5000/api/debug/retrieve?q=peacock+motif&k=5"

# Response shows:
# - Query
# - Retrieved chunks (ID, similarity score, preview text)
# - Useful for debugging RAG
```

---

## 📝 Configuration

### Change Ollama Model
Edit `app.py` line 84:
```python
OLLAMA_MODEL = "gpt-oss:20b"  # Change me!

# Other options:
# OLLAMA_MODEL = "llama2"
# OLLAMA_MODEL = "mistral"
# OLLAMA_MODEL = "neural-chat"
```

### Change Flask Port
Edit bottom of `app.py`:
```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)  # Change 5000 to your port
```

### Change Ollama Host
Edit `app.py` line 83:
```python
OLLAMA_BASE_URL = "http://localhost:11434"  # Change if Ollama is remote
```

---

## 🧪 Testing

### 1. Unit Test: Metadata Loading
```powershell
python -c "
import json
with open('artifacts/chunks.json') as f:
    data = json.load(f)
    assert 'chunks' in data
    assert 'chunk_metadata' in data
    assert len(data['chunks']) == 54
    assert len(data['chunk_metadata']) == 54
    print('✅ Metadata loaded correctly')
"
```

### 2. Integration Test: RAG Pipeline
```bash
# Query 1: General question
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Berapa banyak motif batik?"}'

# Query 2: Location-specific
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Motif apa asal Surabaya?"}'

# Query 3: Semantic search
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Batik apa yang bermakna keberanian?"}'
```

### 3. Performance Monitoring
Check Flask logs for:
- ✅ "✓ Answer ready" = Success
- ⚠️ "No chunks retrieved" = Query issue
- ❌ "Ollama" error = Check ollama serve

---

## 🐛 Troubleshooting

### Issue: "Ollama not running"
**Error**: `Cannot reach Ollama at http://localhost:11434`

**Fix**:
```bash
# In another terminal:
ollama serve
```

---

### Issue: "Model not found"
**Error**: `Model 'gpt-oss:20b' not in Ollama`

**Fix**:
```bash
ollama pull gpt-oss:20b
# Or update app.py to use available model:
ollama list  # See what's available
# Then update OLLAMA_MODEL in app.py
```

---

### Issue: "Chunks not loaded"
**Error**: `artifacts/chunks.json not found`

**Fix**:
```bash
python setup-artifacts-new.py
# Wait ~2 minutes for artifacts to generate
```

---

### Issue: "FAISS/Embedder error"
**Error**: `Error loading FAISS index` or `Error loading embedder`

**Fix**:
```bash
# Reinstall dependencies:
pip install --upgrade faiss-cpu sentence-transformers torch

# On older systems:
pip install numpy==1.24.3 torch==2.0.1 sentence-transformers==2.2.2
```

---

### Issue: "Out of memory"
**Error**: Memory allocation failure

**Fix**:
```python
# Edit app.py line 295, reduce context size:
MAX_CONTEXT_CHARS = 4_000  # Reduce from 8_000
```

---

### Issue: "Port already in use"
**Error**: `Address already in use (:5000)`

**Fix**:
```bash
# Find process using port 5000:
netstat -ano | findstr :5000

# Kill it:
taskkill /PID <PID> /F

# Or change port in app.py and restart
```

---

## 📊 System Architecture

```
┌─────────────────────────────────────────────┐
│      Web Browser (localhost:5000)           │
│   - index.html (chat interface)             │
│   - static/css, static/js                   │
└──────────────┬──────────────────────────────┘
               │ HTTP
┌──────────────▼──────────────────────────────┐
│         Flask App (app.py)                  │
│  ┌────────────────────────────────────────┐ │
│  │ Routes:                                │ │
│  │ - GET  /              (web page)       │ │
│  │ - POST /api/chat      (main RAG)       │ │
│  │ - GET  /api/health    (status)         │ │
│  │ - GET  /api/debug/retrieve (debug)     │ │
│  │ - GET  /api/suggestions (hints)        │ │
│  └────────────────────────────────────────┘ │
└──────────────┬──────────────────────────────┘
               │
     ┌─────────┼─────────┐
     │         │         │
     ▼         ▼         ▼
┌─────────┐ ┌──────┐ ┌──────────┐
│ Artifacts│ │FAISS │ │ Embedder │
│ (54 text)│ │Index │ │ Model    │
│ Metadata │ │      │ │ (384D)   │
└─────────┘ └──────┘ └──────────┘
     │
     └─────────────────┬──────────────────┐
                       │                  │
                       ▼                  ▼
                   ┌────────────┐    ┌──────────┐
                   │   Semantic │    │  Ollama  │
                   │   Search   │    │   LLM    │
                   │  (FAISS)   │    │ (Remote) │
                   └────────────┘    └──────────┘

Flow: Query → Embed → FAISS Search → Retrieve → LLM Generate Answer
```

---

## 🚀 Production Deployment

For production use, consider:

1. **Update Flask config**
   ```python
   app.run(
       host='0.0.0.0',
       port=5000,
       debug=False,           # Disable debug
       use_reloader=False,    # No auto-reload
       threaded=True          # Enable threading
   )
   ```

2. **Use production WSGI server**
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

3. **Add environment variables**
   ```bash
   export OLLAMA_BASE_URL="http://your-ollama-server:11434"
   export FLASK_ENV="production"
   python app.py
   ```

---

## 📞 Support

| Issue | Check |
|-------|-------|
| "Can't download model" | Internet connection, ~5GB space |
| "Flask won't start" | Port conflicts, Python version |
| "RAG gives wrong answers" | Ollama model quality, context size |
| "Slow responses" | CPU usage, model size, RAM |

---

## ✅ Quick Checklist

Before running in production:

- [ ] Ollama installed & running (`ollama serve`)
- [ ] Model pulled (`ollama pull gpt-oss:20b`)
- [ ] Python venv activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Artifacts generated (`python setup-artifacts-new.py`)
- [ ] Health check passes (`/api/health` returns 200)
- [ ] Test query works (`/api/chat` returns answer)
- [ ] Frontend loads (`http://localhost:5000`)

---

**Status**: ✅ Ready to run!  
**Next**: `python app.py` 🚀
