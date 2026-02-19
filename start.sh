#!/bin/bash
# Start jobs-agent API + frontend
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "Starting jobs-agent..."

# Check if already running
if curl -s --max-time 2 http://localhost:8000/api/health > /dev/null 2>&1; then
  echo "⚠️  API already running on :8000"
else
  source .venv/bin/activate
  nohup uvicorn api.main:app --host 0.0.0.0 --port 8000 > /tmp/jobs-agent-api.log 2>&1 &
  echo "$!" > /tmp/jobs-agent-api.pid
  echo "✓ API started (PID $!, log: /tmp/jobs-agent-api.log)"
fi

if curl -s --max-time 2 http://localhost:3001 > /dev/null 2>&1; then
  echo "⚠️  Frontend already running on :3001"
else
  cd "$DIR/web"
  nohup npx vite --port 3001 > /tmp/jobs-agent-vite.log 2>&1 &
  echo "$!" > /tmp/jobs-agent-vite.pid
  echo "✓ Frontend started (PID $!, log: /tmp/jobs-agent-vite.log)"
fi

# Wait and verify
sleep 3

FAIL=0
if curl -s --max-time 5 http://localhost:8000/api/health > /dev/null 2>&1; then
  echo "✓ API healthy on http://localhost:8000"
else
  echo "✗ API failed to start — check /tmp/jobs-agent-api.log"
  FAIL=1
fi

if curl -s --max-time 5 http://localhost:3001 > /dev/null 2>&1; then
  echo "✓ Frontend serving on http://localhost:3001"
else
  echo "✗ Frontend failed to start — check /tmp/jobs-agent-vite.log"
  FAIL=1
fi

exit $FAIL
