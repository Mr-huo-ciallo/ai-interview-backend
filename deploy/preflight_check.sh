#!/usr/bin/env bash

set -u

APP_ROOT="${APP_ROOT:-/opt/ai-interview}"
FRONTEND_DIR="${FRONTEND_DIR:-$APP_ROOT/ai-interview-platform}"
BACKEND_DIR="${BACKEND_DIR:-$APP_ROOT/ai-interview-backend}"
SERVICE_NAME="${SERVICE_NAME:-ai-interview-backend}"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000/}"
NGINX_HEALTH_URL="${NGINX_HEALTH_URL:-http://127.0.0.1/backend-health}"

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

print_title() {
  printf "\n== %s ==\n" "$1"
}

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf "[PASS] %s\n" "$1"
}

warn() {
  WARN_COUNT=$((WARN_COUNT + 1))
  printf "[WARN] %s\n" "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf "[FAIL] %s\n" "$1"
}

has_command() {
  command -v "$1" >/dev/null 2>&1
}

check_file() {
  if [ -f "$1" ]; then
    pass "$2"
  else
    fail "$3"
  fi
}

check_dir() {
  if [ -d "$1" ]; then
    pass "$2"
  else
    fail "$3"
  fi
}

check_command() {
  if has_command "$1"; then
    local version
    version="$("$@" 2>&1 | head -n 1)"
    pass "$1 available: $version"
  else
    fail "$1 is not installed"
  fi
}

check_systemd_service() {
  local service="$1"
  if ! has_command systemctl; then
    warn "systemctl is unavailable; skipped $service service check"
    return
  fi

  if systemctl list-unit-files "$service.service" >/dev/null 2>&1; then
    pass "systemd service file exists: $service"
  else
    fail "systemd service file missing: $service"
  fi

  if systemctl is-enabled "$service" >/dev/null 2>&1; then
    pass "systemd service enabled: $service"
  else
    warn "systemd service is not enabled: $service"
  fi

  if systemctl is-active "$service" >/dev/null 2>&1; then
    pass "systemd service running: $service"
  else
    fail "systemd service is not running: $service"
  fi
}

check_http() {
  local url="$1"
  local name="$2"
  if ! has_command curl; then
    warn "curl is unavailable; skipped $name HTTP check"
    return
  fi

  local code
  code="$(curl -L -s -o /dev/null -w "%{http_code}" --max-time 8 "$url" || true)"
  case "$code" in
    200|204|301|302)
      pass "$name reachable: $url ($code)"
      ;;
    000)
      fail "$name unreachable: $url"
      ;;
    *)
      warn "$name returned HTTP $code: $url"
      ;;
  esac
}

check_port() {
  local port="$1"
  local name="$2"
  if has_command ss; then
    if ss -ltn | grep -q ":$port "; then
      pass "$name port listening: $port"
    else
      fail "$name port is not listening: $port"
    fi
  else
    warn "ss is unavailable; skipped $name port check"
  fi
}

print_title "AceHire AI Deployment Preflight"
printf "APP_ROOT=%s\n" "$APP_ROOT"
printf "FRONTEND_DIR=%s\n" "$FRONTEND_DIR"
printf "BACKEND_DIR=%s\n" "$BACKEND_DIR"

print_title "1. System Commands"
check_command nginx -v
check_command mysql --version
check_command python3 --version
check_command node -v
check_command npm -v
check_command git --version
check_command curl --version

print_title "2. Project Directories"
check_dir "$APP_ROOT" "app root exists: $APP_ROOT" "app root missing: $APP_ROOT"
check_dir "$FRONTEND_DIR" "frontend dir exists: $FRONTEND_DIR" "frontend dir missing: $FRONTEND_DIR"
check_dir "$BACKEND_DIR" "backend dir exists: $BACKEND_DIR" "backend dir missing: $BACKEND_DIR"

print_title "3. Frontend"
check_file "$FRONTEND_DIR/package.json" "frontend package.json exists" "frontend package.json missing"
check_file "$FRONTEND_DIR/.env.production" "frontend .env.production exists" "frontend .env.production missing"
check_dir "$FRONTEND_DIR/dist" "frontend dist exists" "frontend dist missing; run npm run build"
check_file "$FRONTEND_DIR/dist/index.html" "frontend dist/index.html exists" "frontend dist/index.html missing"
check_dir "$FRONTEND_DIR/dist/assets" "frontend dist/assets exists" "frontend dist/assets missing"

if [ -d "$FRONTEND_DIR/src/fakeview" ]; then
  warn "unused frontend fakeview directory still exists"
