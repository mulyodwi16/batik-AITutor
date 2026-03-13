# Batik AI-Tutor

Chatbot pendidikan interaktif dengan **RAG (Retrieval Augmented Generation) + LLM** untuk mempelajari warisan budaya Batik Indonesia. Dibangun dengan Flask, menggunakan semantic search dengan FAISS dan LLM untuk generate jawaban.

## Fitur Utama

### RAG + LLM Pipeline
- **Semantic Search**: FAISS indexing untuk fast similarity search (cosine distance)
- **Retrieval**: Top-k relevant chunks dari knowledge base
- **LLM Generation**: Ollama GPT 20B untuk generate context-aware answers
- **Smart Fallback**: Rule-based responses jika Ollama tidak tersedia

### Chat Interface
- Real-time chatbot dengan streaming responses
- Responsive design untuk mobile & desktop
- Retrieval confidence scores ditampilkan
- Suggestion buttons untuk quick learning

### Knowledge Base
- 25 semantic chunks dari batik knowledge
- Embedding vectors (384-dimensional / all-MiniLM-L6-v2)
- FAISS index untuk O(1) retrieval complexity
- Comprehensive batik information (sejarah, motif, proses, warisan, regional)

## System Architecture

```
User Query
    ↓
Embedding (sentence-transformers)
    ↓
FAISS Index Search
    ↓
Top-k Retrieval
    ↓
Context Construction
    ↓
Ollama API (gpt-oss:20b)
    ↓
LLM Response
```

## Repo Structure

```
batik-AITutor/
│
├── app.py
├── requirements.txt
├── setup-artifacts.py
├── learn-batikindonesia.md
├── AI_Tutor.ipynb
│
├── artifacts/
│   ├── chunks.json
│   ├── embeddings.npy
│   └── faiss.index
│
├── templates/
│   └── index.html
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── chat.js
│
├── Dockerfile              # OPTIONAL deployment
├── docker-compose.yml      # OPTIONAL deployment
│
└── README.md

```

## Requirements

- Python 3.9+
- Ollama (for LLM inference)
- Model: gpt-oss:20b
- 4GB+ RAM (8–16GB recommended)
- CUDA-compatible GPU (optional but recommended)

Docker & Docker Compose are **optional** and only required for containerized deployment.
The application can run directly with Python.

## Quick Start (Penting)

### Prerequisites: Setup Ollama + Generate Artifacts

#### 1️ Setup Ollama
```bash
# Download & install Ollama dari https://ollama.ai
# Jalankan Ollama service (akan run di localhost:11434)
ollama serve

# Di terminal baru, pull model GPT 20B
ollama pull gpt-oss:20b

# Verifikasi model berhasil diunduh
ollama list
```

#### 2️ Generate Knowledge Base Artifacts

**Option A: Pakai helper script (Recommended)**
```bash
# 1. Install dependencies
pip install sentence-transformers faiss-cpu numpy

# 2. Generate artifacts dari learn-batikindonesia.md
python setup-artifacts.py

# Output: artifacts/chunks.json, embeddings.npy, faiss.index
```

**Option B: Dari Jupyter Notebook**
```bash
# Run AI_Tutor.ipynb TAHAP 1 & 2 cells untuk generate artifacts
# Copy artifacts/ folder ke project directory
```

---

## Cara Menjalankan

### Opsi 1: Lokal (tanpa Docker)

1. **Setup Ollama** (lihat prerequisites di atas)

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Generate artifacts** (jika belum):
```bash
python setup-artifacts.py
```

4. **Pastikan Ollama service berjalan:**
```bash
# Terminal 1: Jalankan Ollama server
ollama serve

# Terminal 2 atau baru: Check apakah Ollama siap
curl http://localhost:11434/api/tags
```

5. **Jalankan aplikasi Flask di terminal baru:**
```bash
python app.py
```

6. **Akses di browser:**
```
http://localhost:5000
```

**Health check:**
```bash
curl http://localhost:5000/api/health
```

### Opsi 2: Docker Compose (Optional)

**IMPORTANT: Setup Ollama & artifacts first!**

```bash
# 1. Setup Ollama dengan model GPT 20B (lihat Prerequisites)
ollama pull gpt-oss:20b

# 2. Install base dependencies
pip install sentence-transformers faiss-cpu numpy

# 3. Generate artifacts (creates artifacts/ folder)
python setup-artifacts.py

# 4. Jalankan Ollama service di terminal terpisah
ollama serve

# 5. Build & run Docker Compose di terminal baru
docker-compose up --build

# 6. Akses di browser
# http://localhost:5000
```

