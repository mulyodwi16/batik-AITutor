# Tailscale Funnel Deployment Guide

Menggunakan Tailscale Funnel untuk expose Batik AI-Tutor ke internet tanpa open port firewall.

## Architecture

```
Internet (publik)
    ↓
Tailscale Funnel (HTTPS endpoint)
    ↓
Server (port 80) 
    ↓
Nginx (reverse proxy)
    ↓
Gunicorn:8000 (app server)
    ↓
Flask (app) + Ollama (LLM)
```

## Prerequisites

1. Server dengan Tailscale installed
2. Domain Tailcale (otomatis saat login)
3. Gunicorn & Nginx installed

## Step-by-Step Deployment

### 1. Install Tailscale (di server)

**Linux:**
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
# Copy & paste auth link ke browser, login dengan account kamu
```

**macOS:**
```bash
brew install tailscale
tailscale up
```

**Windows Server:**
```powershell
winget install Tailscale.Tailscale
tailscale up
```

### 2. Setup Project di Server

```bash
# Clone or upload project
cd /opt/batik-ai-tutor  # atau folder lain

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Gunicorn & Nginx
pip install gunicorn
sudo apt install nginx  # Linux
# atau brew install nginx (macOS)
```

### 3. Generate Artifacts (jika belum)

```bash
python setup-artifacts-new.py
# Output: artifacts/chunks.json, embeddings.npy, faiss.index
```

### 4. Config Nginx

Copy config template ke Nginx:

**Linux/macOS:**
```bash
sudo cp deploy/nginx/batik-ai-tutor-tailscale.conf /etc/nginx/sites-available/batik-ai-tutor
sudo ln -s /etc/nginx/sites-available/batik-ai-tutor /etc/nginx/sites-enabled/
sudo nginx -t  # test config
sudo systemctl restart nginx
```

**Windows:**
Sesuaikan path di `nginx.conf` untuk point ke config file kamu.

### 5. Start Services

**Terminal 1 - Ollama:**
```bash
ollama serve
# atau: nohup ollama serve > ollama.log 2>&1 &
```

**Terminal 2 - Gunicorn:**
```bash
cd /opt/batik-ai-tutor
source venv/bin/activate
gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app
# atau: nohup gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app > gunicorn.log 2>&1 &
```

**Terminal 3 - Enable Tailscale Funnel:**
```bash
sudo tailscale funnel 80
# atau 443 jika punya SSL cert
```

Output akan seperti:
```
Your app is available at:
https://your-hostname-xxxxx.ts.net/
```

Copy URL itu → sudah bisa diakses dari internet!

### 6. Test

```bash
# Test health endpoint
curl https://your-hostname-xxxxx.ts.net/api/health

# Test chat
curl -X POST https://your-hostname-xxxxx.ts.net/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Apa itu Batik?"}'
```

## Optional: Systemd Service Files (Linux)

Agar services auto-start setelah reboot.

**File: /etc/systemd/system/ollama.service**
```ini
[Unit]
Description=Ollama LLM Service
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/opt/batik-ai-tutor
ExecStart=/usr/bin/ollama serve
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**File: /etc/systemd/system/batik-gunicorn.service**
```ini
[Unit]
Description=Batik AI-Tutor Gunicorn
After=network.target ollama.service

[Service]
Type=notify
User=your_user
WorkingDirectory=/opt/batik-ai-tutor
Environment="PATH=/opt/batik-ai-tutor/venv/bin"
ExecStart=/opt/batik-ai-tutor/venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable & start:
```bash
sudo systemctl enable ollama.service
sudo systemctl enable batik-gunicorn.service
sudo systemctl start ollama.service
sudo systemctl start batik-gunicorn.service
```

## Troubleshooting

### Funnel endpoint 404
- Pastikan Nginx running: `systemctl status nginx`
- Check config: `sudo nginx -t`
- Restart Nginx: `sudo systemctl restart nginx`

### Timeout saat chat
- Ollama mungkin lambat first time
- Increase Nginx proxy_read_timeout (lihat config di atas)
- Check Ollama status: `ollama ps`

### Tailscale connection drop
- Reconnect: `sudo tailscale up`
- Check status: `tailscale status`

### Port binding error
- Pastikan port 80 tidak dipakai app lain
- Check: `sudo lsof -i :80`
- Kill process jika perlu: `sudo kill -9 <PID>`

## Monitoring

Check logs:
```bash
# Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Gunicorn
tail -f /tmp/gunicorn.log

# Ollama
tail -f /tmp/ollama.log
```

## Access Control (Optional)

Tailscale Funnel punya access control built-in. Kelaur untuk manage di:
- https://login.tailscale.com/admin/acls

Contoh: hanya IP tertentu bisa akses:

```yaml
{
  "acls": [
    {
      "action": "accept",
      "src": ["your-ip"],
      "dst": ["*:80,443"],
    },
  ],
}
```

## URLs

- UI: `https://your-hostname-xxxxx.ts.net/`
- Chat API: `POST https://your-hostname-xxxxx.ts.net/api/chat`
- Health: `GET https://your-hostname-xxxxx.ts.net/api/health`

Selesai! 🎉
