# Deployment Information — Day 12 Lab 06

> **Student:** Bùi Gia Huy (2A202601879)
> **Verified:** 10 August 2026

## Public Service

- **URL:** <https://day12.huygoodboy.io.vn>
- **Platform:** Ubuntu 22.04 VPS (`103.77.241.150`)
- **Container registry:** `docker.io/huygoodboy/day12-agent`
- **Deployed immutable tag:** `76260bf0dd92`
- **Image digest:** `sha256:b1d08de4b69752b676640567a8a47c148e3624e241eac3665432eda0d22091bb`
- **TLS:** Let's Encrypt ECDSA certificate, valid through 8 November 2026
- **LLM mode:** supplied mock LLM; no OpenAI key is stored on the VPS

## Architecture

```text
Internet :80/:443
        |
        v
Host Nginx + Certbot
        |
        v
127.0.0.1:8000 -> FastAPI agent container
                         |
                         v
                   private Redis container
```

The FastAPI port is bound to loopback only. Redis does not publish a host port.
UFW allows inbound TCP 22, 80, and 443 and denies other inbound traffic.

## Verified Production Results

| Check | Observed result |
|---|---|
| HTTP `/health` | 301 redirect to HTTPS |
| HTTPS `/health` | 200, trusted certificate |
| HTTPS `/ready` | 200 |
| `/ask` without API key | 401 |
| `/ask` with deployed API key | 200 |
| `/token` then `/secure` | 200 |
| Authenticated `/metrics` | 200 |
| 15-request burst | nine 200 responses followed by six 429 responses |
| Agent container | healthy, running as user `agent` |
| Redis container | healthy, `PONG` |
| Certbot renewal simulation | success |
| Production readiness checker | 20/20 |

Safe public checks:

```bash
curl -i http://day12.huygoodboy.io.vn/health
curl -i https://day12.huygoodboy.io.vn/health
curl -i https://day12.huygoodboy.io.vn/ready
curl -i -X POST https://day12.huygoodboy.io.vn/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'
# The final request returns 401 because no API key is supplied.
```

Authenticated examples intentionally reference an environment variable instead
of embedding the real key:

```bash
curl -X POST https://day12.huygoodboy.io.vn/ask \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is deployment?"}'

curl https://day12.huygoodboy.io.vn/metrics \
  -H "X-API-Key: $AGENT_API_KEY"
```

## Docker Hub Release

Build and publish a new Linux AMD64 release from `06-lab-complete`:

```bash
IMAGE_TAG=$(git rev-parse --short=12 HEAD)
docker buildx build --platform linux/amd64 --load \
  -t "huygoodboy/day12-agent:$IMAGE_TAG" \
  -t huygoodboy/day12-agent:latest .
docker push "huygoodboy/day12-agent:$IMAGE_TAG"
docker push huygoodboy/day12-agent:latest
```

The VPS pins the immutable tag in `/opt/day12-agent/.env`. Updating `latest`
does not silently replace the running release.

## VPS Operations

Check the current deployment:

```bash
cd /opt/day12-agent
docker compose ps
docker compose logs --tail 100 agent
curl http://127.0.0.1:8000/health
sudo nginx -t
sudo certbot certificates
```

Deploy a new immutable tag:

```bash
cd /opt/day12-agent
sudoedit .env                 # update DAY12_IMAGE only
docker compose pull agent
docker compose up -d agent
docker compose ps
curl http://127.0.0.1:8000/health
```

Rollback by restoring the previous `DAY12_IMAGE` tag in `.env`, then run:

```bash
cd /opt/day12-agent
docker compose pull agent
docker compose up -d agent
```

## DNS and TLS

The public DNS record is:

| Type | Host | Value | TTL |
|---|---|---|---|
| A | `day12` | `103.77.241.150` | 300/Auto |

Nginx configuration is installed at
`/etc/nginx/sites-available/day12.huygoodboy.io.vn`. Certbot manages the TLS
directives and automatic HTTP-to-HTTPS redirect.

Test automatic renewal:

```bash
sudo certbot renew --dry-run --no-random-sleep-on-renew
```

## Production Environment Variables

Secrets live only in `/opt/day12-agent/.env` with mode `0600`.

| Variable | Deployed purpose |
|---|---|
| `DAY12_IMAGE` | immutable Docker Hub release tag |
| `AGENT_API_KEY` | protects `/ask` and `/metrics` |
| `JWT_SECRET` | signs demo JWTs |
| `REDIS_URL` | Compose injects `redis://redis:6379/0` |
| `RATE_LIMIT_PER_MINUTE` | 10 |
| `DAILY_BUDGET_USD` | 5.0 monthly guard value |
| `ALLOWED_ORIGINS` | `https://day12.huygoodboy.io.vn` |

The repository contains only examples and variable names, never deployed
values. The root SSH password should be rotated after deployment because it was
shared during the provisioning session.

## Reproducible Local Verification

```bash
cd 06-lab-complete
python check_production_ready.py
docker compose up --build
python smoke_test.py http://127.0.0.1:8000
```

The PNG files in `screenshots/` document the local verification run. Sanitized
production results are recorded in `screenshots/vps-deployment.txt`.
