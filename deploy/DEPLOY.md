# Deploying The Pack on Alibaba Cloud

Everything runs on **one ECS instance** behind **managed Postgres (RDS) and Redis (Tair)**.
Three Docker containers handle the whole app — nginx serves the frontend and proxies to the Python engine and Rust gateway.

---

## What you will create

| Resource | Product | Notes |
|----------|---------|-------|
| Compute | ECS (ecs.c6.xlarge or larger) | Ubuntu 22.04 LTS, min 4 vCPU / 8 GB RAM |
| Database | ApsaraDB RDS for PostgreSQL 16 | 1 vCPU / 2 GB is fine to start |
| Cache / Streams | ApsaraDB Tair (Redis-compatible) | Standard edition, 1 GB |
| LLM | Qwen via DashScope international | Singapore endpoint |
| Web search | Tavily | External API key |
| Domain (optional) | Any registrar + Alibaba DNS | For HTTPS |

All four Alibaba resources should be in the **same region and the same VPC** so the ECS instance can reach RDS and Tair without going over the public internet.

---

## Step 1 — Alibaba Cloud: create the managed services

### 1a. RDS for PostgreSQL

1. Console → ApsaraDB RDS → Create Instance
2. Engine: **PostgreSQL 16**
3. Zone: pick one zone in your chosen region (e.g. ap-southeast-1a, Singapore)
4. Edition: Basic (one node) is fine for launch
5. Instance class: pg.n2.small.1 (1 vCPU / 2 GB) or larger
6. After creation → **Accounts** tab → Create account:
   - Account name: `pack`
   - Account type: Standard (not privileged)
   - Password: something strong — you will put this in `.env.prod`
7. **Databases** tab → Create database: `pack`, owner `pack`
8. **Connection** tab → note the **VPC internal endpoint** (looks like `rm-xxxxxxxx.pg.rds.aliyuncs.com:5432`) — this is your `POSTGRES_URL` host
9. **Whitelist** tab → add the ECS private IP (you get this in Step 2)

### 1b. Tair (Redis)

1. Console → ApsaraDB for Redis → Create Instance
2. Type: **Tair** (Community edition is fine — it is Redis 7 compatible)
3. Same region and VPC as your RDS
4. Architecture: Standard (no cluster needed)
5. Memory: 1 GB
6. After creation → set a password under **Security** → Password Management
7. Note the **VPC internal endpoint** (looks like `r-xxxxxxxx.redis.rds.aliyuncs.com:6379`)
8. **Whitelist** → add the ECS private IP

### 1c. DashScope API key (Qwen)

1. Go to: https://dashscope-intl.aliyuncs.com
2. Sign in with your Alibaba Cloud account
3. API Keys → Create API Key
4. Note it — this is your `QWEN_API_KEY`
5. Region: use **Singapore (ap-southeast-1)** — the international endpoint already points there

### 1d. Tavily API key (web search)

1. Go to: https://tavily.com → Sign up
2. Dashboard → copy your API key
3. This is your `SEARCH_API_KEY`

---

## Step 2 — ECS: create and configure the server

### Create the instance

1. Console → ECS → Create Instance
2. Image: **Ubuntu 22.04 LTS** (64-bit)
3. Instance type: **ecs.c6.xlarge** (4 vCPU / 8 GB) minimum — the Rust gateway + Python engine + nginx + Docker all live here
4. Same region and VPC as your RDS/Tair
5. Storage: 40 GB system disk (SSD)
6. Network: assign a **public IP** (EIP) or select "Assign public IP"
7. Security group: create one with these inbound rules:
   - TCP 22 (SSH) — from your IP only
   - TCP 80 (HTTP)
   - TCP 443 (HTTPS — for later)
8. After creation, note the **private IP** — add it to your RDS and Tair whitelists (Step 1)

### Install Docker

SSH into the instance, then:

```bash
# Update and install Docker
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

Verify: `docker --version` and `docker compose version`

---

## Step 3 — Upload the code

**Option A — clone from GitHub (recommended):**
```bash
git clone https://github.com/yourorg/the-pack.git
cd the-pack
```

**Option B — rsync from your local machine:**
```bash
rsync -av --exclude='.git' --exclude='node_modules' --exclude='.venv' --exclude='target' \
  "path/to/the pack/" ubuntu@YOUR_ECS_IP:~/the-pack/
```

---

## Step 4 — Configure secrets

On the ECS instance, inside the repo:

```bash
cp deploy/.env.prod.example deploy/.env.prod
nano deploy/.env.prod
```

Fill in every value. The critical ones:

```env
# Qwen
QWEN_API_KEY=sk-your-real-key

# Postgres — VPC internal endpoint from Step 1a
POSTGRES_URL=postgresql://pack:your-password@rm-xxxxxxxx.pg.rds.aliyuncs.com:5432/pack
POSTGRES_SSLMODE=require

# Tair — VPC internal endpoint from Step 1b
REDIS_URL=redis://:your-password@r-xxxxxxxx.redis.rds.aliyuncs.com:6379/0

# Tavily
SEARCH_API_KEY=tvly-your-real-key

# Session secret — generate a fresh one
SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

Protect the file so other users on the box can't read it:
```bash
chmod 600 deploy/.env.prod
```

---

## Step 5 — Build and start

```bash
cd deploy
docker compose -f docker-compose.prod.yml up -d --build
```

This will:
1. Build the **engine** image (Python 3.12, installs deps, copies `backend/`)
2. Build the **gateway** image (Rust multi-stage, produces a ~5 MB binary)
3. Build the **web** image (Node 20 builds the React SPA, copies to nginx)
4. Start all three containers
5. On first start, the engine auto-applies the Postgres schema (idempotent DDL)

