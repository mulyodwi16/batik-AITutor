# 🎨 Batik AI-Tutor

Chatbot pendidikan interaktif dengan **RAG (Retrieval Augmented Generation) + LLM** untuk mempelajari warisan budaya Batik Indonesia. Dibangun dengan Flask, menggunakan semantic search dengan FAISS dan LLM untuk generate jawaban.

## ✨ Fitur Utama

### 🤖 RAG + LLM Pipeline
- **Semantic Search**: FAISS indexing untuk fast similarity search (cosine distance)
- **Retrieval**: Top-k relevant chunks dari knowledge base
- **LLM Generation**: TinyLlama 1.1B untuk generate context-aware answers
- **Smart Fallback**: Rule-based responses jika LLM tidak tersedia

### 💬 Chat Interface
- Real-time chatbot dengan streaming responses
- Responsive design untuk mobile & desktop
- Retrieval confidence scores ditampilkan
- Suggestion buttons untuk quick learning

### 📚 Knowledge Base
- 25 semantic chunks dari batik knowledge
- Embedding vectors (384-dimensional / all-MiniLM-L6-v2)
- FAISS index untuk O(1) retrieval complexity
- Comprehensive batik information (sejarah, motif, proses, warisan, regional)

## 🏗️ System Architecture

```
User Query
    ↓
Embedding (sentence-transformers)
    ↓
FAISS Index Search (top-k retrieval)
    ↓
Build Context (chunks + scores)
    ↓
LLM Prompt Engineering
    ↓
TinyLlama 1.1B Generation
    ↓
Response + Metadata
```

## 📋 Persyaratan

- Python 3.9+
- CUDA-compatible GPU (recommended) atau CPU (slower)
- 3-4GB RAM untuk model inference
- Docker & Docker Compose (untuk deployment)

## 🚀 Cara Menjalankan

### Opsi 1: Lokal (tanpa Docker)

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Ensure artifacts exist** (FAISS index, chunks, embeddings):
```bash
# artifacts/ folder harus berisi:
# - chunks.json
# - embeddings.npy
# - faiss.index
```

3. **Jalankan aplikasi:**
```bash
python app.py
```

4. **Akses di browser:**
```
http://localhost:5000
```

### Opsi 2: Docker Compose (Recommended)

1. **Build dan jalankan:**
```bash
docker-compose up --build
```

2. **Akses di browser:**
```
http://localhost:5000
```

3. **Untuk stop:**
```bash
docker-compose down
```

## 🔍 API Endpoints

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

## 📁 Struktur Proyek

```
AI-Tutor/
├── app.py                      # Flask app dengan RAG + LLM
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container config
├── docker-compose.yml          # Docker Compose setup
│
├── templates/
│   └── index.html             # Chat UI
│
├── static/
│   ├── css/
│   │   └── style.css          # Batik-themed styling
│   └── js/
│       └── chat.js            # Chat functionality
│
└── artifacts/
    ├── chunks.json            # 25 knowledge chunks
    ├── embeddings.npy         # FAISS vectors (25×384)
    └── faiss.index            # Searchable index
```

## 🎯 Model Configuration

### Embedder Model
- **Name**: `sentence-transformers/all-MiniLM-L6-v2`
- **Dimension**: 384
- **Speed**: 50K sentences/sec on CPU
- **Size**: 22MB

### LLM Model
- **Name**: `TinyLlama-1.1B-Chat-v1.0`
- **Parameters**: 1.1 Billion
- **Language**: Bahasa Indonesia (fine-tuned)
- **Memory**: ~2.2GB (float16)
- **Speed**: ~30-40 tokens/sec on CPU

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
MODEL_NAME = "TinyLlama/..."

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
docker-compose -f docker-compose.yml up -p 8000:5000
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

## 🎓 Learning Path

1. **Understand RAG**: Read about Retrieval Augmented Generation
2. **Try Basic Chat**: Test dengan suggestion prompts
3. **Check Metadata**: Lihat retrieval scores dan sources
4. **Explore Notebook**: See `AI_Tutor.ipynb` untuk detail teknis

## 🚀 Production Deployment

Untuk production:

```bash
# Use gunicorn instead of Flask development server
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Scale with Docker
docker-compose up -d --scale chatbot=3

# Use load balancer (nginx)
# Add monitoring (prometheus/grafana)
```

## 📝 License

Bagian dari Riset KAIT 2026, Politeknik Elektronika Negeri Surabaya.

## 👥 Authors

Tim AI-Tutor @ PENS

---

**Dibuat dengan ❤️ untuk melestarikan warisan budaya Batik Indonesia** 🎨

*Last Updated: March 5, 2026*
