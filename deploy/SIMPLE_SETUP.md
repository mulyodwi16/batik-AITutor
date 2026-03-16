# Simple Setup Guide - Batik AI-Tutor

Langsung jalan tanpa perlu prosedur rumit.

## Prerequisites

- Server dengan Python 3.9+
- Ollama installed & qwen2.5:14b pulled
- Git untuk clone repo

## 1. Clone & Setup (First Time Only)

```bash
# Clone repo
git clone https://github.com/mulyodwi16/batik-AITutor.git
cd batik-AITutor

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
# atau Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 2. Generate Artifacts (First Time Only)

```bash
python setup-artifacts-new.py
# Output: artifacts/chunks.json, artifacts/faiss.index, artifacts/embeddings.npy
```

## 3. Run App

```bash
# Make sure Ollama is running in another terminal
ollama serve

# In new terminal:
source venv/bin/activate
python app.py
```

Access: `http://localhost:5000`

## 4. Make It Auto-Start (Systemd Service)

Agar auto-start saat server reboot.

### Create Service File

**Linux/macOS:**

```bash
# Create service file
sudo nano /etc/systemd/system/batik-ai-tutor.service
```

Paste config:

```ini
[Unit]
Description=Batik AI-Tutor Flask App
After=network.target ollama.service

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/batik-AITutor
Environment="PATH=/path/to/batik-AITutor/venv/bin"
ExecStart=/path/to/batik-AITutor/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Replace:
- `your_username` → output dari: `whoami`
- `/path/to/batik-AITutor` → output dari: `pwd` (saat di folder project)

### Enable & Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable batik-ai-tutor.service

# Start service now
sudo systemctl start batik-ai-tutor.service
```

### Check Status

```bash
# View status
sudo systemctl status batik-ai-tutor.service

# View logs (live)
sudo journalctl -u batik-ai-tutor.service -f

# Stop service
sudo systemctl stop batik-ai-tutor.service

# Restart service
sudo systemctl restart batik-ai-tutor.service
```

## 5. Update from GitHub

```bash
# Pull latest changes
git pull origin main

# Restart service (if running)
sudo systemctl restart batik-ai-tutor.service
```

## 6. Access from Network

App runs on `localhost:5000` (only local network).

### Option A: Direct IP (if on same network)

Find server IP:
```bash
hostname -I
# or: ifconfig
```

Access from another PC: `http://<server-ip>:5000`

### Option B: Tailscale Funnel (Public Internet)

```bash
sudo tailscale funnel 5000
```

Endpoint: `https://your-hostname-xxx.ts.net/`

---

## That's It!

**Workflow:**
```
1. git pull                    (update code)
2. python setup-artifacts.py   (first time only)
3. python app.py               (run app)
4. systemctl enable & start    (auto-start on reboot)
5. journalctl -f              (monitor logs)
```

Simple & straightforward. 🎉
