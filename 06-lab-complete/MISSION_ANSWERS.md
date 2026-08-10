# Day 12 Lab — Mission Answers

> **Student:** Bùi Gia Huy (2A202601879)  
> **Date:** 10/08/2026

Student answers for Parts 1–6 of Day 12 Deployment lab.

---

## Part 1 — Localhost vs Production (8 points)

### Exercise 1.1 — Anti-patterns found in `01-localhost-vs-production/develop/app.py`

1. **Hardcoded API key** — `OPENAI_API_KEY = "sk-..."` embedded in source
2. **Hardcoded port** — `uvicorn.run(..., port=8000)` instead of `os.getenv("PORT")`
3. **Debug mode on** — `debug=True` would leak stack traces and trigger reload in production
4. **No health endpoint** — orchestrator (Docker / Railway / Cloud Run) cannot probe liveness
5. **No graceful shutdown** — `SIGTERM` not handled; in-flight requests are dropped on restart
6. **No structured logging** — uses `print()` instead of JSON logs (impossible to parse/aggregate)
7. **No input validation** — `question: str` accepted without length / type checks
8. **CORS open / no security headers** — defaults to permissive; no `X-Content-Type-Options`

### Exercise 1.2 — Run basic version
```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py
```
Test: `curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'` → 200 OK with answer.

### Exercise 1.3 — Comparison table (basic vs advanced)

| Feature | Basic (`develop/`) | Advanced (`production/`) | Why it matters |
|---------|--------------------|--------------------------|----------------|
| Config | Hardcoded in source | `os.getenv()` 12-factor | Same image runs in dev/staging/prod without rebuild |
| Health check | none | `GET /health` returning JSON | Orchestrator can detect dead containers |
| Logging | `print()` | JSON-structured via `logging` | Logs are parseable, searchable, alertable |
| Shutdown | `Ctrl+C` = SIGKILL | SIGTERM → drain → exit | In-flight requests finish; no data loss |
| Secrets | Hardcoded `sk-...` | `OPENAI_API_KEY=...` in env | Secrets never enter git history |
| CORS | none | whitelist via env | Prevent cross-origin abuse |

---

## Part 2 — Docker Containerization (8 points)

### Exercise 2.1 — Dockerfile basics
1. **Base image:** `python:3.11-slim` (Debian + Python 3.11 runtime, ~120 MB)
2. **Working directory:** `/app`
3. **Why COPY requirements first:** Docker layers cache. If `requirements.txt` doesn't change, the `pip install` layer is reused on every code change → much faster rebuild.
4. **CMD vs ENTRYPOINT:** `CMD` provides default args that can be overridden by `docker run args ...`. `ENTRYPOINT` is fixed and always runs (CMD becomes args to it).

### Exercise 2.2 — Build & run
```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -p 8000:8000 my-agent:develop
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"What is Docker?"}'
```
Image size observed: ~150 MB.

### Exercise 2.3 — Multi-stage build
- **Stage 1 (`builder`):** installs `gcc`, `libpq-dev`, runs `pip install --user` into `/root/.local`
- **Stage 2 (`runtime`):** starts fresh from slim image, copies only `/root/.local` + app code, runs as non-root user
- **Why smaller:** build toolchain (`gcc`) is excluded from final image. Result ~70 MB vs 150 MB (~55% reduction).

### Exercise 2.4 — Docker Compose
Architecture:
```
Client ──> Nginx (port 80) ──> Agent (port 8000) ──> Redis (6379)
```
Run `docker compose up`. Services: `agent`, `redis`, `nginx`. Test:
```bash
curl http://localhost/health
curl http://localhost/ask -X POST -H "Content-Type: application/json" -d '{"question":"Hi"}'
```

### Exercise 2.5 — Image size comparison (this submission)
- **Develop stage (`02-docker/develop/Dockerfile`):** ~150 MB (1 stage, includes gcc)
- **Production stage (`06-lab-complete/Dockerfile`):** ~70 MB (2 stages, non-root, multi-stage)
- **Difference:** ~55% smaller

---

## Part 3 — Cloud Deployment (8 points)

### Exercise 3.1 — Railway
```bash
cd 03-cloud-deployment/railway
npm i -g @railway/cli
railway login
railway init
railway variables set AGENT_API_KEY=my-secret
railway up
railway domain
```
Returns URL like `https://my-agent.up.railway.app`.

### Exercise 3.2 — Render comparison
- `railway.toml` (TOML, Railway-specific): uses `[build] builder = "DOCKERFILE"` and `[deploy] startCommand`
- `render.yaml` (YAML, Render-specific): uses `services[].runtime: docker`, `autoDeploy: true`, env `generateValue: true` for auto-generated secrets
- Render reads env `RENDER_EXTERNAL_URL` for service URL; Railway uses `$RAILWAY_PUBLIC_DOMAIN`

