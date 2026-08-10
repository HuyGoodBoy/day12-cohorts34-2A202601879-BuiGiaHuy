#!/usr/bin/env python
"""
Smoke test — runs all 8 self-test cases from DEPLOYMENT.md
against http://localhost:8000 (or URL passed as first arg).

Usage:
    python smoke_test.py                    # test http://localhost:8000
    python smoke_test.py https://my.app     # test remote URL
"""
import sys
import json
import os
import urllib.request
import urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

passed = 0
failed = 0


def request(method, path, *, headers=None, body=None, expect=None):
    """Make HTTP request and assert status code."""
    global passed, failed
    url = BASE + path
    data = None
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status = resp.status
            payload = resp.read().decode()
    except urllib.error.HTTPError as e:
        status = e.code
        payload = e.read().decode()
    label = f"{method:4} {path:30}  expect={expect}  got={status}"
    if expect is not None and status != expect:
        print(f"{RED}FAIL{RESET}  {label}")
        print(f"       body: {payload[:200]}")
        failed += 1
        return status, None
    print(f"{GREEN}PASS{RESET}  {label}")
    passed += 1
    try:
        return status, json.loads(payload)
    except Exception:
        return status, payload


def main():
    global passed, failed
    print(f"\n=== Smoke test against {BASE} ===\n")

    # Read API key from .env if available
    api_key = os.getenv("AGENT_API_KEY")
    try:
        if not api_key:
            with open(".env", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("AGENT_API_KEY="):
                        api_key = line.strip().split("=", 1)[1].strip('"').strip("'")
                        break
    except FileNotFoundError:
        pass

    if not api_key:
        print(f"{YELLOW}WARN{RESET}  No .env found — using placeholder API key 'test'")
        api_key = "test"

    # 1. Health
    request("GET", "/health", expect=200)

    # 2. Ready
    request("GET", "/ready", expect=200)

    # 3. Ask without API key → 401
    request("POST", "/ask",
            headers={"Content-Type": "application/json"},
            body={"question": "Hello"},
            expect=401)

    # 4. Ask with API key → 200 (skip if key is placeholder)
    if api_key != "test":
        _, resp = request("POST", "/ask",
                          headers={"Content-Type": "application/json",
                                   "X-API-Key": api_key},
                          body={"question": "What is deployment?"},
                          expect=200)
        if resp and "answer" in resp:
            print(f"       answer preview: {resp['answer'][:80]}...")
    else:
        print(f"{YELLOW}SKIP{RESET}  POST /ask with real key (placeholder key used)")

    # 5. Token → 200
    _, token_resp = request("POST", "/token",
                            headers={"Content-Type": "application/json"},
                            body={"username": "alice", "password": "p"},
                            expect=200)
    if token_resp and "access_token" in token_resp:
        token = token_resp["access_token"]
        # 6. Secure with JWT
        request("GET", "/secure",
                headers={"Authorization": f"Bearer {token}"},
                expect=200)

    # 7. Metrics (auth required)
    if api_key != "test":
        request("GET", "/metrics",
                headers={"X-API-Key": api_key},
                expect=200)

    # 8. Rate limit (only if real key)
    if api_key != "test":
        print("\n--- Rate limit test (15 requests) ---")
        statuses = []
        for i in range(15):
            status_code, _ = request(
                "POST", "/ask",
                headers={"Content-Type": "application/json",
                         "X-API-Key": api_key},
                body={"question": f"Test {i+1}"},
                expect=None,
            )
            statuses.append(status_code)
            print(f"       [{i+1:2}] HTTP {status_code}")
        unexpected = [code for code in statuses if code not in (200, 429)]
        if unexpected:
            print(f"{RED}FAIL{RESET}  Unexpected rate-limit statuses: {unexpected}")
            failed += 1
        elif 429 in statuses:
            print(f"{GREEN}PASS{RESET}  Rate limit produced HTTP 429")
            passed += 1
        else:
            print(f"{RED}FAIL{RESET}  Rate limit never produced HTTP 429")
            failed += 1

    print(f"\n=== Result: {passed} passed, {failed} failed ===")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
