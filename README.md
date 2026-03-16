# Batik AI-Tutor

A Flask-based RAG chatbot for Indonesian batik learning.

## Current Workflow (Verified)

1. Source knowledge files live in `RawDataforChunking/`.
2. Run `setup-artifacts-new.py` to generate:
   - `artifacts/chunks.json`
   - `artifacts/embeddings.npy`
   - `artifacts/faiss.index`
3. Run `app.py`.
4. Frontend in `templates/index.html` + `static/js/chat.js` calls `POST /api/chat`.
5. Backend pipeline in `app.py`:
   - embed query (MiniLM)
   - retrieve with FAISS
   - optional location filter from metadata
   - send context to Ollama model `qwen2.5:14b`
   - return answer + retrieval metadata

## Project Structure

- `app.py` - main Flask app and RAG pipeline
- `setup-artifacts-new.py` - artifact generator from `RawDataforChunking/`
- `wsgi.py` - Gunicorn entrypoint
- `templates/` - web UI templates
- `static/` - CSS and JS assets
- `artifacts/` - generated retrieval artifacts
- `deploy/nginx/batik-ai-tutor.conf` - Nginx reverse proxy example

## Requirements

- Python 3.9+
- Ollama running on `http://localhost:11434`
- Ollama model: `qwen2.5:14b`

## Quick Start (Local)

```bash
pip install -r requirements.txt
python setup-artifacts-new.py
ollama pull qwen2.5:14b
python app.py
```

Open: `http://localhost:5000`

Health check:

```bash
curl http://localhost:5000/api/health
```

## Production Suggestion (Nginx + Gunicorn)

For exposed `POST /api/chat`, use Gunicorn behind Nginx.

1. Start app with Gunicorn:

```bash
gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app
```

2. Use Nginx config template from:

- `deploy/nginx/batik-ai-tutor.conf`

3. Point static alias in that file to your deployed static folder, e.g. `/var/www/batik-ai-tutor/static/`.

Benefits:
- better connection handling and buffering
- easier TLS/HTTPS termination
- cleaner production routing and logging
- safer public exposure of `/api/chat`

## API

### `POST /api/chat`
Request:

```json
{
  "message": "Apa motif batik Surabaya?"
}
```

Response:

```json
{
  "reply": "...",
  "timestamp": "...",
  "metadata": {
    "retrieved_chunks": [0, 1],
    "retrieval_scores": [0.12, 0.18],
    "model_used": "RAG+LLM",
    "has_context": true,
    "top_score": 0.12,
    "answer_length": 120
  }
}
```

### `GET /api/health`
Returns model/artifact readiness state.
