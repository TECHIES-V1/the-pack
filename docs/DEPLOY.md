# Pack — Production Deploy (Alibaba Cloud)

Plain-language runbook to put Pack on the internet: one **ECS** server runs the engine +
gateway + frontend (via Docker), talking to managed **ApsaraDB RDS** (Postgres) and **Tair**
(Redis). Everything in **Singapore (`ap-southeast-1`)**, same VPC.

```
 Internet ──https──▶ ECS box (Docker) ──private VPC──▶ RDS (Postgres) + Tair (Redis)
                     ├─ web   (nginx: serves UI, proxies /api and /ws)
                     ├─ engine (FastAPI :8000)
                     └─ gateway (Rust WS :8080)
```

You do the **console clicks + the money**; the repo ships everything else (Dockerfiles, the
compose file, nginx). A deploy is ~5 commands on the server.

---

## Step 1 — Postgres (ApsaraDB RDS)
1. **RDS console → Create Instance**: **PostgreSQL 16**, region **Singapore**, smallest spec,
   pay-as-you-go. Put it in a **VPC** (note the VPC + vSwitch).
2. When **Running**: **Accounts** → create account `pack` (+ password). **Databases** → create
   database `pack`.
3. **Connection** → copy the **VPC (private) endpoint** host + port `5432`. Note if **SSL** is on.
4. Build: `POSTGRES_URL = postgresql://pack:PASSWORD@HOST:5432/pack` (SSL on → `POSTGRES_SSLMODE=require`).

## Step 2 — Redis (Tair)
1. **Tair console → Create Instance**: Redis-compatible, region **Singapore**, smallest spec,
   **same VPC** as the RDS.
2. Set a **password**.
3. **Connection** → copy the **VPC (private) endpoint** host + port `6379`.
4. Build: `REDIS_URL = redis://:PASSWORD@HOST:6379/0` (plain `redis://` is fine inside the VPC).

## Step 3 — The server (ECS)
1. **ECS console → Create Instance**: **Ubuntu 22.04**, region **Singapore**, **same VPC** as
   RDS/Tair, a small instance (2 vCPU / 4 GB is plenty), assign a **public IP**.
2. **Security Group**: allow inbound **22** (SSH), **80** (HTTP), **443** (HTTPS).
3. Note the ECS **public IP** (for browsing) and its **private IP** (for whitelisting).

## Step 4 — Let the server reach the database + redis
- In **RDS → Whitelist** and **Tair → Whitelist**, add the ECS **private IP** (or the VPC's
  CIDR). Same VPC = private, fast, secure.

## Step 5 — Deploy (on the ECS box)
SSH in (`ssh root@<ECS-public-IP>`), then:

```bash
# 1. Install Docker + compose plugin
curl -fsSL https://get.docker.com | sh

# 2. Get the code
git clone <your-repo-url> pack && cd pack/deploy

# 3. Fill in secrets (server-only; never committed)
cp .env.prod.example .env.prod
nano .env.prod        # paste QWEN_API_KEY, POSTGRES_URL, POSTGRES_SSLMODE, REDIS_URL

# 4. Build + start everything
docker compose -f docker-compose.prod.yml up -d --build

# 5. Watch it come up
docker compose -f docker-compose.prod.yml logs -f engine
```

On first boot the engine **auto-creates its tables** in RDS (no manual migration).

## Step 6 — Open it
- App: **`http://<ECS-public-IP>/`** → the Door. Submit a task → approve → watch the hunt.
- API docs: **`http://<ECS-public-IP>/api/docs`** (Swagger).
- Health: `http://<ECS-public-IP>/api/health`.

That's a live production deployment. Steps 7–8 make it polished.

---

## Step 7 — Domain + HTTPS (recommended for the submission)
1. Point a domain's **A record** at the ECS public IP (e.g. `pack.yourdomain.com`).
2. Easiest TLS — Caddy in front, or certbot. Quick certbot path on the box:
   ```bash
   sudo apt-get install -y certbot
   docker compose -f docker-compose.prod.yml stop web   # free port 80 for the challenge
   sudo certbot certonly --standalone -d pack.yourdomain.com
   ```
   Then mount the certs into the `web` service, add a `listen 443 ssl;` server block to
   `deploy/nginx.conf` pointing at `/etc/letsencrypt/live/pack.yourdomain.com/`, uncomment
   `443:443` in `docker-compose.prod.yml`, and `up -d` again. (Alternatively, terminate TLS at
   an Alibaba **SLB/ALB** in front of the box — no nginx cert changes needed.)
3. Once HTTPS is on, the frontend's WS auto-upgrades to `wss://` (no rebuild — `streamClient`
   resolves `/ws` against the page origin).

## Updating a deployment
```bash
cd pack && git pull && cd deploy
docker compose -f docker-compose.prod.yml up -d --build
```

## Troubleshooting
- `docker compose -f docker-compose.prod.yml ps` — what's running.
- `... logs -f engine` / `gateway` / `web` — per-service logs.
- Engine can't reach DB/Redis → check the **whitelists** (Step 4) and that the URLs use the
  **VPC private** endpoints.
- WS not streaming → confirm the Security Group allows 80/443 and that you reached the app over
  the same origin (the `/ws` proxy needs the nginx in this stack).

## Notes
- **Secrets** live only in `deploy/.env.prod` on the server (gitignored). For stricter prod,
  use a secret manager instead of a file.
- **Single box** is correct for the hackathon. The engine keeps each hunt's sequence in memory
  (one process per hunt), so don't run multiple engine replicas without the sticky-routing work
  (that's a post-hackathon item).
- **Cost**: smallest ECS + RDS + Tair, pay-as-you-go, is a few dollars; stop/release them after
  judging to avoid charges.
