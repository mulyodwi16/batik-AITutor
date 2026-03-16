# Quick Start: Tailscale Funnel (5 Menit)

## Prerequisite Checklist

- [ ] Server dengan Linux/macOS/Windows
- [ ] Sudah punya Tailscale account
- [ ] Tailscale CLI installed di server

## Step 1: Prepare Server (2 menit)

```bash
# Login Tailscale
sudo tailscale up
# Copy link ke browser & authenticate

# Verify:
tailscale status
```

## Step 2: Setup Project (2 menit)

```bash
cd /opt/batik-ai-tutor  # atau folder project kamu

# Pastikan artifacts sudah ada
ls artifacts/chunks.json artifacts/faiss.index artifacts/embeddings.npy
```

## Step 3: Start Services (1 menit)

**Terminal 1:**
```bash
ollama serve &
```

**Terminal 2:**
```bash
source venv/bin/activate
gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app &
```

**Terminal 3:**
```bash
# Setup Nginx (Linux)
sudo cp deploy/nginx/batik-ai-tutor-tailscale.conf /etc/nginx/sites-available/batik-ai-tutor
sudo ln -s /etc/nginx/sites-available/batik-ai-tutor /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# atau testing manually:
sudo nginx -c /etc/nginx/nginx.conf -g 'daemon off;'
```

## Step 4: Enable Funnel (1 menit)

```bash
sudo tailscale funnel 80
```

Output:
```
Your app is available at:
https://your-hostname-abc123.ts.net/
```

## Step 5: Test & Share (1 menit)

```bash
# Test health
curl https://your-hostname-abc123.ts.net/api/health

# Share link!
https://your-hostname-abc123.ts.net/
```

## That's It! 🎉

App sudah live dan accessible dari internet!

### Commands Quick Reference

```bash
# Check Tailscale status
tailscale status

# View Funnel info
sudo tailscale funnel status

# Disable Funnel
sudo tailscale funnel --reset 80

# Logs
journalctl -u nginx -f
```

### If Something Wrong

```bash
# Restart everything
sudo systemctl restart nginx
killall gunicorn
ollama serve &
gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app &
```

### Monitoring

```bash
# Real-time logs
tail -f /var/log/nginx/access.log

# Check processes
ps aux | grep -E 'nginx|gunicorn|ollama'

# Check ports
sudo lsof -i -P -n | grep LISTEN
```

Done! Enjoy your Batik AI-Tutor online! 🎨
