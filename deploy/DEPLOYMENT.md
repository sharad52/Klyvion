# Deploying Klyvion to klyvion.sharadbhandari.com.np

This guide takes you from the repo to a live, HTTPS-protected demo that
visitors can use from your portfolio. It's written for the recommended
subdomain **`klyvion.sharadbhandari.com.np`** — short, memorable, and obvious in
a nav bar. (Alternatives: `tts.` or `speak.` — just substitute throughout.)

**What visitors get:** a web page (bundled at `/`) with a text box, the four
preset voices, a voice-cloning uploader, and a live waveform player. The REST
API and interactive docs (`/docs`) stay available for technically curious
recruiters.

---

## 0. Choose your hosting path first

XTTS v2 is a real neural model. This decides everything else:

| Path | Cost | Quality | Speed | Effort |
|------|------|---------|-------|--------|
| **A. VPS, CPU** (recommended) | ~$10–17/mo | Full XTTS | ~20–60 s per paragraph | this guide |
| **B. GPU cloud** | $150+/mo or per-second billing | Full XTTS | ~1–3 s | overkill for a portfolio |
| **C. Hugging Face Spaces (free)** + redirect | $0 | Full XTTS | slow, cold starts | see Appendix |
| **D. VPS, `pyttsx3` lite engine** | ~$5/mo | robotic | instant | not demo-worthy |

**Path A sizing:** XTTS on CPU needs **~6–8 GB RAM** and works best with 4
vCPUs. Good fits: Hetzner CPX31/CX32 (~€8–14/mo), DigitalOcean 8 GB
(~$48/mo — pricier), Contabo (~$10/mo, variable performance). Nepal-local
latency doesn't matter much — synthesis time dominates; a Singapore or
Falkenstein region is fine.

The rest of this guide assumes **Path A on Ubuntu 22.04/24.04**.

---

## 1. DNS: point the subdomain at your VPS

You don't need to involve your `.com.np` registrar (Mercantile/register.com.np)
for subdomains — you only add a record wherever your DNS is *hosted*.

**If your DNS is on Cloudflare** (recommended — free, and its proxy absorbs
abusive traffic):

1. Cloudflare dashboard → `sharadbhandari.com.np` → **DNS → Records**
2. Add: `Type A` · `Name voice` · `IPv4 <your-VPS-IP>` · Proxy **ON** (orange)
3. SSL/TLS mode: **Full (strict)** (after step 6 completes)

**If your DNS is at the registrar / cPanel:** add the same A record
(`voice` → VPS IP) in its DNS zone editor. Propagation for `.com.np` zones is
usually minutes but can take a few hours.

Verify: `dig +short klyvion.sharadbhandari.com.np` returns your IP (or
Cloudflare IPs if proxied).

---

## 2. Prepare the VPS

```bash
ssh root@<your-vps-ip>

# a non-root user
adduser sharad && usermod -aG sudo,docker sharad 2>/dev/null || true

# firewall: SSH + web only
ufw allow OpenSSH && ufw allow 80,443/tcp && ufw enable

# Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker sharad
```

Log back in as `sharad` before continuing.

---

## 3. Get the code and build the image

```bash
git clone https://github.com/sharad52/klyvion
cd klyvion
docker compose build       # ~15–25 min: bakes the 2 GB XTTS model into the image
```

Baking the model into the image (see `Dockerfile`) means the first visitor
never waits on a download and redeploys are instant. The
`COQUI_TOS_AGREED=1` env var accepts the Coqui model license
non-interactively — read it once yourself first (it restricts *commercial*
use of the model weights; a free portfolio demo is fine).

Before building, edit `docker-compose.yml` if needed:

- `KLYVION_CORS_ORIGINS` — already set to your domains
- `KLYVION_ENABLE_CLONING: "0"` — flip this if you'd rather launch a
  synthesis-only demo first (see "Abuse" below)

```bash
docker compose up -d
curl http://127.0.0.1:8000/healthz     # {"status":"ok"}  (takes ~1–2 min to warm)
```

Note the compose file binds to `127.0.0.1:8000` — the container is *never*
directly exposed to the internet; only nginx is.

---

## 4. Install nginx as the public front door

