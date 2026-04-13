#!/usr/bin/env bash
# setup.sh — installs the RedNotebook API
# Run as your normal user (not root); sudo is called where needed.
set -e

INSTALL_DIR=/opt/rednotebook-api
SERVICE_NAME="rednotebook-api@${USER}"
PORT=8000

echo "==> Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-venv python3-pip

echo "==> Creating install directory at $INSTALL_DIR..."
sudo mkdir -p "$INSTALL_DIR"
sudo cp main.py requirements.txt "$INSTALL_DIR/"
sudo chown -R "$USER":"$USER" "$INSTALL_DIR"

echo "==> Creating Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install -q --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"

echo "==> Installing systemd service..."
sudo cp "rednotebook-api@.service" /etc/systemd/system/
sudo systemd-analyze verify /etc/systemd/system/rednotebook-api@.service 2>/dev/null || true
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo ""
echo "✓ Service installed and running."
echo ""
echo "  Status:   sudo systemctl status $SERVICE_NAME"
echo "  Logs:     journalctl -u $SERVICE_NAME -f"
echo "  API docs: http://localhost:$PORT/docs"
echo ""

# Show local IP so you know what to put in the Android app
LOCAL_IP=$(hostname -I | awk '{print $1}')
echo "  Android app URL: http://$LOCAL_IP:$PORT"
echo ""
echo "  Make sure port $PORT is open on your firewall:"
echo "    sudo ufw allow $PORT/tcp   # if using ufw"
