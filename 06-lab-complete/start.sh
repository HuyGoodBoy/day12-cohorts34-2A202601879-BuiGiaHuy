#!/usr/bin/env bash
# ============================================================
# start.sh — Quick-start script for graders / reviewers
# ============================================================
# Usage:
#   chmod +x start.sh
#   ./start.sh           # start with docker compose (recommended)
#   ./start.sh local     # run without docker (requires redis-server on :6379)
#   ./start.sh scale     # start with 3 agent replicas behind nginx
#   ./start.sh test      # run smoke tests against running server
# ============================================================

set -e

MODE="${1:-docker}"

case "$MODE" in
  docker)
    echo "Starting with Docker Compose..."
    if [ ! -f .env ]; then
      echo "ERROR: .env not found. Copy .env.example to .env first:"
      echo "  cp .env.example .env"
      echo "  # then edit .env to set strong AGENT_API_KEY and JWT_SECRET"
      exit 1
    fi
    docker compose up --build
    ;;

  local)
    echo "Starting locally (no Docker)..."
    if [ ! -f .env ]; then
      echo "ERROR: .env not found. Copy .env.example to .env first."
      exit 1
    fi
    pip install -r requirements.txt
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ;;

  scale)
    echo "Starting 3 agent replicas behind Nginx (Part 5.4)..."
    if [ ! -f .env ]; then
      echo "ERROR: .env not found."
      exit 1
    fi
    docker compose -f docker-compose.scale.yml up --build --scale agent=3
    ;;

  test)
    echo "Running smoke tests against http://localhost:8000 ..."
    python smoke_test.py
    ;;

  *)
    echo "Usage: $0 {docker|local|scale|test}"
    exit 1
    ;;
esac
