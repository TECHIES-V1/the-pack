# How to deploy The Pack — step by step

This guide assumes you have an Alibaba Cloud account and access to the code.
You do not need to know how to code. Just follow each step in order.

If anything goes wrong, the **Troubleshooting** section at the bottom has the common fixes.

---

## What you are setting up

You need 4 things on Alibaba Cloud:

1. **A server (ECS)** — the machine that runs the app
2. **A database (RDS Postgres)** — stores all hunts and conversations
3. **A cache (Tair/Redis)** — streams live events to the browser
4. **A Qwen API key** — the AI brain that powers the pack

And 1 thing from outside Alibaba:

5. **A Tavily API key** — gives the pack real web search ability

Everything should be in the **same region**. Use **Singapore (ap-southeast-1)** — it's the closest region with full Qwen support.

---

## Before you start — accounts you need

- [ ] Alibaba Cloud account with billing enabled
- [ ] A Tavily account (free) — sign up at https://tavily.com
- [ ] The Pack codebase on your computer (or a GitHub repo)

---

## Part 1 — Create the database (RDS Postgres)

This is where all hunt data is saved permanently.

1. Log into Alibaba Cloud console → search for **"RDS"** in the search bar → click **ApsaraDB RDS**
2. Click **Create Instance**
3. Fill in:
   - **Engine:** PostgreSQL
   - **Version:** 16
   - **Region:** Singapore (ap-southeast-1)
   - **Edition:** Basic (cheapest option)
   - **Instance class:** pg.n2.small.1 (1 core, 2 GB — enough to start)
   - **Storage:** 20 GB SSD
4. Click through to payment and confirm — it will take about 5 minutes to be ready

Once it's running:

5. Click on the instance → go to the **Accounts** tab
   - Click **Create Account**
   - Username: `pack`
   - Type: Standard Account
   - Password: make something strong and **write it down** — you will need it later
   
6. Go to the **Databases** tab
   - Click **Create Database**
   - Name: `pack`
   - Owner: `pack` (the account you just created)

7. Go to the **Connection** tab
   - Find the **Internal Endpoint** (it looks like `rm-xxxxxxxx.pg.rds.aliyuncs.com`)
   - **Copy and save this** — you will need it later

The database is ready. Leave this tab open.

---

## Part 2 — Create the cache (Tair/Redis)

This is what streams live events to the browser while a hunt is running.

1. In the Alibaba console → search for **"Tair"** → click **ApsaraDB for Redis (Tair)**
2. Click **Create Instance**
3. Fill in:
   - **Type:** Community Edition (Redis compatible)
   - **Version:** Redis 7.0
   - **Region:** Singapore (same as your database — important)
   - **Architecture:** Standard (single node)
   - **Memory:** 1 GB
4. Confirm and wait for it to be ready (~3 minutes)

Once running:

5. Click on the instance → **Security** → **Password Management**
   - Set a password and **write it down**

6. Go to the **Connection** tab
   - Copy the **Internal Endpoint** (looks like `r-xxxxxxxx.redis.rds.aliyuncs.com:6379`)
   - **Save this**

---

## Part 3 — Create the server (ECS)

This is the machine that runs the app, the AI engine, and the live streaming.

1. In the Alibaba console → search **"ECS"** → click **Elastic Compute Service**
2. Click **Create Instance**
3. Fill in:
   - **Region:** Singapore (same region as your database and cache — very important)
   - **Image:** Ubuntu 22.04 LTS 64-bit
   - **Instance type:** ecs.c6.xlarge (4 vCPU / 8 GB RAM) — do not go smaller
   - **Storage:** 40 GB Enhanced SSD
   - **Network:** Make sure it is in the same VPC as your RDS and Tair
   - **Public IP:** tick "Assign public IP" — you need this to access the server from outside
4. Under **Security Group** — create a new one with these rules:
   - Allow TCP port **22** (SSH — for you to connect)
   - Allow TCP port **80** (HTTP — for the app)
   - Allow TCP port **443** (HTTPS — for secure access later)
5. Set a root password or SSH key (SSH key is safer — use one if you have it)
6. Confirm and wait (~2 minutes)

Once running:
7. Copy the **Public IP address** — you will use this to access the app
8. Copy the **Private IP address** — you need to whitelist it in RDS and Tair

### Whitelist the server in the database and cache

