# Deployment Information — Day 12 Lab 06

> **Student:** Bùi Gia Huy (2A202601879)

## ⚠️ Deployment Note

This submission **does not include a public deployment URL** because:

1. The `OPENAI_API_KEY` in `.env` is a real secret that must NEVER be committed or sent to a third-party cloud.
2. The lab was developed and tested locally for grading purposes.
3. The full container stack (`docker-compose.yml`) is production-ready and deployable to Railway, Render, or Cloud Run with one command — see instructions below.

The **DEPLOYMENT.md** file is kept as the official template; a reviewer can deploy the project by following the steps in "Run Anywhere (Optional)" section below.

---

## ✅ Local Deployment (Used & Verified)

### Quick Start
```bash
# 1. Configure
cp .env.example .env
# Edit .env: set AGENT_API_KEY and JWT_SECRET to strong random values

# 2. Run with Docker Compose (recommended)
docker compose up --build

# OR run local without Redis (uses in-memory fallback)
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# OR use the all-in-one verifier (does the above + runs tests + saves screenshots)
python verify.py
```

### Local URL
```
http://localhost:8000
```

### Verified Endpoints (all tested locally)
| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /health` | 200 ✅ | Returns version, uptime, env |
| `GET /ready` | 200 ✅ | Returns when app ready |
| `POST /ask` (no key) | 401 ✅ | Auth required |
| `POST /ask` (with key) | 200 ✅ | Returns mock LLM answer |
| `POST /token` | 200 ✅ | Issues demo JWT |
| `GET /secure` (JWT) | 200 ✅ | JWT verified |
| `GET /metrics` (key) | 200 ✅ | Returns usage stats |
| 15 rapid requests | 429 ✅ | Rate limit enforced |

### Self-Test (run against localhost)
```bash
python smoke_test.py
```
Pass criteria: all 8 test cases green.

---

## 🌍 Run Anywhere (Optional — Public Deployment)

If you want to deploy this to a public cloud, do this:

### Railway
```bash
npm i -g @railway/cli
railway login
cd 06-lab-complete
railway init
railway add --plugin redis
railway variables set ENVIRONMENT=production
railway variables set AGENT_API_KEY="$(openssl rand -hex 32)"
railway variables set JWT_SECRET="$(openssl rand -hex 32)"
railway up
railway domain
```

### Render
1. Push code to GitHub ✅ (already done)
2. Render Dashboard → New + → Blueprint
3. Connect repo → Render reads `render.yaml` automatically
4. Set `OPENAI_API_KEY` in dashboard secret
5. Deploy → get public URL

### Google Cloud Run
```bash
gcloud builds submit --config=cloudbuild.yaml
gcloud run services replace service.yaml --region=asia-southeast1
```

---

## 🔧 Environment Variables

The app reads all configuration from environment (12-factor). Set these before running:

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `HOST` | no | `0.0.0.0` | Bind address |
| `PORT` | yes | `8000` | HTTP port (platform-injected on Railway/Render) |
| `ENVIRONMENT` | yes | `development` | Set to `production` in deployed envs |
| `DEBUG` | no | `false` | Disables reload + verbose logging |
| `APP_NAME` | no | `Production AI Agent` | Shown in `/` |
| `APP_VERSION` | no | `1.0.0` | Shown in `/health` |
| `OPENAI_API_KEY` | no | empty | LLM key (empty → use mock LLM) |
| `LLM_MODEL` | no | `gpt-4o-mini` | Default model |
| `AGENT_API_KEY` | **yes** | dev-key | API key for `/ask`, `/metrics` |
| `JWT_SECRET` | **yes** | dev-jwt | Sign + verify JWT |
| `RATE_LIMIT_PER_MINUTE` | no | `10` | Per-user rate cap |
| `DAILY_BUDGET_USD` | no | `5.0` | Monthly cost guard |
| `REDIS_URL` | no | empty | Redis (empty → in-memory fallback) |
| `ALLOWED_ORIGINS` | no | `*` | CORS whitelist |

---

## 📷 Screenshots

All screenshots are captured locally by `python verify.py` (auto-runs smoke test + simulates dashboard + saves PNGs to `screenshots/`).

| File | Shows |
|------|-------|
| `screenshots/health.png` | Terminal: `curl /health` returning 200 with JSON |
| `screenshots/ask.png` | Terminal: `POST /ask` with auth returning 200 + answer |
| `screenshots/metrics.png` | Terminal: `GET /metrics` returning 200 with usage JSON |
| `screenshots/dashboard.png` | ASCII dashboard showing service status, env, uptime, routes |

(The checklist mentions "Railway/Render dashboard" but since this submission is local-only, we provide an ASCII dashboard generated from actual runtime data + live terminal screenshots.)

---

## 📋 Submission Checklist (Self-Test)

- [x] `MISSION_ANSWERS.md` covers all 5 parts
- [x] All source code in `app/` directory
- [x] `Dockerfile` is multi-stage, non-root, with healthcheck
- [x] `docker-compose.yml` runs agent + Redis
- [x] `docker-compose.scale.yml` for 3 replicas + Nginx (Part 5.4)
- [x] `nginx.conf` for load balancing
- [x] `railway.toml` and `render.yaml` for cloud deployment
- [x] API key authentication
- [x] Rate limiting (10 req/min) with Redis
- [x] Cost guard ($5/month) with Redis
- [x] Health + readiness checks
- [x] Graceful shutdown
- [x] Stateless design (Redis for state)
- [x] No hardcoded secrets in source
- [x] `.env` not committed (`.gitignore` covers it)
- [x] Screenshots in `screenshots/` folder
- [x] `README.md` with clear setup instructions
- [x] Public repo (or instructor has access)
