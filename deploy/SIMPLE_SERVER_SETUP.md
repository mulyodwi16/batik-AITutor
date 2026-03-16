# Simple Server Setup untuk Batik AI-Tutor

Setup app di server dengan **auto-restart service** (tanpa Tailscale/ngrok, langsung IP).

## Yang Kamu Butuh

- Linux server (Ubuntu/Debian recommended)
- Python 3.9+
- Ollama installed
- Nginx installed

---

## Step 1: Upload Project

```bash
# Di server, clone project
cd /opt
git clone https://github.com/mulyodwi16/batik-AITutor.git
cd batik-AITutor
```

## Step 2: Setup Python & Artifacts

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Generate artifacts (one-time)
python setup-artifacts-new.py

# Check artifacts exist
ls -la artifacts/chunks.json artifacts/faiss.index artifacts/embeddings.npy
```

## Step 3: Setup Ollama Service (auto-start)

**File: `/etc/systemd/system/ollama.service`**

```ini
[Unit]
Description=Ollama LLM Service
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/ollama serve
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable & start:**
```bash
sudo systemctl enable ollama.service
sudo systemctl start ollama.service
sudo systemctl status ollama.service
```

**Verify model:**
```bash
ollama pull qwen2.5:14b
ollama list
```

## Step 4: Setup Flask App Service (auto-start)

**File: `/etc/systemd/system/batik-app.service`**

```ini
[Unit]
Description=Batik AI-Tutor Flask App
After=network.target ollama.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/batik-AITutor
Environment="PATH=/opt/batik-AITutor/venv/bin"
ExecStart=/opt/batik-AITutor/venv/bin/python /opt/batik-AITutor/app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Enable & start:**
```bash
sudo systemctl enable batik-app.service
sudo systemctl start batik-app.service
sudo systemctl status batik-app.service
```

**Check logs:**
```bash
sudo journalctl -u batik-app.service -f
```

## Step 5: Setup Nginx (Reverse Proxy)

**File: `/etc/nginx/sites-available/batik-ai-tutor`**

Copy content dari: `/opt/batik-AITutor/deploy/nginx/batik-ai-tutor.conf`

```bash
sudo cp /opt/batik-AITutor/deploy/nginx/batik-ai-tutor.conf /etc/nginx/sites-available/batik-ai-tutor
```

Edit file:
```bash
sudo nano /etc/nginx/sites-available/batik-ai-tutor
```

Ganti:
```nginx
alias /var/www/batik-ai-tutor/static/;
```

Jadi (sesuai path kamu):
```nginx
alias /opt/batik-AITutor/static/;
```

**Enable site:**
```bash
sudo ln -s /etc/nginx/sites-available/batik-ai-tutor /etc/nginx/sites-enabled/
```

**Test config:**
```bash
sudo nginx -t
```

Output should be:
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration will be successful
```

**Restart Nginx:**
```bash
sudo systemctl restart nginx
sudo systemctl status nginx
```

## Step 6: Test

**Health check:**
```bash
curl http://localhost:5000/api/health
```

**Via Nginx:**
```bash
curl http://localhost/api/health
```

**Chat test:**
```bash
curl -X POST http://localhost/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Apa itu Batik?"}'
```

**Via browser:**
```
http://YOUR_SERVER_IP/
```

---

## Managing Services

### Check status
```bash
sudo systemctl status ollama.service
sudo systemctl status batik-app.service
sudo systemctl status nginx
```

### View logs
```bash
# Ollama
sudo journalctl -u ollama.service -f

# Flask app
sudo journalctl -u batik-app.service -f

# Nginx
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

### Restart service
```bash
sudo systemctl restart batik-app.service
sudo systemctl restart ollama.service
sudo systemctl restart nginx
```

### Stop service
```bash
sudo systemctl stop batik-app.service
sudo systemctl stop ollama.service
sudo systemctl stop nginx
```

---

## After Reboot

Services akan **auto-start** otomatis.

Verify:
```bash
sudo systemctl status ollama.service
sudo systemctl status batik-app.service
sudo systemctl status nginx
```

---

## Troubleshooting

**Port 5000 gagal (Flask app tidak jalan)?**
```bash
# Check service error
sudo journalctl -u batik-app.service -n 50

# Manually test
cd /opt/batik-AITutor
source venv/bin/activate
python app.py
```

**Nginx return 502 (bad gateway)?**
```bash
# Check if Flask app running
curl http://localhost:5000/api/health

# Check Nginx error log
sudo tail -f /var/log/nginx/error.log

# Verify Nginx config
sudo nginx -t
```

**Ollama not responding?**
```bash
# Check service
sudo systemctl status ollama.service

# Manual start
ollama serve

# Check model
ollama list
```

**Permission denied?**
```bash
# Make sure files readable
sudo chown -R www-data:www-data /opt/batik-AITutor
sudo chmod -R 755 /opt/batik-AITutor
```

---

## Monitoring

**Real-time access log:**
```bash
sudo tail -f /var/log/nginx/access.log | grep api/chat
```

**Check active processes:**
```bash
ps aux | grep -E 'ollama|python|nginx'
```

**Memory usage:**
```bash
free -h
```

---

## Summary

✅ Ollama auto-restart when crash
✅ Flask app auto-restart when crash  
✅ Nginx reverse proxy
✅ Auto-start on server reboot
✅ Access via: `http://YOUR_SERVER_IP/`

Done! 🎉