Go back to your **RDS instance** → **Whitelist** tab:
- Click **Add Whitelist Group** → add the server's **private IP** → save

Go back to your **Tair instance** → **Whitelist** tab:
- Same thing — add the server's **private IP** → save

This allows your server to connect to the database and cache.

---

## Part 4 — Get the API keys

### Qwen (the AI)

1. Go to: https://dashscope-intl.aliyuncs.com
2. Sign in with your Alibaba Cloud account
3. Click **API Keys** in the left menu → **Create API Key**
4. Copy the key (starts with `sk-`) and save it

### Tavily (web search)

1. Go to: https://tavily.com
2. Click Sign Up → create a free account
3. After logging in, your API key is on the dashboard
4. Copy it (starts with `tvly-`) and save it

---

## Part 5 — Connect to the server and set it up

You need a terminal app to connect to the server. On Mac it's built in. On Windows, use **PuTTY** or the built-in Windows Terminal.

### Connect via SSH

```
ssh root@YOUR_SERVER_PUBLIC_IP
```

Replace `YOUR_SERVER_PUBLIC_IP` with the IP you copied in Part 3.

If it asks "are you sure you want to continue connecting" — type `yes` and press Enter.

### Install Docker

Copy and paste this entire block into the terminal — press Enter and wait for it to finish (~2 minutes):

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

Check it worked:
```bash
docker --version
```
You should see something like `Docker version 26.x.x` — any version number is fine.

---

## Part 6 — Upload the code to the server

**If the code is on GitHub:**
```bash
git clone https://github.com/YOUR_USERNAME/the-pack.git
cd the-pack
```

**If the code is on your computer (run this from your computer, not the server):**
```bash
rsync -av --exclude='node_modules' --exclude='.venv' --exclude='target' \
  "/path/to/the pack/" root@YOUR_SERVER_IP:~/the-pack/
```

Then on the server:
```bash
cd ~/the-pack
```

---

## Part 7 — Fill in your secrets

This is the most important step. You are creating a file that tells the app all the passwords and keys it needs.

On the server, run:
```bash
cp deploy/.env.prod.example deploy/.env.prod
nano deploy/.env.prod
```

This opens a text editor. Fill in the values below. Use the arrow keys to move around, edit the text, then press **Ctrl+X**, then **Y**, then **Enter** to save.

Here is what to change — replace every `replace-me` with your real values:

```
QWEN_API_KEY=          ← paste your Qwen key here (the sk-... one)
SEARCH_API_KEY=        ← paste your Tavily key here (the tvly-... one)

POSTGRES_URL=postgresql://pack:YOUR_RDS_PASSWORD@YOUR_RDS_INTERNAL_ENDPOINT:5432/pack
               ← replace YOUR_RDS_PASSWORD with the password from Part 1
               ← replace YOUR_RDS_INTERNAL_ENDPOINT with the endpoint from Part 1

REDIS_URL=redis://:YOUR_TAIR_PASSWORD@YOUR_TAIR_INTERNAL_ENDPOINT:6379/0
               ← replace YOUR_TAIR_PASSWORD with the password from Part 2
               ← replace YOUR_TAIR_INTERNAL_ENDPOINT with the endpoint from Part 2

SESSION_SECRET=        ← generate one by running this command and pasting the result:
                          python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Example of what a filled-in file looks like:**
```
QWEN_API_KEY=sk-abc123def456...
SEARCH_API_KEY=tvly-xyz789...
POSTGRES_URL=postgresql://pack:MyStr0ngPass@rm-abc123.pg.rds.aliyuncs.com:5432/pack
POSTGRES_SSLMODE=require
REDIS_URL=redis://:MyRedisPwd@r-def456.redis.rds.aliyuncs.com:6379/0
SESSION_SECRET=a3f9c2d81b4e7f6a...
```

---

## Part 8 — Start the app

```bash
cd ~/the-pack/deploy
docker compose -f docker-compose.prod.yml up -d --build
```

This will:
- Build the app (takes **5–10 minutes** the first time — the Rust gateway compiles from scratch)
- Start 3 containers: the Python engine, the Rust live-stream gateway, and nginx

Watch the build with:
```bash
docker compose -f docker-compose.prod.yml logs -f
```

Press **Ctrl+C** to stop watching the logs (the app keeps running).

When it's done, check everything is running:
```bash
docker compose -f docker-compose.prod.yml ps
```

You should see 3 rows, all showing **Up** or **running**.

---

## Part 9 — Check it works

Run these checks one by one:

```bash
# Check the engine is alive
curl http://localhost/api/health
# Should print: {"status":"ok"}

