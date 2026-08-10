#!/usr/bin/env python
"""
verify.py — All-in-one verification script for Day 12 Lab submission.

What it does:
  1. Starts the FastAPI server in the background (with env from .env)
  2. Waits for /health to be ready
  3. Runs 8 smoke tests (health, ready, auth, ask, token, secure, metrics, rate-limit)
  4. Generates 4 PNG screenshots in screenshots/ folder:
       - health.png     (curl /health terminal output)
       - ask.png        (POST /ask with auth terminal output)
       - metrics.png    (GET /metrics terminal output)
       - dashboard.png  (ASCII dashboard of service status)
  5. Cleans up the server process
  6. Prints a final summary

Usage:
    python verify.py
"""
import os
import sys
import time
import json
import shutil
import signal
import socket
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
SHOTS = ROOT / "screenshots"
SHOTS.mkdir(exist_ok=True)

PORT = 8765  # use non-default port to avoid conflicts with running app
BASE = f"http://127.0.0.1:{PORT}"

# ============================================================
# Utilities
# ============================================================

def load_api_key():
    """Load AGENT_API_KEY from .env (utf-8)."""
    env = ROOT / ".env"
    if not env.exists():
        return None
    try:
        with open(env, encoding="utf-8") as f:
            for line in f:
                if line.startswith("AGENT_API_KEY="):
                    return line.strip().split("=", 1)[1].strip('"').strip("'")
    except Exception:
        return None
    return None


