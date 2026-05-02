#!/bin/bash
set -e

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     IMS — Incident Management System Launcher        ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"

# ── Step 1: Check Docker daemon ───────────────────────────────────────────────
echo "🔍 Checking Docker..."
if ! docker info > /dev/null 2>&1; then
  echo "❌ Docker daemon is not running. Please start Docker and try again."
  exit 1
fi
echo "✅ Docker is running."
echo ""

# ── Step 2: Stop any old containers ──────────────────────────────────────────
echo "🛑 Stopping any old IMS containers..."
docker compose down --remove-orphans 2>/dev/null || true
echo ""

# ── Step 3: Build and start all services ─────────────────────────────────────
echo "🚀 Building and starting all services..."
echo "   (This may take 3-5 minutes on first run while Docker pulls images)"
echo ""
docker compose up --build -d

echo ""
echo "⏳ Waiting for services to be healthy..."

# Wait for backend to be ready (up to 120s)
TIMEOUT=120
ELAPSED=0
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
  if [ $ELAPSED -ge $TIMEOUT ]; then
    echo ""
    echo "❌ Backend did not start in time. Showing logs:"
    docker compose logs backend --tail=30
    exit 1
  fi
  printf "."
  sleep 3
  ELAPSED=$((ELAPSED + 3))
done

echo ""
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅  IMS is fully up and running!                    ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                      ║"
echo "║  🌐  Dashboard      →  http://localhost:3000         ║"
echo "║  📖  API Docs       →  http://localhost:8000/docs    ║"
echo "║  ❤️   Health Check   →  http://localhost:8000/health  ║"
echo "║                                                      ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  🐒  To run Chaos Simulator:                         ║"
echo "║      python3 sample-data/chaos_simulator.py          ║"
echo "║                                                      ║"
echo "║  🛑  To stop:  docker compose down                   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
