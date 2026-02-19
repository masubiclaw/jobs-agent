#!/bin/bash
# Quick API smoke test for jobs-agent
# Usage: ./test_api.sh [base_url]

BASE="${1:-http://localhost:8000}"
API="$BASE/api"
PASS=0
FAIL=0
TOKEN=""

green() { printf "\033[32m✓ %s\033[0m\n" "$1"; PASS=$((PASS+1)); }
red()   { printf "\033[31m✗ %s\033[0m\n" "$1"; FAIL=$((FAIL+1)); }

check() {
  local label="$1" url="$2" method="${3:-GET}" data="$4" expected="${5:-200}"

  if [ "$method" = "GET" ]; then
    CODE=$(curl -s -o /tmp/api_test_body -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$url")
  else
    CODE=$(curl -s -o /tmp/api_test_body -w "%{http_code}" -X "$method" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d "$data" "$url")
  fi

  BODY=$(cat /tmp/api_test_body)

  if [ "$CODE" = "$expected" ]; then
    green "$label (HTTP $CODE)"
  else
    red "$label — expected $expected, got $CODE"
    echo "    Response: $(echo "$BODY" | head -c 200)"
  fi
}

echo ""
echo "=== Jobs-Agent API Smoke Test ==="
echo "Target: $BASE"
echo ""

# --- Health ---
echo "--- Health ---"
check "GET /api/health" "$API/health"

# --- Auth: Register + Login ---
echo ""
echo "--- Auth ---"
TS=$(date +%s)
EMAIL="test_${TS}@example.com"

# Register
CODE=$(curl -s -o /tmp/api_test_body -w "%{http_code}" -X POST \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Test User\",\"email\":\"$EMAIL\",\"password\":\"TestPass123!\"}" \
  "$API/auth/register")
BODY=$(cat /tmp/api_test_body)
if [ "$CODE" = "201" ] || [ "$CODE" = "200" ]; then
  green "POST /api/auth/register (HTTP $CODE)"
else
  red "POST /api/auth/register — got $CODE"
  echo "    $BODY"
fi

# Login
CODE=$(curl -s -o /tmp/api_test_body -w "%{http_code}" -X POST \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"TestPass123!\"}" \
  "$API/auth/login")
BODY=$(cat /tmp/api_test_body)
TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [ -n "$TOKEN" ] && [ "$CODE" = "200" ]; then
  green "POST /api/auth/login (HTTP $CODE, got token)"
else
  red "POST /api/auth/login — got $CODE, no token"
  echo "    $BODY"
fi

# --- Profiles ---
echo ""
echo "--- Profiles ---"
check "GET /api/profiles" "$API/profiles"

# Create profile
PROFILE_DATA='{"name":"Test User","email":"test@example.com","phone":"555-0100","location":"Seattle, WA"}'
CODE=$(curl -s -o /tmp/api_test_body -w "%{http_code}" -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "$PROFILE_DATA" "$API/profiles")
BODY=$(cat /tmp/api_test_body)
PROFILE_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
if [ "$CODE" = "201" ] && [ -n "$PROFILE_ID" ]; then
  green "POST /api/profiles (HTTP $CODE, id=$PROFILE_ID)"
else
  red "POST /api/profiles — got $CODE"
  echo "    $(echo "$BODY" | head -c 200)"
fi

# Get profile
if [ -n "$PROFILE_ID" ]; then
  check "GET /api/profiles/:id" "$API/profiles/$PROFILE_ID"

  # Update profile
  check "PUT /api/profiles/:id" "$API/profiles/$PROFILE_ID" "PUT" \
    '{"name":"Test User Updated","location":"Portland, OR"}'

  # Activate profile
  check "POST /api/profiles/:id/activate" "$API/profiles/$PROFILE_ID/activate" "POST" "{}"

  # Delete profile
  check "DELETE /api/profiles/:id" "$API/profiles/$PROFILE_ID" "DELETE" "" "204"
fi

# --- Jobs ---
echo ""
echo "--- Jobs ---"
check "GET /api/jobs" "$API/jobs"
check "GET /api/jobs/top" "$API/jobs/top"

# --- Admin (may fail if test user isn't admin) ---
echo ""
echo "--- Admin (test user is not admin, expect 403) ---"
check "GET /api/admin/stats (non-admin → 403)" "$API/admin/stats" "GET" "" "403"
check "GET /api/admin/pipeline/status (non-admin → 403)" "$API/admin/pipeline/status" "GET" "" "403"

# --- Summary ---
echo ""
echo "==========================="
printf "Results: \033[32m%d passed\033[0m, \033[31m%d failed\033[0m\n" "$PASS" "$FAIL"
echo "==========================="
echo ""

rm -f /tmp/api_test_body
exit $FAIL
