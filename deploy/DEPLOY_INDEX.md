# Deployment Documentation Index

Panduan lengkap untuk deploy Batik AI-Tutor ke internet.

## Quick Navigation

### 🚀 Recommended: Tailscale Funnel (Kamu)
- **Setup Time**: 5 menit
- **Complexity**: Sangat mudah
- **Cost**: Gratis
- **Best untuk**: Lab, research, team collaboration
- **File**: [QUICK_START_TAILSCALE.md](QUICK_START_TAILSCALE.md) ← **START HERE**
- **Detailed**: [TAILSCALE_FUNNEL_GUIDE.md](TAILSCALE_FUNNEL_GUIDE.md)

### Alternative Options

1. **Cloudflare Tunnel**
   - Setup Time: 10 menit
   - Complexity: Mudah
   - Best untuk: Production + custom domain
   - (Guide coming soon)

2. **ngrok (Quick Demo)**
   - Setup Time: 2 menit
   - Complexity: Sangat mudah
   - Best untuk: Prototype cepat
   - (Guide coming soon)

3. **Direct Deployment (VPS)**
   - Setup Time: 30 menit
   - Complexity: Medium
   - Best untuk: Full control, production
   - (Guide coming soon)

## Architecture Overview

```
┌─────────────────────────┐
│   Internet (Publik)     │
│ https://xxx.ts.net/     │
└────────────┬────────────┘
             │ (HTTPS)
┌────────────▼────────────┐
│  Tailscale Funnel       │◄──── Your Server
│ (Encrypted Tunnel)      │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│   Nginx (Reverse Proxy) │
│   Port 80/443           │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│ Gunicorn (App Server)   │
│ Port 8000               │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│  Flask + RAG Pipeline   │
│  port 5000 (internal)   │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│  Ollama (LLM)           │
│  Port 11434 (localhost) │
└─────────────────────────┘
```

## Files in This Directory

```
deploy/
├── nginx/
│   ├── batik-ai-tutor.conf              # Standard Nginx config (public IP)
│   └── batik-ai-tutor-tailscale.conf    # Tailscale-optimized config
├── QUICK_START_TAILSCALE.md             # ⭐ 5-minute setup (kamu)
├── TAILSCALE_FUNNEL_GUIDE.md            # Detailed guide
├── DEPLOYMENT_OPTIONS.md                # Option comparison
└── DEPLOY_INDEX.md                      # This file
```

## Checklist Before Deploy

- [ ] Project folder structure verified
- [ ] artifacts/ folder exists (chunks.json, faiss.index, embeddings.npy)
- [ ] Ollama installed at target server
- [ ] Ollama model `qwen2.5:14b` pulled
- [ ] Python venv created & dependencies installed
- [ ] Gunicorn tested locally
- [ ] Nginx config tested (`nginx -t`)

## Performance Expectations

| Metric | Value |
|--------|-------|
| Embedding inference | ~100ms (CPU) |
| FAISS retrieval | <10ms |
| Ollama LLM generation | 5-15s (first time) |
| Total response time | 10-20s |
| Concurrent users | 2-5 (single Gunicorn worker) |

**Optimization Tips:**
- Use GPU for Ollama (`CUDA_VISIBLE_DEVICES=0 ollama serve`)
- Increase Gunicorn workers: `-w 4` (if server has resources)
- Enable Nginx caching for static files (already configured)
- Close browser tabs that aren't using it (save RAM)

## Monitoring & Logs

```bash
# Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Gunicorn
ps aux | grep gunicorn

# Ollama
ollama ps

# Tailscale
sudo tailscale status
```

## Next Steps

1. **If using Tailscale Funnel** (recommended):
   - Read: [QUICK_START_TAILSCALE.md](QUICK_START_TAILSCALE.md)
   - Execute 5 steps
   - Share endpoint

2. **If using other options**:
   - Pick from [DEPLOYMENT_OPTIONS.md](DEPLOYMENT_OPTIONS.md)
   - Follow detailed guide (coming soon)

## Troubleshooting

**Chat endpoint timeout?**
- Check if Ollama is running: `ollama ps`
- Check Gunicorn logs for errors
- First LLM response is slow (normal)

**Funnel endpoint 404?**
- Verify Nginx is running: `systemctl status nginx`
- Test config: `sudo nginx -t`
- Check proxy settings in nginx config

**Can't connect to funnel?**
- Tailscale connection check: `tailscale status`
- Reconnect: `sudo tailscale up`
- View Funnel status: `sudo tailscale funnel status`

**Port already in use?**
- Linux: `sudo lsof -i :80` then `sudo kill -9 <PID>`
- Make sure only one Nginx instance running

## Support & References

- Tailscale Docs: https://tailscale.com/kb/
- Gunicorn Docs: https://gunicorn.org/
- Nginx Docs: https://nginx.org/en/docs/
- Flask Docs: https://flask.palletsprojects.com/

---

**Questions?** Check the specific guide for your chosen deployment method. 🚀
