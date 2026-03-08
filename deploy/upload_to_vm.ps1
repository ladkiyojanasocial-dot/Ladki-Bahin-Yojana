# Kisan Portal Alerts Agent — Upload to Oracle Cloud VM
# Edit the two variables below, then right-click this file → "Run with PowerShell"

$KEY_PATH = "C:\path\to\your-oracle-key.key"   # ← Change this
$VM_IP    = "YOUR_PUBLIC_IP"                     # ← Change this

# Project root (same folder as this script's parent)
$PROJECT_ROOT = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not (Test-Path "$PROJECT_ROOT\main.py")) {
    $PROJECT_ROOT = "G:\Kisan Portal Alerts App"   # Fallback if run from elsewhere
}

Write-Host "Uploading Kisan Portal Alerts Agent to Oracle Cloud VM..." -ForegroundColor Green
Write-Host "Project: $PROJECT_ROOT" -ForegroundColor Gray

# Upload Python files
scp -i $KEY_PATH "$PROJECT_ROOT\main.py" "ubuntu@${VM_IP}:/opt/kisan-agent/"
scp -i $KEY_PATH "$PROJECT_ROOT\config.py" "ubuntu@${VM_IP}:/opt/kisan-agent/"
scp -i $KEY_PATH "$PROJECT_ROOT\.env" "ubuntu@${VM_IP}:/opt/kisan-agent/"
scp -i $KEY_PATH "$PROJECT_ROOT\requirements.txt" "ubuntu@${VM_IP}:/opt/kisan-agent/"
scp -i $KEY_PATH "$PROJECT_ROOT\gemini_client.py" "ubuntu@${VM_IP}:/opt/kisan-agent/"

# Upload modules
scp -i $KEY_PATH -r "$PROJECT_ROOT\sources" "ubuntu@${VM_IP}:/opt/kisan-agent/"
scp -i $KEY_PATH -r "$PROJECT_ROOT\detection" "ubuntu@${VM_IP}:/opt/kisan-agent/"
scp -i $KEY_PATH -r "$PROJECT_ROOT\notifications" "ubuntu@${VM_IP}:/opt/kisan-agent/"
scp -i $KEY_PATH -r "$PROJECT_ROOT\writer" "ubuntu@${VM_IP}:/opt/kisan-agent/"
scp -i $KEY_PATH -r "$PROJECT_ROOT\publisher" "ubuntu@${VM_IP}:/opt/kisan-agent/"
scp -i $KEY_PATH -r "$PROJECT_ROOT\database" "ubuntu@${VM_IP}:/opt/kisan-agent/"

# Upload service file
scp -i $KEY_PATH "$PROJECT_ROOT\deploy\kisan-agent.service" "ubuntu@${VM_IP}:/opt/kisan-agent/"

Write-Host ""
Write-Host "Upload complete!" -ForegroundColor Green
Write-Host "Now SSH in and restart: sudo systemctl restart kisan-agent" -ForegroundColor Yellow
Read-Host "Press Enter to close"
