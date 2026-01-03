#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/voice-assistant-client"
ENV_FILE="/etc/voice-assistant-client.env"
SERVICE_FILE="/etc/systemd/system/voice-assistant-client.service"

echo "📦 Installing system dependencies..."
sudo -n apt-get update
sudo -n apt-get install -y ffmpeg git

# uv
if ! command -v uv >/dev/null 2>&1; then
  echo "📦 Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# app checkout
if [ ! -d "$APP_DIR/.git" ]; then
  echo "📥 Cloning voice-assistant-client..."
  sudo -n mkdir -p "$APP_DIR"
  sudo -n chown -R "$USER:$USER" "$APP_DIR"
  git clone https://github.com/Highgrove-Home/app-voice-assistant-client "$APP_DIR"
fi

cd "$APP_DIR"
echo "🔄 Updating repository..."
git fetch origin
git checkout main
git pull --ff-only

echo "📦 Installing Python dependencies..."
uv sync

# env file (per-device values)
if [ ! -f "$ENV_FILE" ]; then
  echo "⚙️  Creating environment configuration..."
  sudo -n tee "$ENV_FILE" >/dev/null <<'EOF'
ROOM=bedroom
PIPECAT_SERVER=http://pi-voice.local:7860
ALSA_DEVICE=plughw:1,0
EOF
  sudo -n chmod 0644 "$ENV_FILE"
  echo "⚠️  Please edit $ENV_FILE to set the correct ROOM name for this device"
fi

# systemd service
echo "⚙️  Creating systemd service..."
sudo -n tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=Voice Assistant Client
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
Environment=PATH=$HOME/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/usr/bin/env bash -lc 'cd $APP_DIR && uv run python client.py'
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

echo "🚀 Enabling and starting service..."
sudo -n /usr/bin/systemctl daemon-reload
sudo -n /usr/bin/systemctl enable --now voice-assistant-client
sudo -n /usr/bin/systemctl --no-pager --full status voice-assistant-client || true

echo ""
echo "=========================================="
echo "GitHub Actions Self-Hosted Runner Setup"
echo "=========================================="
echo ""

# Get room name from env file
ROOM=$(grep "^ROOM=" "$ENV_FILE" | cut -d'=' -f2)

echo "This device will be registered as a GitHub Actions runner with labels:"
echo "  - voice-assistant-client"
echo "  - $ROOM"
echo ""
echo "To get the registration token:"
echo "  1. Go to: https://github.com/Highgrove-Home/app-voice-assistant-client/settings/actions/runners/new"
echo "  2. Select 'Linux' as the OS"
echo "  3. Copy the token from the './config.sh' command"
echo ""
read -p "Enter GitHub runner registration token (or press Enter to skip): " RUNNER_TOKEN

if [ -n "$RUNNER_TOKEN" ]; then
  RUNNER_DIR="$HOME/actions-runner"

  if [ ! -d "$RUNNER_DIR" ]; then
    echo "📦 Setting up GitHub Actions runner..."
    mkdir -p "$RUNNER_DIR"
    cd "$RUNNER_DIR"

    # Download latest runner
    RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | grep tag_name | cut -d'"' -f4 | sed 's/v//')
    curl -o actions-runner-linux-x64.tar.gz -L "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
    tar xzf actions-runner-linux-x64.tar.gz
    rm actions-runner-linux-x64.tar.gz
  else
    cd "$RUNNER_DIR"
  fi

  # Configure runner
  echo "🔧 Configuring runner..."
  ./config.sh \
    --url https://github.com/Highgrove-Home/app-voice-assistant-client \
    --token "$RUNNER_TOKEN" \
    --name "$(hostname)-$ROOM" \
    --labels "voice-assistant-client,$ROOM" \
    --work _work \
    --replace

  # Install as service
  echo "🚀 Installing runner as service..."
  sudo ./svc.sh install
  sudo ./svc.sh start

  # Add sudoers permissions for deployment
  echo "🔐 Setting up sudo permissions for deployment..."
  echo "$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl" | sudo tee /etc/sudoers.d/voice-assistant-client >/dev/null
  sudo chmod 0440 /etc/sudoers.d/voice-assistant-client

  echo "✅ GitHub Actions runner configured and started"
else
  echo "⏭️  Skipping GitHub Actions runner setup"
fi

cd "$APP_DIR"

echo ""
echo "✅ Bootstrap complete!"
echo ""
echo "Next steps:"
echo "  1. Edit $ENV_FILE to set the correct ROOM name"
echo "  2. Run: sudo systemctl restart voice-assistant-client"
echo "  3. Check logs: sudo journalctl -u voice-assistant-client -f"
