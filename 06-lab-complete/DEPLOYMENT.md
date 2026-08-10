# Deployment Information — Day 12 Lab 06

## Public URL
> _Fill in after first deploy: e.g. `https://my-agent.up.railway.app`_

## Platform
Railway / Render / Cloud Run

---

## Test Commands (copy-paste ready)

Replace `<PUBLIC_URL>` and `<YOUR_API_KEY>` below.

### 1. Health check
```bash
curl <PUBLIC_URL>/health
```
Expected:
```json
{"status":"ok","version":"1.0.0","environment":"production","uptime_seconds":...}
```

### 2. Readiness check
```bash
curl <PUBLIC_URL>/ready
```
Expected: `{"ready":true}`

### 3. Auth — should fail
```bash
curl -X POST <PUBLIC_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
```
Expected: `401 Unauthorized` — `{"detail":"Missing API key..."}`

### 4. Auth — should succeed
```bash
curl -X POST <PUBLIC_URL>/ask \
  -H "X-API-Key: <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is deployment?"}'
```
Expected: `200 OK` with `{"question":"...","answer":"...","model":"gpt-4o-mini","timestamp":"..."}`

### 5. Get a JWT token (demo)
```bash
curl -X POST <PUBLIC_URL>/token \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"p"}'
```
Returns: `{"access_token":"eyJ...","token_type":"bearer","expires_in":3600}`

### 6. Use the JWT
```bash
TOKEN="<paste from step 5>"
curl <PUBLIC_URL>/secure -H "Authorization: Bearer $TOKEN"
```
Expected: `{"message":"Hello, alice! JWT verified."}`

### 7. Rate limiting (should eventually return 429)
```bash
for i in {1..15}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST <PUBLIC_URL>/ask \
    -H "X-API-Key: <YOUR_API_KEY>" \
    -H "Content-Type: application/json" \
    -d "{\"question\":\"Test $i\"}"
done
```
Expected: first 10 → `200`, then `429`.

### 8. Metrics (auth required)
```bash
curl <PUBLIC_URL>/metrics -H "X-API-Key: <YOUR_API_KEY>"
```
Returns: uptime, request count, spend, budget usage, rate limit, instance ID.

---

## Environment Variables Set on Platform

| Variable | Source | Purpose |
|----------|--------|---------|
| `HOST` | auto (0.0.0.0) | bind address |
| `PORT` | platform-injected | web server port |
| `ENVIRONMENT` | `production` | triggers config validation |
| `DEBUG` | `false` | disable reload & verbose logging |
| `APP_NAME` | `Production AI Agent` | shown in `/` |
| `APP_VERSION` | `1.0.0` | shown in `/health` |
| `OPENAI_API_KEY` | platform secret | LLM API key (empty → mock) |
| `LLM_MODEL` | `gpt-4o-mini` | default model |
| `AGENT_API_KEY` | platform secret | primary auth |
| `JWT_SECRET` | platform secret | JWT signing key |
| `RATE_LIMIT_PER_MINUTE` | `10` | per-user rate cap |
| `DAILY_BUDGET_USD` | `5.0` | cost guard cap |
| `REDIS_URL` | platform Redis plugin | e.g. `redis://default:***@containers-us-west-xxx.railway.app:6379` |
| `ALLOWED_ORIGINS` | `*` | CORS (tighten in real prod) |

---

## Deployment Steps (Railway example)

```bash
# 1. Install CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Init + link project
cd 06-lab-complete
railway init

# 4. Add Redis plugin
railway add --plugin redis

# 5. Set env (the platform injects REDIS_URL automatically)
railway variables set ENVIRONMENT=production
railway variables set AGENT_API_KEY="<paste-strong-64-char-key>"
railway variables set JWT_SECRET="<paste-different-strong-64-char-key>"

# 6. Deploy
railway up

# 7. Get URL
railway domain
```

---

## Self-Test Checklist (run after deploy)

- [ ] `curl <URL>/health` → 200
- [ ] `curl <URL>/ready` → 200
- [ ] `curl <URL>/ask` (no key) → 401
- [ ] `curl <URL>/ask` (with key) → 200, JSON answer
- [ ] 15 rapid requests → eventually 429
- [ ] `curl <URL>/metrics` (with key) → 200, shows your bucket
- [ ] `curl <URL>/token` → 200, returns JWT
- [ ] `curl <URL>/secure` (with JWT) → 200

---

## Screenshots

Place the following in `screenshots/`:
- `dashboard.png` — Railway/Render service dashboard showing "Running"
- `health.png` — terminal showing `curl /health` returning 200
- `ask.png` — terminal showing successful `POST /ask` with answer
- `metrics.png` — terminal showing `/metrics` JSON output

These are **mandatory** for submission per `DAY12_DELIVERY_CHECKLIST.md`.
