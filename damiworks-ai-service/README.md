# DamiWorks AI Service

FastAPI backend — Gemini multi-routing, RAG via Supabase, DamiWorks sales consultant, English School demo.

## Local dev

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install ...  # Linux/Mac
cp .env.example .env                            # fill in real values
uvicorn app.main:app --host 0.0.0.0 --port 8010
```

Health check: `curl http://localhost:8010/health` → `{"status":"ok"}`

## VPS deployment (Docker)

### 1 — Install Docker & Docker Compose

```bash
curl -fsSL https://get.docker.com | sh
# Docker Compose v2 is bundled — verify:
docker compose version
```

### 2 — Copy backend to VPS

```bash
# Option A: clone the monorepo and work from the backend subfolder
git clone https://github.com/your-org/plum-dev.git
cd plum-dev/damiworks-ai-service

# Option B: scp just the backend folder
scp -r damiworks-ai-service/ user@your-vps:/opt/damiworks-api
cd /opt/damiworks-api
```

### 3 — Create .env

```bash
cp .env.example .env
nano .env   # fill GEMINI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
```

Minimum required values:

```env
GEMINI_API_KEY=...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
```

Optional (leave blank to disable Telegram lead notifications):

```env
LEAD_TELEGRAM_BOT_TOKEN=...
LEAD_TELEGRAM_CHAT_ID=...
```

### 4 — Start

```bash
docker compose up -d --build
```

### 5 — Verify

```bash
# Container is healthy
docker compose ps

# Logs (follow)
docker compose logs -f api

# Health endpoint
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

### 6 — Stop / restart

```bash
docker compose down          # stop and remove container
docker compose restart api   # restart without rebuild
docker compose up -d --build # rebuild and restart
```

## Reverse proxy (Caddy — recommended)

Caddy handles HTTPS automatically.

```bash
# Install Caddy
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install caddy

# Copy the Caddyfile
cp Caddyfile /etc/caddy/Caddyfile
systemctl reload caddy
```

The included `Caddyfile` proxies `api.damiworks.com` → `localhost:8000` with automatic TLS.

Point your DNS `A` record for `api.damiworks.com` at the VPS IP before running this.

## Environment variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `GEMINI_API_KEY` | **yes** | — | Backend will not start without this |
| `SUPABASE_URL` | **yes** | — | |
| `SUPABASE_SERVICE_ROLE_KEY` | **yes** | — | |
| `LEAD_TELEGRAM_BOT_TOKEN` | no | `""` | Lead notifications to owner; skipped when empty |
| `LEAD_TELEGRAM_CHAT_ID` | no | `""` | |
| `MAX_HISTORY_MESSAGES` | no | `15` | |
| `RAG_MATCH_COUNT` | no | `3` | |
| `ENABLE_B2B_MEMORY_SUMMARY` | no | `true` | |
| `INTELLIGENCE_SHADOW_ENABLED` | no | `true` | |
| `ENABLE_GENERATION_FALLBACK` | no | `false` | |

## Frontend integration

The Next.js frontend proxies chat through `/api/chat` → this backend. In production set:

```env
FASTAPI_URL=https://api.damiworks.com
```

in the Next.js deployment environment (Vercel or your own hosting).