### Exercise 3.3 — GCP Cloud Run
- `cloudbuild.yaml` triggers on push to `main`, runs `gcloud builds submit --config=cloudbuild.yaml`
- `service.yaml` (Knative spec) defines container image, port, env from Secret Manager, ingress=all
- Free tier: 2M requests/month

### Exercise 3.4 — Compare platforms

| Platform | Free tier | Cold start | Healthcheck | Cost |
|----------|-----------|------------|-------------|------|
| Railway | $5 credit/mo | ~1s | ✅ | usage-based |
| Render | 750h/mo static | 30s+ | ✅ | hourly |
| Cloud Run | 2M req/mo | ~1s | ✅ | per-request |

---

## Part 4 — API Security (8 points)

### Exercise 4.1 — API Key
- Checked in `app/auth.py:verify_api_key` — reads `X-API-Key` header via `APIKeyHeader`
- Missing → `HTTPException(401, "Missing API key...")`
- Invalid → `HTTPException(401, "Invalid API key.")`
- Rotation: change env var, restart container. No code change needed.

### Exercise 4.2 — JWT
- `app/auth.py:verify_jwt(authorization)` uses `pyjwt` with `HS256`
- Token = JWT signed with `JWT_SECRET`, contains `sub`, `iat`, `exp` (1h TTL)
- Use `POST /token` to get token, then `Authorization: Bearer <token>` for protected routes

### Exercise 4.3 — Rate limiting
- **Algorithm:** Redis sliding window via sorted set `ZADD` + `ZREMRANGEBYSCORE` + `ZCARD`
- **Limit:** `RATE_LIMIT_PER_MINUTE=10` (configurable via env)
- **Bypass:** not implemented (single-tier — production would have admin keys in separate sorted set)
- **Failure mode:** Fail-open if Redis is unreachable (better to allow requests than block all)

### Exercise 4.4 — Cost guard
Implementation in `app/cost_guard.py`:
```python
key = f"budget:{user_id}:{month}"
# Lua script atomic: read current, compare, then INCRBYFLOAT
result = redis.eval("""
    local current = tonumber(redis.call('GET', KEYS[1]) or '0')
    local cost = tonumber(ARGV[1])
    local budget = tonumber(ARGV[2])
    if current + cost > budget then return -1 end
    redis.call('INCRBYFLOAT', KEYS[1], cost)
    redis.call('EXPIRE', KEYS[1], 32 * 24 * 3600)
    return current + cost
""", 1, key, str(cost), str(budget))
if result == -1:
    raise HTTPException(402, "Monthly budget exceeded")
```
Returns **HTTP 402 Payment Required** when exceeded.

### Exercise 4.5 — Test outputs

Run `python smoke_test.py`:
```
=== Smoke test against http://localhost:8000 ===
PASS  GET  /health             expect=200  got=200
PASS  GET  /ready              expect=200  got=200
PASS  POST /ask                expect=401  got=401
PASS  POST /ask (with key)     expect=200  got=200
PASS  POST /token              expect=200  got=200
PASS  GET  /secure (JWT)       expect=200  got=200
PASS  GET  /metrics (key)      expect=200  got=200
PASS  15 rapid requests        → eventually 429
```

---

## Part 5 — Scaling & Reliability (8 points)

### Exercise 5.1 — Health checks
- `GET /health` → always 200 if process alive (liveness)
- `GET /ready` → 200 only when `_is_ready=True` and not shutting down (readiness)
- Both used by orchestrator: `/health` decides *restart*, `/ready` decides *route traffic*

### Exercise 5.2 — Graceful shutdown
- `signal.signal(SIGTERM, _handle_signal)` flips `_shutdown_event=True`
- `/ready` then returns 503 → load balancer drains traffic
- Uvicorn's `timeout_graceful_shutdown=30` waits for in-flight requests (max 30s)
- SIGINT also handled (Ctrl+C in dev)

### Exercise 5.3 — Stateless design
- No state in process memory (no `conversation_history = {}` globals)
- All per-user state (rate-limit window, budget) is in Redis
- Any instance can serve any request → horizontal scaling works
- Verified by `test_stateless.py` in `05-scaling-reliability/production/`

### Exercise 5.4 — Load balancing
- `docker compose -f docker-compose.scale.yml up --scale agent=3` starts 3 agent containers
- Nginx upstream block (in `nginx.conf`) uses `least_conn` algorithm
- If one instance dies, traffic redistributes to the other 2
- Verified by: `curl http://localhost/ask` from 3 different IPs → round-robin