```bash
sudo apt install -y nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/klyvion
sudo ln -s /etc/nginx/sites-available/klyvion /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

The provided config does three important things:

1. **Rate-limits `/synthesize` to 6 requests/minute per IP** — one CPU
   synthesis pegs a core for up to a minute, so this is what keeps a single
   visitor (or bot) from taking your demo down
2. Sets `proxy_read_timeout 180s` so long syntheses don't 504
3. Allows 20 MB bodies for voice-sample uploads

At this point `http://klyvion.sharadbhandari.com.np` should already load the UI.

---

## 5. HTTPS with Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d klyvion.sharadbhandari.com.np
```

Certbot edits the nginx config, obtains the certificate, and installs an
auto-renewal timer. Choose "redirect HTTP → HTTPS" when asked.

> **Cloudflare proxy note:** if the orange cloud is ON, temporarily set the
> DNS record to "DNS only" for the certbot run (HTTP-01 validation), then
> re-enable the proxy and set SSL mode to Full (strict).

Verify: `https://klyvion.sharadbhandari.com.np` shows the padlock, `/docs`
loads, and generating speech works end-to-end.

---

## 6. Add it to your portfolio nav

On `sharadbhandari.com.np`, add the work entry:

```html
<a href="https://klyvion.sharadbhandari.com.np"
   target="_blank" rel="noopener">
  Klyvion — open-source TTS &amp; voice cloning
</a>
```

Two portfolio-polish suggestions:

- On your work/projects page, pair the live link with the **GitHub repo
  link** — for a portfolio piece, the code is half the exhibit
- Add a one-line expectation-setter near the link: *"Runs on a small CPU
  server — synthesis takes ~30 s."* Unexplained slowness reads as broken;
  explained slowness reads as honest engineering

The footer of the demo UI already links back to `sharadbhandari.com.np`, so
navigation works both ways.

---

## 7. Operations: the boring essentials

**Redeploys** (after pushing changes):

```bash
cd ~/klyvion && git pull
docker compose build && docker compose up -d
```

Cloned voices survive redeploys — they live in the `klyvion-data` volume.

**Logs & health:**

```bash
docker compose logs -f --tail 100
curl -s localhost:8000/healthz
```

**Uptime monitoring:** point a free checker (UptimeRobot, Better Stack) at
`https://klyvion.sharadbhandari.com.np/healthz`.

**Backups:** the only state worth backing up is the volume:

```bash
docker run --rm -v klyvion-data:/data -v $PWD:/backup alpine \
    tar czf /backup/klyvion-data.tgz /data
```

---

## 8. Abuse, safety, and cost control for a *public* demo

A public voice-cloning endpoint deserves a moment of thought:

- **Cloning abuse** — strangers could upload a voice they don't own. The UI
  states the consent rule, but for a public demo consider launching with
  `KLYVION_ENABLE_CLONING: "0"` (presets only) and enabling cloning later,
  or after adding per-session voice scoping. Also note: cloned voices are
  currently **global** — every visitor sees every visitor's cloned voice.
  That's fine for a toy, but say so on the page or disable cloning.
- **CPU exhaustion** — handled by the nginx rate limit + the 500-char text
  cap (`KLYVION_MAX_TEXT_LEN`). Keep both.
- **Disk growth** — synthesized WAVs go to `/tmp/outputs` inside the
  container and vanish on restart; a weekly `docker compose restart` cron is
  a lazy but effective janitor.
- **Content** — the demo speaks whatever is typed. TTS of typed text is
  low-risk, but the rate limit keeps it from being used as a bulk generation
  service.

---

## Appendix A: zero-cost alternative (Hugging Face Spaces)

If you'd rather not pay for a VPS yet:

1. Create a free **Gradio Space**, install `klyvion[neural]`, and wrap
   `Klyvion.speak()` in a small Gradio interface (~30 lines)
2. Free CPU Spaces sleep after inactivity (cold start ≈ 1–3 min) and don't
   support custom domains, so on your portfolio either link out to the Space
   directly, or create `klyvion.sharadbhandari.com.np` as a **redirect** — a
   Cloudflare Redirect Rule pointing to the Space URL costs nothing

This is a genuinely fine v1: the project link works, the demo runs, and you
can graduate to the VPS path when you want the custom domain to serve the
app itself.

## Appendix B: when you outgrow CPU

If the demo gets real traffic: RunPod/Vast.ai serverless GPU workers billed
per second, or a small always-on GPU instance. The only change needed is
`KLYVION_DEVICE=cuda` and a CUDA base image in the Dockerfile — the
application code is identical.
