# Pack — Go-Live Setup (Tobi's checklist)

Everything you need to do so we can run the whole system on **real production infrastructure**
(Alibaba Cloud) with the **real Qwen key**, then test it end to end. Do these in order, fill in
the **values block** at the bottom, and hand it back to me. I'll take it from there.

> **Region:** do everything in **Alibaba Cloud International → Singapore (`ap-southeast-1`)** so
> the model, database, and cache share a region.
> **Secrets:** don't commit anything. Just paste the values to me in chat — I write them into
> `backend/.env`, which is gitignored.
> **Search key:** skipped (Scouts reason from Qwen's own knowledge for now).

---

## 0. Account (once)
- [ ] Sign in / create an **Alibaba Cloud International** account: <https://account.alibabacloud.com>
- [ ] Complete identity verification and attach a payment method (Model Studio, RDS, and Tair
      all need an active billing account).
- [ ] Set the console region to **Singapore**.

---

## 1. Qwen API key (Model Studio / DashScope)
- [ ] Open **Model Studio** (a.k.a. Bailian): <https://bailian.console.alibabacloud.com>
- [ ] Activate it / accept terms (Singapore region).
- [ ] Left nav → **API-KEY** → **Create API Key** → copy the value (starts with `sk-...`).
- [ ] (If visible) note the exact model ids for our three tiers — usually `qwen-max`,
      `qwen-plus`, `qwen-flash` (or `qwen-turbo`). If you can't find them, leave it — I'll
      discover and confirm them with a smoke test.

→ **Give me:** `QWEN_API_KEY` (+ model ids if you saw them).

---

## 2. Postgres — ApsaraDB RDS for PostgreSQL
- [ ] **RDS console** → **Create Instance**: engine **PostgreSQL 16**, region **Singapore**,
      smallest spec is fine, a few GB SSD, pay-as-you-go.
- [ ] Wait for it to become **Running**.
- [ ] **Accounts** → create a privileged account: username `pack`, set a password.
- [ ] **Databases** → create a database named `pack`.
- [ ] **Whitelist / Data Security** → add this IP (the machine that runs the engine):

      143.105.174.157

- [ ] **Connection** → copy the **endpoint host** and **port** (5432). Note whether **SSL is
      enforced** (recommended ON for prod).

→ **Give me:** `POSTGRES_URL = postgresql://pack:YOURPASSWORD@HOST:5432/pack` and **"SSL on/off"**.

---

## 3. Redis — Tair (Redis-compatible)
- [ ] **Tair console** → **Create Instance**: Redis-compatible, region **Singapore**, smallest spec.
- [ ] Set a **password** (auth).
- [ ] **Whitelist** → add the same IP:

      143.105.174.157

- [ ] **Connection** → copy the **endpoint host** and **port** (6379). If you turn on TLS, note it.

→ **Give me:** `REDIS_URL = redis://:YOURPASSWORD@HOST:6379/0` (use `rediss://...` if TLS is on).

---

## 4. (Optional, later — NOT needed for the test)
- OSS bucket for artifacts/uploads — only the `/uploads` feature needs it. Skip for now.
- Search provider (Tavily/Serper) — skipped per your call; Scouts run on Qwen knowledge.

---

## Values block — fill this in and send it to me

```
QWEN_API_KEY      = sk-...
QWEN_MODEL_MAX    = (e.g. qwen-max ; leave blank if unsure)
QWEN_MODEL_PLUS   = (e.g. qwen-plus ; leave blank if unsure)
QWEN_MODEL_FLASH  = (e.g. qwen-flash ; leave blank if unsure)

POSTGRES_URL      = postgresql://pack:PASSWORD@HOST:5432/pack
POSTGRES_SSL      = on | off

REDIS_URL         = redis://:PASSWORD@HOST:6379/0
```

- [ ] IP `143.105.174.157` whitelisted on **both** RDS and Tair.

---

## What I do the moment you send these back
1. Write `backend/.env` (gitignored) and point the gateway at `REDIS_URL`.
2. `python scripts/hello_qwen.py` — confirm auth, the real model names per tier, token
   accounting, and the thinking-needs-streaming behaviour (tells us if `qwen-plus` supports
   thinking for the Tracker; I'll adjust that wolf if not).
3. `pytest` — the 3 currently-skipped DB/outbox tests now run against your real Postgres + Tair.
4. Bring up **engine + gateway + frontend** and run a **full live hunt on the canvas**:
   Door → approve plan → real wolves work (Boundary meter moving on real cost) → answer the
   Hold → final artifact. Plus resilience checks (stop, forced boundary halt, gateway reconnect).

---

## Fastest fallback if cloud provisioning stalls
If RDS/Tair take too long and you just want to see it run today, install **Docker Desktop**
(<https://www.docker.com/products/docker-desktop/>), start it, and tell me — I'll
`docker compose up -d redis postgres` locally and we test with the real Qwen key against local
Postgres/Redis. (Cloud is still the prod target; this is only a shortcut.)
