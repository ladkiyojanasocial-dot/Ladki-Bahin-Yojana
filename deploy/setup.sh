#!/bin/bash
# ══════════════════════════════════════════════════════
# Kisan Portal Alerts Agent — Oracle Cloud VM Setup Script
# Run this ONCE after SSH-ing into your new VM
# ══════════════════════════════════════════════════════

set -e

echo "=========================================="
echo "  Kisan Portal Alerts Agent — Server Setup"
echo "=========================================="

# 1. Update system
echo "[1/6] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# 2. Install Python 3.11+ and pip
echo "[2/6] Installing Python..."
sudo apt install -y python3 python3-pip python3-venv git

# 3. Create project directory
echo "[3/6] Setting up project directory..."
sudo mkdir -p /opt/kisan-agent
sudo chown $USER:$USER /opt/kisan-agent

# 4. Create virtual environment
echo "[4/6] Creating Python virtual environment..."
cd /opt/kisan-agent
python3 -m venv venv
source venv/bin/activate

# 5. Install dependencies
echo "[5/6] Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# 6. Create directories
echo "[6/6] Creating directories..."
mkdir -p images logs

echo ""
echo "=========================================="
echo "  Setup complete!"
echo "=========================================="
echo ""
echo "NEXT STEPS:"
echo "  1. Upload your project files to /opt/kisan-agent/"
echo "  2. Create your .env file with API keys"
echo "  3. Run: sudo cp kisan-agent.service /etc/systemd/system/"
echo "  4. Run: sudo systemctl enable kisan-agent"
echo "  5. Run: sudo systemctl start kisan-agent"
echo ""
echo "Check status: sudo systemctl status kisan-agent"
echo "View logs:    sudo journalctl -u kisan-agent -f"