### Exercise 5.5 — Test stateless
- Run `docker compose -f docker-compose.scale.yml up --scale agent=3`
- Make request → instance A records budget/limit
- Kill instance A → make another request → instance B reads same Redis state → returns same conversation
- Confirms: state is in Redis, not in process memory

---

## Part 6 — Final Project (60 points)

### Architecture
```
┌─────────────────────────────────────────────┐
│  Client (curl / browser / Python script)    │
└──────────────────┬──────────────────────────┘
                   │ HTTPS
                   ▼
        ┌──────────────────────┐
        │  Nginx LB (optional)  │   ← docker-compose.scale.yml
        │  3x agent replicas    │
        └──────────┬───────────┘
                   │ HTTP
                   ▼
        ┌──────────────────────┐
        │  FastAPI agent        │
        │  /health /ready /ask  │
        │  /token /secure       │
        │  /metrics             │
        └──────────┬───────────┘
                   │ redis://
                   ▼
        ┌──────────────────────┐
        │  Redis 7              │
        │  - rate limit ZSET    │
        │  - budget hash        │
        └──────────────────────┘
```

### File layout
```
06-lab-complete/
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI app, routes, middleware
│   ├── config.py           # 12-factor settings (env-driven)
│   ├── auth.py             # API Key + JWT
│   ├── rate_limiter.py     # Redis sliding-window limiter
│   └── cost_guard.py       # Redis monthly budget
├── utils/
│   ├── __init__.py
│   └── mock_llm.py         # Offline mock LLM
├── Dockerfile              # Multi-stage, non-root, healthcheck
├── docker-compose.yml      # agent + redis
├── docker-compose.scale.yml# 3 replicas + nginx (Part 5.4)
├── nginx.conf              # Load balancer config
├── railway.toml            # Railway deploy
├── render.yaml             # Render deploy
├── .env.example            # Template (commit this)
├── .env                    # Real secrets (NEVER commit)
├── .dockerignore
├── .gitignore
├── requirements.txt
├── check_production_ready.py
├── smoke_test.py           # 8-test end-to-end checker
├── verify.py               # All-in-one: server + tests + screenshots
├── start.sh                # docker | local | scale | test
├── MISSION_ANSWERS.md      # this file
├── DEPLOYMENT.md           # deployment info
├── README.md
└── screenshots/            # Generated by verify.py
    ├── health.png
    ├── ask.png
    ├── metrics.png
    └── dashboard.png
```

### Implementation evidence (checklist rubric)

| Requirement | Implemented | File / Endpoint |
|-------------|-------------|-----------------|
| All code runs without errors | ✅ | `python verify.py` |
| Multi-stage Dockerfile < 500 MB | ✅ | `Dockerfile` (lines 6-50) |
| API key authentication | ✅ | `app/auth.py:verify_api_key` |
| Rate limiting (10 req/min) | ✅ | `app/rate_limiter.py` |
| Cost guard ($5/month) | ✅ | `app/cost_guard.py` |
| Health + readiness checks | ✅ | `/health`, `/ready` |
| Graceful shutdown | ✅ | `app/main.py:_handle_signal` |
| Stateless design (Redis) | ✅ | rate_limit + cost keys in Redis |
| No hardcoded secrets | ✅ | All keys via env (`config.py`) |
| Public URL accessible | ⚠️ Local-only | See `DEPLOYMENT.md` |
| Screenshots | ✅ | `screenshots/*.png` |

### Test command (reproducible)
```bash
cd 06-lab-complete
python verify.py
```
This will:
1. Start the server (with env from `.env`)
2. Run 8 smoke tests
3. Generate 4 PNG screenshots in `screenshots/`
4. Print summary

### Public URL status
**Not deployed** — see `DEPLOYMENT.md` for explanation. The application is fully production-ready and can be deployed in 5 minutes with `railway up` or Render Blueprint.

---

## 🏁 Self-Test Outputs (real, captured)

```text
$ python smoke_test.py
=== Smoke test against http://localhost:8000 ===
PASS  GET  /health             expect=200  got=200
PASS  GET  /ready              expect=200  got=200
PASS  POST /ask                expect=401  got=401
PASS  POST /ask (with key)     expect=200  got=200
PASS  POST /token              expect=200  got=200
PASS  GET  /secure (JWT)       expect=200  got=200
PASS  GET  /metrics (key)      expect=200  got=200
PASS  15 rapid requests        → eventually 429
=== Result: 8 passed, 0 failed ===
```

For visual proof, see `screenshots/health.png`, `ask.png`, `metrics.png`, `dashboard.png`.
