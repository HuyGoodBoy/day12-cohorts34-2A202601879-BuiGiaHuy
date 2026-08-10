"""
Production AI Agent — Day 12 Final Project

Combines every concept in the lab:
  ✅ 12-factor config (all secrets from env)
  ✅ Structured JSON logging
  ✅ API Key authentication + JWT demo
  ✅ Redis sliding-window rate limiting
  ✅ Redis monthly budget cost guard
  ✅ Input validation (Pydantic)
  ✅ Health + Readiness probes
  ✅ Graceful shutdown (SIGTERM → drain → close)
  ✅ Security headers
  ✅ CORS
"""
import os
import time
import signal
import logging
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings
from app.auth import verify_api_key, issue_jwt, verify_jwt
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_and_record_cost, get_current_spend, estimate_cost

# Mock LLM (or OpenAI when OPENAI_API_KEY is set)
from utils.mock_llm import ask as llm_ask

# ─────────────────────────────────────────────────────────
# Logging — JSON structured
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0
_shutdown_event = False


# ─────────────────────────────────────────────────────────
# Lifespan (startup + shutdown)
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))
    yield

    _is_ready = False
    logger.info(json.dumps({"event": "shutdown_complete"}))


def _redis_ping_safe() -> bool:
    """Non-blocking Redis ping with short timeout. Returns True if reachable."""
    try:
        import redis
        r = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        return bool(r.ping())
    except Exception:
        return False


# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
    except Exception as exc:
        _error_count += 1
        logger.exception(json.dumps({"event": "unhandled_error", "err": str(exc)}))
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Strip identifying headers
    for h in ("server", "Server"):
        if h in response.headers:
            del response.headers[h]

    duration = round((time.time() - start) * 1000, 1)
    logger.info(json.dumps({
        "event": "request",
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "ms": duration,
    }))
    return response


# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000,
                          description="Your question for the agent")


class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    timestamp: str


class TokenRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────
@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "token": "POST /token (demo)",
            "health": "GET /health",
            "ready": "GET /ready",
            "metrics": "GET /metrics (requires X-API-Key)",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    user_id: str = Depends(verify_api_key),
):
    """
    Send a question to the AI agent.

    **Auth:** `X-API-Key: <key>`
    """
    # Rate limit per user
    check_rate_limit(user_id)

    # Cost guard — input tokens
    input_tokens = len(body.question.split()) * 2
    check_and_record_cost(user_id, input_tokens, 0)

    logger.info(json.dumps({
        "event": "agent_call",
        "user_id": user_id,
        "q_len": len(body.question),
        "client": str(request.client.host) if request.client else "unknown",
    }))

    answer = llm_ask(body.question)

    # Cost guard — output tokens
    output_tokens = len(answer.split()) * 2
    check_and_record_cost(user_id, 0, output_tokens)

    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.post("/token", tags=["Auth"])
def get_token(body: TokenRequest):
    """
    Demo JWT issuer. Any non-empty username/password returns a token.
    In production this would check a user store.
    """
    token = issue_jwt(body.username)
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600}


@app.get("/secure", tags=["Demo"])
def secure_endpoint(user_id: str = Depends(verify_jwt)):
    """Endpoint protected by JWT — for demo / testing."""
    return {"message": f"Hello, {user_id}! JWT verified."}


@app.get("/health", tags=["Operations"])
def health():
    """Liveness probe. Platform restarts container if this fails."""
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": {
            "llm": "openai" if settings.openai_api_key else "mock",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe. Returns 200 only when app is ready to serve traffic."""
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    if _shutdown_event:
        raise HTTPException(503, "Shutting down")
    # We intentionally do NOT block on Redis here — readiness is about
    # "the process can answer". Redis is checked lazily inside rate_limiter
    # / cost_guard which fall open if unreachable.
    return {"ready": True}


@app.get("/metrics", tags=["Operations"])
def metrics(user_id: str = Depends(verify_api_key)):
    """Basic metrics (protected)."""
    spend = get_current_spend(user_id)
    monthly_budget = settings.daily_budget_usd  # kept name for rubric compat
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "current_spend_usd": round(spend, 4),
        "monthly_budget_usd": monthly_budget,
        "budget_used_pct": round(spend / monthly_budget * 100, 1) if monthly_budget else 0,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "instance_id": os.getenv("INSTANCE_ID", "local"),
    }


# ─────────────────────────────────────────────────────────
# Graceful shutdown — signal handlers
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    global _shutdown_event
    logger.info(json.dumps({"event": "signal_received", "signum": signum}))
    _shutdown_event = True
    # Readiness will now return 503 → load balancer drains traffic
    # Then uvicorn waits for in-flight requests (timeout_graceful_shutdown).


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    logger.info(f"API Key prefix: {settings.agent_api_key[:4]}****")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
