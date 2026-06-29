#!/usr/bin/env bash
# Idempotent deploy script for booking-concierge on hetzner-vps.
# Run on VPS as queenp (has sudo). Assumes repo already cloned.
#
# Initial setup (one-time, run manually):
#   sudo useradd -r -m -d /home/booking -s /sbin/nologin booking
#   sudo groupadd -f apps
#   sudo usermod -aG apps booking
#   sudo mkdir -p /opt/apps/booking-concierge
#   sudo chown booking:apps /opt/apps/booking-concierge
#   sudo -u booking git clone https://github.com/patw47/booking-concierge.git /opt/apps/booking-concierge
#   # Copy .env and service account key:
#   sudo cp /path/to/.env /opt/apps/booking-concierge/.env
#   sudo chown booking:apps /opt/apps/booking-concierge/.env
#   sudo chmod 600 /opt/apps/booking-concierge/.env
#   sudo cp /path/to/property-cm-agent-key.json /opt/apps/booking-concierge/
#   sudo chown booking:apps /opt/apps/booking-concierge/property-cm-agent-key.json
#   sudo chmod 600 /opt/apps/booking-concierge/property-cm-agent-key.json
#
# Usage (subsequent deploys):
#   ssh hetzner-vps "bash /opt/apps/booking-concierge/deploy/remote.sh"
# Or from local:
#   ssh hetzner-vps "cd /opt/apps/booking-concierge && git pull && bash deploy/remote.sh"

set -euo pipefail

REPO_DIR="/opt/apps/booking-concierge"
SERVICE="booking-concierge"
VENV="${REPO_DIR}/.venv"
PIP="${VENV}/bin/pip"
TRAEFIK_DYNAMIC_DIR="/root/infra/traefik/dynamic"

log() { echo "[$(date +%H:%M:%S)] $*"; }
die() { log "FATAL: $*"; exit 1; }

[ -d "${REPO_DIR}" ] || die "Repo not found at ${REPO_DIR}. Run initial setup first."

# ── Step 1 — Git pull ─────────────────────────────────────────────────────────
log "Step 1: git pull"
sudo -u booking git -C "${REPO_DIR}" pull --ff-only
log "  $(sudo -u booking git -C "${REPO_DIR}" log -1 --format='%h %s')"

# ── Step 2 — Virtual env + dependencies ──────────────────────────────────────
log "Step 2: venv + pip install"
if [ ! -d "${VENV}" ]; then
    sudo -u booking python3 -m venv "${VENV}"
fi
sudo -u booking "${PIP}" install -q --upgrade pip
sudo -u booking "${PIP}" install -q -r "${REPO_DIR}/requirements.txt"
log "  deps OK"

# ── Step 3 — Systemd unit ────────────────────────────────────────────────────
log "Step 3: systemd unit"
UNIT_SRC="${REPO_DIR}/deploy/${SERVICE}.service"
UNIT_DST="/etc/systemd/system/${SERVICE}.service"
if ! diff -q "${UNIT_SRC}" "${UNIT_DST}" &>/dev/null; then
    sudo cp "${UNIT_SRC}" "${UNIT_DST}"
    sudo systemctl daemon-reload
    log "  unit updated"
fi
sudo systemctl enable "${SERVICE}" --quiet

# ── Step 4 — Traefik dynamic config ──────────────────────────────────────────
log "Step 4: Traefik config"
TRAEFIK_SRC="${REPO_DIR}/deploy/traefik-booking-concierge.yml"
TRAEFIK_DST="${TRAEFIK_DYNAMIC_DIR}/${SERVICE}.yml"
if ! diff -q "${TRAEFIK_SRC}" "${TRAEFIK_DST}" &>/dev/null; then
    sudo cp "${TRAEFIK_SRC}" "${TRAEFIK_DST}"
    log "  Traefik config updated — hot-reloaded automatically"
else
    log "  Traefik config unchanged"
fi

# ── Step 5 — UFW: WebRTC media relay ─────────────────────────────────────────
log "Step 5: UFW rules"
# aiortc binds dynamic UDP ports for WebRTC media — browser needs to reach them.
if ! sudo ufw status | grep -q "49152:65535/udp"; then
    sudo ufw allow 49152:65535/udp comment "WebRTC media relay"
    log "  UFW: 49152-65535/udp opened"
else
    log "  UFW: WebRTC range already open"
fi

# ── Step 6 — Restart service ─────────────────────────────────────────────────
log "Step 6: restart ${SERVICE}"
sudo systemctl restart "${SERVICE}"
sleep 3
if sudo systemctl is-active --quiet "${SERVICE}"; then
    log "  ${SERVICE}: active"
else
    log "  ${SERVICE}: FAILED — check: journalctl -u ${SERVICE} -n 50"
    exit 1
fi

# ── Step 7 — Healthcheck ─────────────────────────────────────────────────────
log "Step 7: healthcheck"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:7861/" || echo "000")
if [ "${HTTP_CODE}" = "200" ] || [ "${HTTP_CODE}" = "404" ]; then
    log "  HTTP ${HTTP_CODE} — service responding on :7861"
else
    log "  HTTP ${HTTP_CODE} — service not responding on :7861"
    log "  Check: journalctl -u ${SERVICE} -n 50 --no-pager"
    exit 1
fi

# ── Done ──────────────────────────────────────────────────────────────────────
log "Deploy complete."
log "Service: https://concierge.code-art.ch (once DNS + Traefik auth configured)"
log "Logs:    journalctl -u ${SERVICE} -f"
