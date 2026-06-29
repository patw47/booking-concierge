#!/usr/bin/env bash
# Idempotent deploy script for booking-concierge on VPS.
# Calqué sur property-cm/deploy/remote.sh.
# Usage: bash deploy/remote.sh

set -euo pipefail

REPO_DIR="/opt/apps/booking-concierge"
SERVICE="booking-concierge"
PYTHON="${REPO_DIR}/.venv/bin/python"
PIP="${REPO_DIR}/.venv/bin/pip"

log() { echo "[$(date +%H:%M:%S)] $*"; }

svc_exists() { systemctl list-units --full -all | grep -Fq "$1.service"; }
svc_restart() { systemctl restart "$1" && systemctl is-active --quiet "$1"; }

# ── Step 0 — Virtual env + dependencies ──────────────────────────────────────
log "Step 0: installing dependencies"
if [ ! -d "${REPO_DIR}/.venv" ]; then
    python3 -m venv "${REPO_DIR}/.venv"
fi
${PIP} install -q --upgrade pip
${PIP} install -q -r "${REPO_DIR}/requirements.txt"

# ── Step 1 — Copy systemd unit if changed ────────────────────────────────────
log "Step 1: installing systemd unit"
UNIT_SRC="${REPO_DIR}/deploy/${SERVICE}.service"
UNIT_DST="/etc/systemd/system/${SERVICE}.service"
if ! diff -q "${UNIT_SRC}" "${UNIT_DST}" &>/dev/null 2>&1; then
    cp "${UNIT_SRC}" "${UNIT_DST}"
    systemctl daemon-reload
    log "  Unit updated — daemon reloaded"
fi
systemctl enable "${SERVICE}" --quiet

# ── Step 2 — Restart service ─────────────────────────────────────────────────
log "Step 2: restarting ${SERVICE}"
svc_restart "${SERVICE}" && log "  ${SERVICE}: OK" || { log "  ${SERVICE}: FAILED"; STATUS_OVERALL="fail"; }

# ── Step 3 — Healthcheck ─────────────────────────────────────────────────────
log "Step 3: healthcheck"
sleep 3
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:7861/" || echo "000")
if [ "${HTTP_CODE}" = "200" ] || [ "${HTTP_CODE}" = "404" ]; then
    log "  HTTP ${HTTP_CODE} — service responding"
    STATUS_OVERALL="${STATUS_OVERALL:-ok}"
else
    log "  HTTP ${HTTP_CODE} — service not responding"
    STATUS_OVERALL="fail"
fi

# ── Output ────────────────────────────────────────────────────────────────────
echo "STATUS_SERVICE=$(systemctl is-active ${SERVICE})"
echo "STATUS_OVERALL=${STATUS_OVERALL:-ok}"
