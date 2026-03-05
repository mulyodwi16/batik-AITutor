# 🎨 Batik AI-Tutor

Chatbot pendidikan interaktif untuk mempelajari warisan budaya Batik Indonesia. Dibangun dengan Flask, berorientasi pada pembelajaran tentang sejarah, motif, proses pembuatan, dan pentingnya batik dalam budaya Indonesia.

## ✨ Fitur

- **Chat Interface Modern**: Antarmuka chatbot yang responsif dan user-friendly
- **Konten Batik Lengkap**: Informasi tentang sejarah, motif, proses, dan warisan UNESCO
- **Deployment Docker**: Mudah di-deploy menggunakan Docker dan Docker Compose
- **Suggestion Buttons**: Pertanyaan contoh untuk memandu pembelajaran
- **Sidebar Navigation**: Menu kategori untuk eksplorasi cepat
- **Mobile Responsive**: Bekerja sempurna di desktop dan mobile

## 📋 Persyaratan

- Python 3.9+
- Docker & Docker Compose (untuk deployment)
- Modern web browser

## 🚀 Cara Menjalankan

### Opsi 1: Lokal (tanpa Docker)

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Jalankan aplikasi:**
```bash
python app.py
```

3. **Buka di browser:**
```
http://localhost:5000
```

### Opsi 2: Docker Compose (Recommended)

1. **Build dan jalankan:**
```bash
docker-compose up --build
```

2. **Buka di browser:**
```
http://localhost:5000
```

3. **Untuk stop:**
```bash
docker-compose down
```

### Opsi 3: Docker Manual

1. **Build image:**
```bash
docker build -t batik-ai-tutor .
```

2. **Jalankan container:**
```bash
docker run -p 5000:5000 batik-ai-tutor
```

## 📁 Struktur Proyek

```
AI-Tutor/
├── app.py                      # Flask application
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker configuration
├── docker-compose.yml          # Docker Compose setup
├── .env                        # Environment variables
├── .dockerignore               # Docker ignore file
│
├── templates/
│   └── index.html             # HTML template
│
├── static/
│   ├── css/
│   │   └── style.css          # Styling
│   └── js/
│       └── chat.js            # Chat functionality
│
└── artifacts/
    ├── chunks.json            # Knowledge base chunks
    ├── embeddings.npy         # FAISS embeddings
    └── faiss.index            # FAISS index
```

## 🎓 Topik Pembelajaran

Bot dapat menjawab pertanyaan tentang:
- **Sejarah**: Perkembangan batik di Indonesia
- **Motif**: Berbagai motif batik dan maknanya
- **Proses**: Cara pembuatan batik tradisional
- **Warna**: Pewarnaan alami dalam batik
- **Warisan**: Status UNESCO dan pentingnya batik
- **Regional**: Batik dari berbagai daerah (Yogyakarta, Semarang, Cirebon, dll)

## 🔧 Konfigurasi

Edit `.env` untuk konfigurasi:
```env
FLASK_APP=app.py
FLASK_ENV=development
DEBUG=True
```

## 📝 API Endpoints

### GET `/`
Menampilkan halaman chatbot utama

### POST `/api/chat`
Submit pesan dan dapatkan respons
```json
{
  "message": "Apa itu batik?"
}
```

Response:
```json
{
  "reply": "Batik adalah teknik pewarnaan kain...",
  "timestamp": "2026-03-05T12:00:00.000000"
}
```

### GET `/api/suggestions`
Dapatkan daftar pertanyaan yang disarankan

## 🎨 Customization

### Mengubah Warna (CSS)
Edit [static/css/style.css](static/css/style.css) di bagian `:root`:
```css
:root {
    --primary-color: #8B4513;
    --secondary-color: #D2691E;
    --accent-color: #FF8C00;
}
```

### Menambah Knowledge
Edit bagian `batik_knowledge` di [app.py](app.py) untuk menambah konten baru.

## 📦 Teknologi

- **Backend**: Flask 2.3.2
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Database**: FAISS (vector search)
- **Containerization**: Docker, Docker Compose
- **Python**: 3.9

## 🐛 Troubleshooting

**Port 5000 sudah digunakan?**
```bash
docker-compose up -p 8000:5000
```

**Import error saat menjalankan?**
```bash
pip install --upgrade -r requirements.txt
```

**Container tidak start?**
```bash
docker-compose logs chatbot
```

## 📖 Dokumentasi Lebih Lanjut

- Lihat file sumber untuk detail implementasi
- Dokumentasi Flask: https://flask.palletsprojects.com/
- Dokumentasi Docker: https://docs.docker.com/

## 📄 Lisensi

Proyek ini adalah bagian dari Riset KAIT 2026, Politeknik Elektronika Negeri Surabaya.

## 👥 Kontribusi

Untuk kontribusi, silakan buat issue atau pull request.

---

**Dibuat dengan ❤️ untuk melestarikan warisan budaya batik Indonesia** 🎨
