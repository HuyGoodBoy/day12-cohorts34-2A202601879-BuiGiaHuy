# Day 12 Lab — Mission Answers

> Student answers for Parts 1–5 of Day 12 Deployment lab.
> All answers derived from running the example code in each section.

---

## Part 1 — Localhost vs Production (8 points)

### Exercise 1.1 — Anti-patterns found in `01-localhost-vs-production/develop/app.py`

1. **Hardcoded API key** — OpenAI key embedded in source (line ~`OPENAI_API_KEY = "sk-..."`)
2. **Hardcoded port** — `uvicorn.run(..., port=8000)` instead of `os.getenv("PORT")`
3. **Debug mode on** — `debug=True` would leak stack traces and reload code in production
4. **No health endpoint** — orchestrator (Docker/Railway/Cloud Run) cannot probe liveness
5. **No graceful shutdown** — `signal.SIGTERM` not handled; in-flight requests are dropped on restart
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
| Health check | � none | `GET /health` returning JSON | Orchestrator can detect dead containers |
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

---

## Part 4 — API Security (8 points)

### Exercise 4.1 — API Key
- Checked in `04-api-gateway/develop/app.py` line ~35: `API_KEY = os.getenv("AGENT_API_KEY")`
- Missing → `HTTPException(401)`
- Rotation: change env var, restart container. No code change needed.

### Exercise 4.2 — JWT
- `auth.py` implements `verify_jwt(authorization: Bearer ...)` using `pyjwt`
- Token = JWT HS256 signed with `JWT_SECRET`, contains `sub`, `iat`, `exp` (1h TTL)
- Use `POST /token` to get token, then `Authorization: Bearer <token>` for protected routes

### Exercise 4.3 — Rate limiting
- **Algorithm:** Redis sliding window via sorted set `ZADD` + `ZREMRANGEBYSCORE` + `ZCARD`
- **Limit:** `RATE_LIMIT_PER_MINUTE=10` (configurable via env)
- **Bypass:** not implemented (single-tier — production would have admin keys in separate sorted set)

### Exercise 4.4 — Cost guard
Implementation in `app/cost_guard.py`:
```python
key = f"budget:{user_id}:{month}"
total = float(redis.get(key) or 0)
if total + cost > DAILY_BUDGET_USD:
    raise HTTPException(402, "Monthly budget exceeded")
redis.incrbyfloat(key, cost)
redis.expire(key, 32 * 24 * 3600)  # auto-cleanup next month
```
Returns **HTTP 402 Payment Required** when exceeded.

---

## Part 5 — Scaling & Reliability (8 points)

### Exercise 5.1 — Health checks
- `GET /health` → always 200 if process alive (liveness)
- `GET /ready` → 200 only when `_is_ready=True` and not shutting down (readiness)

### Exercise 5.2 — Graceful shutdown
- `signal.signal(SIGTERM, _handle_signal)` flips `_shutdown_event=True`
- `/ready` then returns 503 → load balancer drains traffic
- Uvicorn's `timeout_graceful_shutdown=30` waits for in-flight requests

### Exercise 5.3 — Stateless design
- No state in process memory (no `conversation_history = {}` globals)
- All per-user state (rate-limit window, budget) is in Redis
- Any instance can serve any request → horizontal scaling works

### Exercise 5.4 — Load balancing
- `docker compose up --scale agent=3` starts 3 agent containers
- Nginx upstream block round-robins requests
- If one dies, traffic redistributes to the other 2

### Exercise 5.5 — Test stateless
- Run `python test_stateless.py` (in `05-scaling-reliability/production/`)
- Script: makes request → kills instance → makes another request → conversation preserved (Redis)

---

## Part 6 — Final Project (60 points)

See `README.md` and `DEPLOYMENT.md` in this folder for:
- Source structure
- API endpoint reference
- Deployment instructions
- Public URL (after deploying)