else
  pass "unused frontend fakeview directory is absent"
fi

if [ -f "$FRONTEND_DIR/.env.production" ]; then
  if grep -q '^VITE_API_BASE_URL=' "$FRONTEND_DIR/.env.production"; then
    pass "frontend VITE_API_BASE_URL is configured"
  else
    warn "frontend VITE_API_BASE_URL is not found in .env.production"
  fi
fi

print_title "4. Backend"
check_file "$BACKEND_DIR/main.py" "backend main.py exists" "backend main.py missing"
check_file "$BACKEND_DIR/requirements.txt" "backend requirements.txt exists" "backend requirements.txt missing"
check_dir "$BACKEND_DIR/.venv" "backend .venv exists" "backend .venv missing"
check_file "$BACKEND_DIR/.venv/bin/python" "backend venv python exists" "backend venv python missing"
check_file "$BACKEND_DIR/.env" "backend .env exists" "backend .env missing"

if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
  if "$BACKEND_DIR/.venv/bin/python" -c "import fastapi, uvicorn, sqlalchemy, pymysql, httpx, dotenv" >/dev/null 2>&1; then
    pass "backend Python dependencies import successfully"
  else
    fail "backend Python dependencies import failed"
  fi
fi

if [ -f "$BACKEND_DIR/.env" ]; then
  grep -q '^DATABASE_URL=' "$BACKEND_DIR/.env" && pass "DATABASE_URL exists" || fail "DATABASE_URL missing"
  grep -q '^CORS_ORIGINS=' "$BACKEND_DIR/.env" && pass "CORS_ORIGINS exists" || warn "CORS_ORIGINS missing"
  grep -q '^LLM_API_KEY=' "$BACKEND_DIR/.env" && pass "LLM_API_KEY exists" || warn "LLM_API_KEY missing"
  grep -q '^LLM_BASE_URL=' "$BACKEND_DIR/.env" && pass "LLM_BASE_URL exists" || warn "LLM_BASE_URL missing"
  grep -q '^LLM_MODEL=' "$BACKEND_DIR/.env" && pass "LLM_MODEL exists" || warn "LLM_MODEL missing"

  if grep -q 'change_me\|example.com\|你的模型\|请替换' "$BACKEND_DIR/.env"; then
    fail "backend .env still contains placeholder values"
  else
    pass "backend .env does not contain common placeholder values"
  fi
fi

print_title "5. Database"
if has_command systemctl; then
  if systemctl is-active mysql >/dev/null 2>&1; then
    pass "mysql service running"
  else
    fail "mysql service is not running"
  fi
fi

if has_command mysql; then
  if mysql -u ai_interview_user -e "USE ai_interview; SELECT 1;" >/dev/null 2>&1; then
    pass "database ai_interview accessible as ai_interview_user without password prompt"
  else
    warn "database direct login check skipped or failed; this is expected if password login is required"
  fi
fi

print_title "6. systemd"
check_file "/etc/systemd/system/$SERVICE_NAME.service" "service file exists in /etc/systemd/system" "service file missing in /etc/systemd/system"
check_systemd_service "$SERVICE_NAME"

print_title "7. Nginx"
check_file "/etc/nginx/sites-available/ai-interview" "Nginx site config exists" "Nginx site config missing"
check_file "/etc/nginx/sites-enabled/ai-interview" "Nginx site enabled" "Nginx site is not enabled"

if has_command nginx; then
  if nginx -t >/tmp/ai-interview-nginx-check.log 2>&1; then
    pass "nginx -t passed"
  else
    fail "nginx -t failed; see /tmp/ai-interview-nginx-check.log"
  fi
fi

if has_command systemctl; then
  if systemctl is-active nginx >/dev/null 2>&1; then
    pass "nginx service running"
  else
    fail "nginx service is not running"
  fi
fi

check_port 80 "Nginx HTTP"
check_port 8000 "Backend"
check_http "$BACKEND_URL" "Backend local health"
check_http "$NGINX_HEALTH_URL" "Nginx backend health"

print_title "8. Disk And Memory"
if has_command df; then
  df -h /
fi
if has_command free; then
  free -h
fi

print_title "Summary"
printf "PASS=%s WARN=%s FAIL=%s\n" "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT"

if [ "$FAIL_COUNT" -gt 0 ]; then
  printf "Preflight result: FAILED\n"
  exit 1
fi

if [ "$WARN_COUNT" -gt 0 ]; then
  printf "Preflight result: PASSED WITH WARNINGS\n"
  exit 0
fi

printf "Preflight result: PASSED\n"
