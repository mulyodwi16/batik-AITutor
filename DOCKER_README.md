# AI Tutor Chatbot - Docker Setup

Simple chatbot website yang menggunakan Flask dan data dari artifacts.

## Commands untuk deployment:

```bash
# Build image
docker build -t ai-chatbot .

# Run container
docker run -p 5000:5000 ai-chatbot

# Atau menggunakan docker-compose
docker-compose up --build
```

Akses di: http://localhost:5000

## File Structure
- `app.py` - Flask application
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration
- `docker-compose.yml` - Docker Compose setup
- `artifacts/` - Data files (chunks.json, embeddings.npy, faiss.index)

## Testing
Buka http://localhost:5000 di browser dan coba tanya sesuatu tentang Batik atau Indonesia.
