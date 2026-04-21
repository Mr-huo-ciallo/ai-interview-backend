#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/opt/ai-interview"
FRONTEND_DIR="$PROJECT_ROOT/ai-interview-platform"
BACKEND_DIR="$PROJECT_ROOT/ai-interview-backend"

echo "Installing system dependencies..."
sudo apt update
sudo apt install -y nginx mysql-server python3 python3-venv python3-pip nodejs npm git

echo "Preparing backend virtual environment..."
cd "$BACKEND_DIR"
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt

if [ ! -f "$BACKEND_DIR/.env" ]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  echo "Created backend .env from .env.example. Please edit it before starting the service."
fi

echo "Preparing frontend build..."
cd "$FRONTEND_DIR"
npm install
if [ ! -f "$FRONTEND_DIR/.env.production" ]; then
  cp "$FRONTEND_DIR/.env.production.example" "$FRONTEND_DIR/.env.production"
fi
npm run build

echo "Installing systemd service and Nginx config..."
sudo cp "$BACKEND_DIR/deploy/ai-interview-backend.service" /etc/systemd/system/ai-interview-backend.service
sudo systemctl daemon-reload
sudo systemctl enable ai-interview-backend

sudo cp "$FRONTEND_DIR/deploy/nginx-ai-interview.conf" /etc/nginx/sites-available/ai-interview
if [ ! -L /etc/nginx/sites-enabled/ai-interview ]; then
  sudo ln -s /etc/nginx/sites-available/ai-interview /etc/nginx/sites-enabled/ai-interview
fi

sudo nginx -t

echo "Bootstrap finished."
echo "Next steps:"
echo "1. Edit $BACKEND_DIR/.env"
echo "2. Edit /etc/nginx/sites-available/ai-interview and replace your-domain.com"
echo "3. Run: sudo systemctl start ai-interview-backend"
echo "4. Run: sudo systemctl reload nginx"