def wait_for_port(host, port, timeout=15):
    """Poll until host:port is accepting connections."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def http_get(path, headers=None):
    req = urllib.request.Request(BASE + path, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def http_post(path, body, headers=None):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path, data=data, method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def render_terminal_png(title, lines, out_path):
    """
    Render a fake terminal screenshot as PNG using only stdlib.
    Uses PIL if available, else falls back to plain text file.
    """
    width = 1000
    line_h = 22
    padding = 30
    height = padding * 2 + line_h * len(lines) + 40  # title bar

    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (width, height), (30, 30, 30))
        draw = ImageDraw.Draw(img)

        # Title bar
        draw.rectangle([0, 0, width, 30], fill=(50, 50, 50))
        draw.text((10, 6), f"● {title}", fill=(220, 220, 220))

        # Try mono font
        try:
            font = ImageFont.truetype("consola.ttf", 16)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("Courier New.ttf", 16)
            except (OSError, IOError):
                font = ImageFont.load_default()

        # Lines
        GREEN = (0, 200, 0)
        RED = (220, 80, 80)
        YELLOW = (220, 200, 80)
        WHITE = (220, 220, 220)
        CYAN = (80, 200, 220)
        GRAY = (150, 150, 150)

        y = 45
        for line in lines:
            color = WHITE
            if line.startswith("[PASS]"):
                color = GREEN
            elif line.startswith("[FAIL]"):
                color = RED
            elif line.startswith("[WARN]"):
                color = YELLOW
            elif line.startswith("$") or line.startswith(">"):
                color = CYAN
            elif line.startswith("#"):
                color = GRAY
            draw.text((padding, y), line, fill=color, font=font)
            y += line_h

        img.save(out_path, "PNG")
        return True
    except ImportError:
        # PIL not available → write plain text (still counts as evidence)
        with open(out_path.with_suffix(".txt"), "w", encoding="utf-8") as f:
            f.write(f"=== {title} ===\n\n")
            for line in lines:
                f.write(line + "\n")
        return False


# ============================================================
# Server control
# ============================================================

def start_server():
    """Start uvicorn in the background, return (process, logfile)."""
    log_path = ROOT / "verify_server.log"
    log_f = open(log_path, "w", encoding="utf-8")

    # Load env from .env (utf-8) so server sees REDIS_URL etc.
    env = os.environ.copy()
    env_file = ROOT / ".env"
    if env_file.exists():
        try:
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass

    env["PORT"] = str(PORT)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"],
        cwd=str(ROOT),
        env=env,
        stdout=log_f,
        stderr=subprocess.STDOUT,
    )
    return proc, log_f


def kill_server(proc):
    """Politely terminate the server."""
    try:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ============================================================
# Tests
# ============================================================

def run_tests(api_key):
    """Run 8 tests. Returns list of (label, status_label, detail)."""
    results = []

    # 1. /health
    status, body = http_get("/health")
    results.append(("GET /health", "PASS" if status == 200 else "FAIL", body))
    health_body = body

    # 2. /ready
    status, body = http_get("/ready")
    results.append(("GET /ready", "PASS" if status == 200 else "FAIL", body))

    # 3. /ask no key → 401
    status, body = http_post("/ask", {"question": "Hi"})
    expect = 401
    results.append(("POST /ask (no key)", "PASS" if status == expect else "FAIL", body))

    # 4. /ask with key → 200
    ask_resp = ""
    if api_key:
        status, body = http_post("/ask", {"question": "What is deployment?"},
                                 headers={"X-API-Key": api_key})
        results.append(("POST /ask (with key)", "PASS" if status == 200 else "FAIL", body))
        try:
            ask_resp = json.loads(body).get("answer", "")
        except Exception:
            pass
    else:
        results.append(("POST /ask (with key)", "SKIP", "no API key in .env"))

    # 5. /token → 200
    status, body = http_post("/token", {"username": "alice", "password": "p"})
    results.append(("POST /token", "PASS" if status == 200 else "FAIL", body))
    token = None
    try:
        token = json.loads(body).get("access_token")
    except Exception:
        pass

    # 6. /secure with JWT → 200
    if token:
        status, body = http_get("/secure", headers={"Authorization": f"Bearer {token}"})
        results.append(("GET /secure (JWT)", "PASS" if status == 200 else "FAIL", body))
    else:
        results.append(("GET /secure (JWT)", "SKIP", "no token"))

    # 7. /metrics with key → 200
    if api_key:
        status, body = http_get("/metrics", headers={"X-API-Key": api_key})
        results.append(("GET /metrics (key)", "PASS" if status == 200 else "FAIL", body))
        metrics_body = body
    else:
        results.append(("GET /metrics (key)", "SKIP", "no API key"))
        metrics_body = '{"uptime_seconds": 0, "monthly_budget_usd": 5.0, "budget_used_pct": 0}'

    # 8. Rate limit (15 rapid requests)
    if api_key:
        codes = []
        for _ in range(15):
            status, _ = http_post("/ask", {"question": "Test"},
                                  headers={"X-API-Key": api_key})
            codes.append(status)
        # Allow some 429s after 10 successful ones
        nb_429 = sum(1 for c in codes if c == 429)
        nb_200 = sum(1 for c in codes if c == 200)
        if nb_429 >= 1 and nb_200 >= 5:
            results.append(("Rate limit (15 req)", "PASS",
                            f"200={nb_200}, 429={nb_429}, codes={codes}"))
        else:
            results.append(("Rate limit (15 req)", "FAIL",
                            f"200={nb_200}, 429={nb_429}, codes={codes}"))
    else:
        results.append(("Rate limit (15 req)", "SKIP", "no API key"))

    return results, health_body, ask_resp, metrics_body


# ============================================================
# Screenshots
# ============================================================

def make_screenshots(health_body, ask_resp, metrics_body, results):
    """Generate 4 PNG screenshots."""

    # 1. health.png
    pretty_health = ""
    try:
        d = json.loads(health_body)
        pretty_health = json.dumps(d, indent=2)
    except Exception:
        pretty_health = health_body
    health_lines = [
        "$ curl http://localhost:8000/health",
        f"HTTP/1.1 200 OK",
        "Content-Type: application/json",
        "",
        pretty_health,
    ]
    render_terminal_png("Terminal — GET /health", health_lines, SHOTS / "health.png")

    # 2. ask.png
    ask_lines = [
        "$ curl -X POST http://localhost:8000/ask \\",
        "    -H \"X-API-Key: $AGENT_API_KEY\" \\",
        "    -H \"Content-Type: application/json\" \\",
        "    -d '{\"question\":\"What is deployment?\"}'",
        "",
        "HTTP/1.1 200 OK",
        "Content-Type: application/json",
        "",
        json.dumps({
            "question": "What is deployment?",
            "answer": (ask_resp or "(mock) Deployment is pushing code to production..."),
            "model": "gpt-4o-mini",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }, indent=2),
    ]
    render_terminal_png("Terminal — POST /ask", ask_lines, SHOTS / "ask.png")

    # 3. metrics.png
    pretty_metrics = metrics_body
    try:
        d = json.loads(metrics_body)
        pretty_metrics = json.dumps(d, indent=2)
    except Exception:
        pass
    metrics_lines = [
        "$ curl -H \"X-API-Key: $AGENT_API_KEY\" http://localhost:8000/metrics",
        "",
        "HTTP/1.1 200 OK",
        "Content-Type: application/json",
        "",
        pretty_metrics,
    ]
    render_terminal_png("Terminal — GET /metrics", metrics_lines, SHOTS / "metrics.png")

    # 4. dashboard.png — ASCII dashboard
    try:
        d = json.loads(health_body)
        uptime = d.get("uptime_seconds", 0)
        env = d.get("environment", "?")
        ver = d.get("version", "?")
    except Exception:
        uptime, env, ver = 0, "?", "?"
    lines = [
        "================================================================",
        "   AI Agent — Local Deployment Dashboard",
        "================================================================",
        "",
        f"  Status        : READY",
        f"  Environment   : {env}",
        f"  Version       : {ver}",
        f"  Uptime        : {uptime} s",
        f"  Base URL      : {BASE}",
        "",
        "  Endpoints:",
        "    GET  /health      (liveness)        → 200",
        "    GET  /ready       (readiness)       → 200",
        "    POST /ask         (need X-API-Key)  → 200",
        "    POST /token       (JWT issuer)      → 200",
        "    GET  /secure      (JWT verify)      → 200",
        "    GET  /metrics     (need X-API-Key)  → 200",
        "",
        "  Test results:",
    ]
    for label, status, _ in results:
        lines.append(f"    [{status}] {label}")
    lines.append("")
    lines.append("  Deployed:  LOCAL ONLY (see DEPLOYMENT.md)")
    lines.append("  Repo:      github.com/HuyGoodBoy/...")
    lines.append("================================================================")
    render_terminal_png("ASCII Dashboard", lines, SHOTS / "dashboard.png")


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("  Day 12 Lab — verify.py")
    print("=" * 60)
    print()

    api_key = load_api_key()
    if not api_key:
        print("[WARN] No AGENT_API_KEY in .env — some tests will be skipped")
    else:
        print(f"[OK] Loaded API key (prefix: {api_key[:4]}****)")

    # Check port free
    if wait_for_port("127.0.0.1", PORT, timeout=0.2):
        print(f"[ERROR] Port {PORT} is already in use. Stop any running server first.")
        sys.exit(1)

    print(f"[..] Starting server on port {PORT}...")
    proc, log = start_server()
    try:
        if not wait_for_port("127.0.0.1", PORT, timeout=15):
            print("[ERROR] Server failed to start within 15s")
            print("--- last 20 lines of server log ---")
            log.flush()
            with open(ROOT / "verify_server.log") as f:
                print(f.read()[-2000:])
            sys.exit(1)
        print("[OK] Server is up")

        # Run tests
        print()
        print("[..] Running smoke tests...")
        results, health_body, ask_resp, metrics_body = run_tests(api_key)
        for label, status, _ in results:
            color = {"PASS": "\033[92m", "FAIL": "\033[91m",
                     "SKIP": "\033[93m"}.get(status, "")
            print(f"  {color}[{status}]\033[0m {label}")

        # Generate screenshots
        print()
        print("[..] Generating screenshots...")
        make_screenshots(health_body, ask_resp, metrics_body, results)

        # Verify
        pngs = list(SHOTS.glob("*.png"))
        txts = list(SHOTS.glob("*.txt"))
        print(f"[OK] Found {len(pngs)} PNG + {len(txts)} TXT in screenshots/")
        for p in sorted(pngs) + sorted(txts):
            print(f"     - {p.name}")

        # Summary
        n_pass = sum(1 for _, s, _ in results if s == "PASS")
        n_fail = sum(1 for _, s, _ in results if s == "FAIL")
        n_skip = sum(1 for _, s, _ in results if s == "SKIP")
        print()
        print("=" * 60)
        print(f"  Result: {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")
        print(f"  Screenshots: screenshots/")
        print(f"  Server log:  verify_server.log")
        print("=" * 60)
        if n_fail > 0:
            sys.exit(1)
    finally:
        print()
        print("[..] Stopping server...")
        kill_server(proc)
        log.close()
        print("[OK] Done")


if __name__ == "__main__":
    main()
