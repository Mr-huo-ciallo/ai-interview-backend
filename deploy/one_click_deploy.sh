#!/usr/bin/env bash

set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/ai-interview}"
FRONTEND_DIR="${FRONTEND_DIR:-$APP_ROOT/ai-interview-platform}"
BACKEND_DIR="${BACKEND_DIR:-$APP_ROOT/ai-interview-backend}"
DOMAIN="${DOMAIN:-your-domain.com}"
WWW_DOMAIN="${WWW_DOMAIN:-www.$DOMAIN}"
DB_NAME="${DB_NAME:-ai_interview}"
DB_USER="${DB_USER:-ai_interview_user}"
DB_PASSWORD="${DB_PASSWORD:-}"
LLM_API_KEY="${LLM_API_KEY:-}"
LLM_BASE_URL="${LLM_BASE_URL:-}"
LLM_MODEL="${LLM_MODEL:-}"
INSTALL_CERTBOT="${INSTALL_CERTBOT:-0}"

SERVICE_NAME="ai-interview-backend"
NGINX_SITE_NAME="ai-interview"
NGINX_AVAILABLE="/etc/nginx/sites-available/$NGINX_SITE_NAME"
NGINX_ENABLED="/etc/nginx/sites-enabled/$NGINX_SITE_NAME"

log() {
  printf "\n== %s ==\n" "$1"
}

die() {
  printf "ERROR: %s\n" "$1" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but not installed"
}

require_env() {
  local name="$1"
  local value="$2"
  if [ -z "$value" ]; then
    die "Missing required environment variable: $name"
  fi
}

run_as_root_sql() {
  sudo mysql -e "$1"
}

log "Checking required deployment variables"
require_env "DB_PASSWORD" "$DB_PASSWORD"
require_env "LLM_API_KEY" "$LLM_API_KEY"
require_env "LLM_BASE_URL" "$LLM_BASE_URL"
require_env "LLM_MODEL" "$LLM_MODEL"

if [ "$DOMAIN" = "your-domain.com" ]; then
  die "Please set DOMAIN before running this script"
fi

if ! printf "%s" "$DB_PASSWORD" | grep -Eq '^[A-Za-z0-9_.-]{12,}$'; then
  die "DB_PASSWORD must be at least 12 characters and only contain letters, numbers, underscore, dot, or hyphen"
fi

log "Checking project directories"
[ -d "$FRONTEND_DIR" ] || die "Frontend directory not found: $FRONTEND_DIR"
[ -d "$BACKEND_DIR" ] || die "Backend directory not found: $BACKEND_DIR"
[ -f "$FRONTEND_DIR/package.json" ] || die "Frontend package.json not found"
[ -f "$BACKEND_DIR/requirements.txt" ] || die "Backend requirements.txt not found"

log "Installing system dependencies"
sudo apt update
sudo apt install -y nginx mysql-server python3 python3-venv python3-pip nodejs npm git curl

need_command nginx
need_command mysql
need_command python3
need_command node
need_command npm
need_command curl

log "Initializing MySQL database"
sudo systemctl enable mysql
sudo systemctl start mysql
run_as_root_sql "CREATE DATABASE IF NOT EXISTS \`$DB_NAME\` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
run_as_root_sql "CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';"
run_as_root_sql "ALTER USER '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';"
run_as_root_sql "GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'localhost';"
run_as_root_sql "FLUSH PRIVILEGES;"

log "Preparing backend virtual environment"
cd "$BACKEND_DIR"
python3 -m venv .venv
"$BACKEND_DIR/.venv/bin/python" -m pip install --upgrade pip
"$BACKEND_DIR/.venv/bin/python" -m pip install -r requirements.txt

log "Writing backend .env"
cat > "$BACKEND_DIR/.env" <<EOF
DATABASE_URL=mysql+pymysql://$DB_USER:$DB_PASSWORD@127.0.0.1:3306/$DB_NAME
CORS_ORIGINS=https://$DOMAIN,https://$WWW_DOMAIN,http://$DOMAIN,http://$WWW_DOMAIN
LLM_API_KEY=$LLM_API_KEY
LLM_BASE_URL=$LLM_BASE_URL
LLM_MODEL=$LLM_MODEL
EOF
chmod 600 "$BACKEND_DIR/.env"

log "Preparing frontend production build"
cd "$FRONTEND_DIR"
npm install
cat > "$FRONTEND_DIR/.env.production" <<EOF
VITE_API_BASE_URL=
EOF
npm run build

log "Installing systemd backend service"
sudo cp "$BACKEND_DIR/deploy/$SERVICE_NAME.service" "/etc/systemd/system/$SERVICE_NAME.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

log "Installing Nginx site"
sudo cp "$FRONTEND_DIR/deploy/nginx-ai-interview.conf" "$NGINX_AVAILABLE"
sudo sed -i "s/server_name your-domain.com www.your-domain.com;/server_name $DOMAIN $WWW_DOMAIN;/" "$NGINX_AVAILABLE"

if [ -e /etc/nginx/sites-enabled/default ]; then
  sudo rm -f /etc/nginx/sites-enabled/default
fi

sudo ln -sf "$NGINX_AVAILABLE" "$NGINX_ENABLED"
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl reload nginx

if [ "$INSTALL_CERTBOT" = "1" ]; then
  log "Installing HTTPS certificate with Certbot"
  sudo apt install -y certbot python3-certbot-nginx
  sudo certbot --nginx -d "$DOMAIN" -d "$WWW_DOMAIN"
else
  log "Skipping Certbot"
  printf "Set INSTALL_CERTBOT=1 when DNS already points to this server and you want HTTPS configured automatically.\n"
fi

log "Running deployment preflight check"
chmod +x "$BACKEND_DIR/deploy/preflight_check.sh"
APP_ROOT="$APP_ROOT" \
FRONTEND_DIR="$FRONTEND_DIR" \
BACKEND_DIR="$BACKEND_DIR" \
SERVICE_NAME="$SERVICE_NAME" \
NGINX_HEALTH_URL="http://127.0.0.1/backend-health" \
"$BACKEND_DIR/deploy/preflight_check.sh"

log "Deployment finished"
printf "Frontend: http://%s\n" "$DOMAIN"
printf "Backend health: http://%s/backend-health\n" "$DOMAIN"
printf "Backend service: %s\n" "$SERVICE_NAME"
printf "Nginx site: %s\n" "$NGINX_AVAILABLE"