# Check the live-stream gateway is alive
curl http://localhost/ws/health
# Should print: ok
```

Then open a browser and go to:
```
http://YOUR_SERVER_PUBLIC_IP
```

You should see The Pack. Start a test hunt and confirm events flow through to the canvas.

---

## Part 10 — Add HTTPS (do this before sharing with users)

HTTPS encrypts all traffic between the browser and the server. Without it, API keys and conversations travel in plain text.

You need a domain name pointing to your server's public IP first. Set an A record in your DNS provider pointing `yourdomain.com` to the server IP, then wait ~10 minutes for it to propagate.

Then on the server:

```bash
# Install Certbot
sudo apt-get install -y certbot

# Stop the web container temporarily (needs port 80 free)
cd ~/the-pack/deploy
docker compose -f docker-compose.prod.yml stop web

# Get a free SSL certificate (replace yourdomain.com with your real domain)
sudo certbot certonly --standalone -d yourdomain.com

# Restart the web container
docker compose -f docker-compose.prod.yml start web
```

Then open `deploy/nginx.conf` and replace its contents with this (swap in your domain):

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://engine:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://gateway:8080/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

Also add these two lines under the `web` service in `docker-compose.prod.yml`:
```yaml
    volumes:
      - /etc/letsencrypt:/etc/letsencrypt:ro
    ports:
      - "80:80"
      - "443:443"
```

Then rebuild the web container:
```bash
docker compose -f docker-compose.prod.yml up -d --build web
```

Now the app works at `https://yourdomain.com`.

---

## Updating the app (when there's new code)

```bash
cd ~/the-pack
git pull
cd deploy
docker compose -f docker-compose.prod.yml up -d --build
```

That's it. Docker only rebuilds what changed. The app restarts with the new code in under a minute.

---

## Viewing logs (if something goes wrong)

```bash
# See everything happening right now
cd ~/the-pack/deploy
docker compose -f docker-compose.prod.yml logs -f

# See only the AI engine logs
docker compose -f docker-compose.prod.yml logs -f engine

# See only the live-stream gateway logs
docker compose -f docker-compose.prod.yml logs -f gateway
```

Press Ctrl+C to stop watching.

---

## Troubleshooting

**The app doesn't load at all**
- Make sure your ECS security group allows port 80 inbound
- Run `docker compose -f docker-compose.prod.yml ps` — are all 3 containers Up?
- If not, run `docker compose -f docker-compose.prod.yml logs web` to see the error

**"Couldn't reach Alpha" error in the chat**
- Your `QWEN_API_KEY` is wrong or missing
- Open `deploy/.env.prod`, check the key, then restart: `docker compose -f docker-compose.prod.yml restart engine`

**Hunts don't stream live (canvas is empty)**
- Your `REDIS_URL` is wrong, or the Tair whitelist doesn't include your server's private IP
- Run `docker compose -f docker-compose.prod.yml logs gateway` — if it shows a Redis connection error, fix the URL and whitelist

**Database connection errors in the engine logs**
- Your `POSTGRES_URL` is wrong, or the RDS whitelist doesn't include your server's private IP
- Double-check the internal endpoint — it should be the VPC one, not the public one

**The build takes forever or fails on the gateway**
- The Rust compiler needs time and memory — first build is ~5 min on 8 GB RAM
- If it runs out of memory, add a swap file:
  ```bash
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  ```
  Then try the build again.

**Scouts always return empty search results**
- Your `SEARCH_API_KEY` is missing — the engine falls back to fake (canned) results
- Add the Tavily key to `.env.prod` and restart the engine container

---

## Monthly cost estimate

| What | Approx. cost (Singapore) |
|------|--------------------------|
| ECS server (4 core / 8 GB) | $60–80/month |
| RDS Postgres (1 core / 2 GB) | $25–35/month |
| Tair/Redis (1 GB) | $15–20/month |
| Public IP address | $5/month |
| Qwen AI (per hunt) | ~$0.05–$0.20 per hunt |
| Tavily search | Free (up to ~1000 searches/month) |
| **Total fixed** | **~$105–140/month** |

Qwen and Tavily only cost money when someone actually uses the app. The rest is fixed.
