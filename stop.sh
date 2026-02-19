#!/bin/bash
# Stop jobs-agent API + frontend
echo "Stopping jobs-agent..."

# Kill API
if pkill -f "uvicorn api.main:app" 2>/dev/null; then
  echo "✓ API stopped"
else
  echo "- API was not running"
fi

# Kill Vite
if pkill -f "vite.*--port 3001" 2>/dev/null; then
  echo "✓ Frontend stopped"
else
  echo "- Frontend was not running"
fi

# Cleanup PID files
rm -f /tmp/jobs-agent-api.pid /tmp/jobs-agent-vite.pid

# Verify
sleep 1
if curl -s --max-time 2 http://localhost:8000/api/health > /dev/null 2>&1; then
  echo "⚠️  API still responding — force killing"
  pkill -9 -f "uvicorn api.main:app" 2>/dev/null
fi

if curl -s --max-time 2 http://localhost:3001 > /dev/null 2>&1; then
  echo "⚠️  Frontend still responding — force killing"
  pkill -9 -f "vite.*--port 3001" 2>/dev/null
fi

echo "Done."
