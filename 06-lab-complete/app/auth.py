"""
Authentication & Authorization
────────────────────────────────
- API Key (X-API-Key header) — primary
- JWT (Authorization: Bearer <token>) — secondary, demo
- All secrets sourced from env (12-factor)
"""
from __future__ import annotations

import time
import jwt
from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings


# ─────────────────────────────────────────────────────────
# API Key
# ─────────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """
    Verify X-API-Key header.

    Returns:
        user_id str (first 8 chars of api_key) — used as bucket key
        for rate limiting / cost tracking.

    Raises:
        401 if missing or invalid.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include header: X-API-Key: <key>",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
    return api_key[:8]


# ─────────────────────────────────────────────────────────
# JWT (demo — dùng khi muốn per-user token)
# ─────────────────────────────────────────────────────────
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 60 * 60  # 1 hour


def issue_jwt(user_id: str) -> str:
    """Mint a JWT for the given user_id (demo)."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + JWT_TTL_SECONDS,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def verify_jwt(authorization: str | None = Header(default=None)) -> str:
    """
    Verify Bearer token from Authorization header.

    Returns:
        user_id (sub claim)

    Raises:
        401 if missing / malformed / expired / bad signature.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token. Include header: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing sub claim")
    return user_id
