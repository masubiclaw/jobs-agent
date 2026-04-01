#!/bin/bash
# Start jobs-agent API + frontend
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

API_PORT=8002
FRONTEND_PORT=3001

echo "Starting jobs-agent..."

# Check if already running
if curl -s --max-time 2 http://localhost:$API_PORT/api/health > /dev/null 2>&1; then
  echo "⚠️  API already running on :$API_PORT"
else
  source .venv/bin/activate
  nohup uvicorn api.main:app --host 0.0.0.0 --port $API_PORT > /tmp/jobs-agent-api.log 2>&1 &
  echo "$!" > /tmp/jobs-agent-api.pid
  echo "✓ API started (PID $!, log: /tmp/jobs-agent-api.log)"
fi

if curl -s --max-time 2 http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
  echo "⚠️  Frontend already running on :$FRONTEND_PORT"
else
  cd "$DIR/web"
  nohup npx vite --port $FRONTEND_PORT > /tmp/jobs-agent-vite.log 2>&1 &
  echo "$!" > /tmp/jobs-agent-vite.pid
  echo "✓ Frontend started (PID $!, log: /tmp/jobs-agent-vite.log)"
fi

# Wait and verify
sleep 3

FAIL=0
if curl -s --max-time 5 http://localhost:$API_PORT/api/health > /dev/null 2>&1; then
  echo "✓ API healthy on http://localhost:$API_PORT"
else
  echo "✗ API failed to start — check /tmp/jobs-agent-api.log"
  FAIL=1
fi

if curl -s --max-time 5 http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
  echo "✓ Frontend serving on http://localhost:$FRONTEND_PORT"
else
  echo "✗ Frontend failed to start — check /tmp/jobs-agent-vite.log"
  FAIL=1
fi

exit $FAIL