**Expected output:**
```
 ✔ Container deploy-gateway-1  Started
 ✔ Container deploy-engine-1   Started
 ✔ Container deploy-web-1      Started
```

Check everything is running:
```bash
docker compose -f docker-compose.prod.yml ps
```

All three should show `Up`.

---

## Step 6 — Verify the deployment

```bash
# 1. Engine health (REST API)
curl http://localhost/api/health
# → {"status":"ok"}

# 2. Gateway health (WebSocket server)
curl http://localhost/ws/health
# → ok

# 3. Frontend
curl -s http://localhost/ | head -5
# → <!doctype html>...
```

Then open `http://YOUR_ECS_PUBLIC_IP` in a browser — you should see The Pack.

Start a hunt and watch the event stream come through in the Territory canvas.

---

## Step 7 — Add HTTPS (strongly recommended)

### Option A — Certbot / Let's Encrypt (free, requires a domain)

```bash
# Point your domain's A record to the ECS public IP first, then:
sudo apt-get install -y certbot

# Stop web container temporarily (needs port 80)
docker compose -f docker-compose.prod.yml stop web

# Get the certificate
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Restart web
docker compose -f docker-compose.prod.yml start web
```

Then update `deploy/nginx.conf` to listen on 443 with SSL:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # ... rest of the existing config (locations for /, /api/, /ws/)
}
```

Mount the certs into the web container — add to `docker-compose.prod.yml` under `web`:
```yaml
volumes:
  - /etc/letsencrypt:/etc/letsencrypt:ro
ports:
  - "80:80"
  - "443:443"
```

Uncomment the `443` port line that's already in the compose file, then rebuild:
```bash
docker compose -f docker-compose.prod.yml up -d --build web
```

### Option B — Alibaba WAF / CDN (no Certbot needed)

Point the Alibaba CDN/WAF at your ECS public IP. SSL terminates at the CDN edge. No cert work needed on the server.

---

## Updating the app

When you push new code:

```bash
# On the ECS instance, inside the repo root
git pull
cd deploy
docker compose -f docker-compose.prod.yml up -d --build
```

Docker only rebuilds layers that changed — usually only the `engine` or `web` layer, not both. The gateway binary rarely changes.

Zero-downtime: `up --build` replaces containers one at a time. WebSocket connections to the gateway will briefly drop during gateway restarts but the `StreamClient` reconnects automatically with exponential backoff.

---

## Viewing logs

```bash
# All containers, live
docker compose -f docker-compose.prod.yml logs -f

# Just the engine (Python)
docker compose -f docker-compose.prod.yml logs -f engine

# Just the gateway (Rust)
docker compose -f docker-compose.prod.yml logs -f gateway
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Engine shows `asyncpg.exceptions.ConnectionDoesNotExistError` | Wrong RDS host or Postgres whitelist | Check `POSTGRES_URL` and that ECS private IP is whitelisted in RDS |
| Engine shows `redis.exceptions.ConnectionError` | Wrong Tair host or Tair whitelist | Check `REDIS_URL` and Tair whitelist |
| Frontend loads but hunts don't stream | Gateway not reachable | `curl http://localhost/ws/health` — if it fails, check gateway container logs |
| Alpha replies with "Couldn't reach Alpha" | Bad or missing `QWEN_API_KEY` | Check key in `.env.prod`, restart engine container |
| Scout always returns empty results | Missing `SEARCH_API_KEY` | Engine falls back to canned results — add Tavily key and restart |
| `docker compose build` fails on gateway | Rust compilation timeout | First build takes ~3-4 min on small instances; use a bigger ECS for the build |

---

## Architecture reference

```
Browser
  │
  │  HTTP (80) or HTTPS (443)
  ▼
┌─────────────────────────────────────────┐
│              nginx (web)                │
│  /           → static React SPA        │
│  /api/*      → engine:8000 (Python)    │
│  /ws/*       → gateway:8080 (Rust)     │
└─────────────────────────────────────────┘
        │                    │
        ▼                    ▼
  ┌──────────┐        ┌──────────────┐
  │  engine  │        │   gateway    │
  │ FastAPI  │──────▶│  Rust/Axum   │
  │ :8000    │ writes │  :8080       │
  └──────────┘ Redis  └──────────────┘
        │                    │
        ▼                    ▼
  ┌──────────┐        ┌──────────────┐
  │ ApsaraDB │        │  Tair/Redis  │
  │ Postgres │        │  event stream│
  │ (truth)  │        │  (projection)│
  └──────────┘        └──────────────┘

engine  = commands, Alpha chat, plan/hold logic, writes events to Postgres + publishes to Redis
gateway = reads Redis Streams, fans live events out to every browser WebSocket
web     = nginx: serves the built React SPA + proxies API/WS to the containers above
```

Postgres is the **source of truth**. Redis is a **projection** — if Tair goes down, events are safe in Postgres and the relay replays them when it comes back.

---

## Cost estimate (monthly, Singapore region)

| Resource | Spec | Est. USD/month |
|----------|------|----------------|
| ECS c6.xlarge | 4 vCPU / 8 GB, pay-as-you-go | ~$60–80 |
| ApsaraDB RDS PostgreSQL | pg.n2.small.1 | ~$25–35 |
| Tair Standard | 1 GB | ~$15–20 |
| EIP (public IP) | — | ~$5 |
| DashScope (Qwen) | Per-token, depends on usage | $0 idle, ~$0.01–0.10/hunt |
| Tavily | Free tier | $0 under 1000 searches/month |
| **Total baseline** | | **~$100–140/month** |

Qwen costs only appear when hunts actually run. A typical 5-step research hunt costs $0.05–$0.20 depending on the strategy.