**Untuk stop:**
```bash
docker-compose down
```

**Note:** Docker container akan terhubung ke Ollama pada `http://localhost:11434` (host machine)

---

## API Endpoints

### POST `/api/chat`
Main chat endpoint dengan RAG + LLM
```json
Request:
{
  "message": "Apa itu batik?"
}

Response:
{
  "reply": "Jawaban dari AI Tutor...",
  "timestamp": "2026-03-05T12:00:00",
  "metadata": {
    "retrieved_chunks": [0, 1, 2],
    "retrieval_scores": [0.75, 0.68, 0.61],
    "model_used": "RAG+LLM",
    "has_context": true,
    "top_score": 0.75
  }
}
```

### GET `/api/health`
Health check endpoint
```json
{
  "status": "ok",
  "model_ready": true,
  "chunks_loaded": 25,
  "faiss_ready": true,
  "embedder_ready": true,
  "llm_ready": true
}
```

### GET `/api/suggestions`
Get suggestion prompts
```json
{
  "suggestions": [
    "Apa itu Batik?",
    "Sejarah Batik Indonesia",
    ...
  ]
}
```
## Model Configuration

### Embedder Model
- **Name**: `sentence-transformers/all-MiniLM-L6-v2`
- **Dimension**: 384
- **Speed**: 50K sentences/sec on CPU
- **Size**: 22MB

### LLM Model
- **Name**: `gpt-oss:20b` (GPT Open Source)
- **Parameters**: 20 Billion
- **Backend**: Ollama (Local Inference)
- **URL**: `http://localhost:11434`
- **Memory**: 8-16GB (recommend GPU for fast inference)
- 
### FAISS Index
- **Type**: IndexFlatIP (cosine similarity)
- **Complexity**: O(n) search, O(1) for fixed k
- **Chunks**: 25 indexed documents
- **Threshold**: 0.35 (minimum relevance score)

## ⚙️ Configuration

Edit `app.py` untuk customize:

```python
# Ubah embedder model
embedder = SentenceTransformer("model-name")

# Ubah LLM model
MODEL_NAME = "gpt-oss:20b"

# Ubah retrieval parameters
retrieve_topk(query, k=5, threshold=0.35)

# Ubah LLM generation parameters
top_p=0.9, temperature=0.7, max_tokens=300
```

## 📊 Performance

| Metric | Value |
|--------|-------|
| Knowledge Chunks | 25 |
| Embedding Quality | 384-dim vectors |
| Retrieval Speed | <10ms per query |
| LLM Speed | ~30-40 tokens/sec |
| Memory Usage | 2-3GB (float16) |
| Typical Response Time | 2-5 seconds |

## 🔧 Troubleshooting

### Port 5000 sudah digunakan
```bash
docker run -p 8000:5000
```

### Model loading lambat
- Normal untuk first startup (embedder + LLM loading)
- Cached setelah pertama kali
- Gunakan GPU untuk faster inference

### FAISS index not found
Pastikan `artifacts/` folder ada dengan:
- `chunks.json`
- `embeddings.npy`
- `faiss.index`

### LLM model tidak load
App akan fallback ke rule-based responses
Check logs: `docker-compose logs chatbot`

## 📈 Model Improvements

Untuk meningkatkan kualitas:

1. **Better Knowledge Base**: Tambah lebih banyak batik content
2. **Larger LLM**: Ganti TinyLlama dengan model yang lebih besar (Mistral, Llama2)
3. **Fine-tuning**: Fine-tune embedder/LLM khusus batik domain
4. **Retrieval Optimization**: Adjust threshold dan k parameter

## Learning Path

1. **Understand RAG**: Read about Retrieval Augmented Generation
2. **Try Basic Chat**: Test dengan suggestion prompts
3. **Check Metadata**: Lihat retrieval scores dan sources
4. **Explore Notebook**: See `AI_Tutor.ipynb` untuk detail teknis

## Production Deployment

Untuk production:

```bash
# Use gunicorn instead of Flask development server
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Scale with Docker
docker-compose up -d --scale chatbot=3

# Use load balancer (nginx)
# Add monitoring (prometheus/grafana)
```

## License

Bagian dari Riset KAIT 2026, Politeknik Elektronika Negeri Surabaya.

## Authors

Takano-sensei
Rante-sensei
Dwi-san

---

**Dibuat dengan ❤️ untuk melestarikan warisan budaya Batik Indonesia**

*Last Updated: March 5, 2026*
