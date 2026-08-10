# Lab 12 — Complete Production Agent

Production-ready AI agent combining **every concept** from the Day 12 lab.

## ✅ Production Readiness: **20/20 checks passed**

```
$ python check_production_ready.py
📁 Required Files       6/6 ✅
🔒 Security             2/2 ✅
🌐 API Endpoints        6/6 ✅
🐳 Docker               6/6 ✅
Result: 20/20 (100%) — PRODUCTION READY!
```

---

## Cấu Trúc Project

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
├── railway.toml            # Railway deploy
├── render.yaml             # Render deploy
├── .env.example            # Template (commit this)
├── .env                    # Real secrets (NEVER commit)
├── .dockerignore
├── .gitignore
├── requirements.txt
├── check_production_ready.py
├── MISSION_ANSWERS.md      # Part 1–5 answers
├── DEPLOYMENT.md           # Deploy instructions + test commands
└── README.md
```

---

## Chạy Local

### Bước 1 — Cấu hình
```bash
cp .env.example .env
# Sửa .env: thay AGENT_API_KEY, JWT_SECRET bằng giá trị mạnh (>= 32 ký tự random)
```

### Bước 2 — Chạy với Docker Compose (khuyến nghị)
```bash
docker compose up --build
```
Mở browser: <http://localhost:8000>

### Hoặc chạy local không cần Redis
```bash
pip install -r requirements.txt
python -m app.main
```

### Hoặc với uvicorn trực tiếp
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## API Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/` | none | Service info |
| POST | `/ask` | `X-API-Key` | Ask the agent a question |
| POST | `/token` | none | Issue demo JWT |
| GET | `/secure` | `Authorization: Bearer` | JWT-protected demo |
| GET | `/health` | none | Liveness probe |
| GET | `/ready` | none | Readiness probe |
| GET | `/metrics` | `X-API-Key` | Prometheus-style metrics |
| GET | `/docs` | none (dev only) | Swagger UI |

---

## Test nhanh

```bash
API_KEY=$(grep ^AGENT_API_KEY .env | cut -d= -f2)

# Health
curl http://localhost:8000/health

# Ask (with API key)
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is deployment?"}'

# Token (demo)
TOKEN=$(curl -s -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"p"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Secure endpoint with JWT
curl http://localhost:8000/secure -H "Authorization: Bearer $TOKEN"
```

---

## Deploy Railway

```bash
npm i -g @railway/cli
railway login
railway init
railway add --plugin redis   # thêm Redis service
railway variables set ENVIRONMENT=production
railway variables set AGENT_API_KEY="$(openssl rand -hex 32)"
railway variables set JWT_SECRET="$(openssl rand -hex 32)"
railway up
railway domain    # lấy public URL
```

Chi tiết xem `DEPLOYMENT.md`.

---

## Deploy Render

1. Push repo lên GitHub
2. Render Dashboard → New + → Blueprint
3. Connect repo → Render tự đọc `render.yaml`
4. Set secrets: `AGENT_API_KEY`, `JWT_SECRET` (Render generate tự động)
5. Add Redis service (Render Marketplace)
6. Deploy → nhận URL

---

## Bảo mật (đọc k� trước khi deploy)

> ⚠️ **Tuyệt đối không commit file `.env`**

- `.env` chứa `OPENAI_API_KEY`, `AGENT_API_KEY`, `JWT_SECRET`
- Nếu lỡ commit → **rotate ngay** tất cả secret
- File `.env.example` không có giá trị thật → an toàn để commit

Kiểm tra:
```bash
git status
# .env KHÔNG được xuất hiện trong "Changes to be committed"
```

---

## Test Production Readiness

```bash
python check_production_ready.py
```

Output mẫu:
```
=======================================================
  Production Readiness Check — Day 12 Lab
=======================================================
📁 Required Files           6/6 ✅
🔒 Security                 2/2 ✅
🌐 API Endpoints (code)     6/6 ✅
🐳 Docker                   6/6 ✅
=======================================================
Result: 20/20 (100%) — PRODUCTION READY!
=======================================================
```

---

## Submission (theo DAY12_DELIVERY_CHECKLIST.md)

Trước khi nộp, đảm bảo:
- [x] `MISSION_ANSWERS.md` đã hoàn thành
- [x] `DEPLOYMENT.md` đã điền public URL sau khi deploy
- [x] `screenshots/` có `dashboard.png`, `health.png`, `ask.png`, `metrics.png`
- [x] Repo public (hoặc đã share với giảng viên)
- [x] Không có `.env` trong git history

---

## License

Educational use — VinUniversity AICB-P1 2026.
