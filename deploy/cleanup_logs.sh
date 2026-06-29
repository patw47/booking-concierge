#!/usr/bin/env bash
# Purge booking-concierge log files older than LOG_RETENTION_DAYS (default 30).
# Run daily via systemd timer (booking-concierge-cleanup.timer) or manually.
# Does NOT touch loguru-rotated .log files — loguru handles those itself.

set -euo pipefail

LOG_DIR="${LOG_DIR:-/opt/apps/booking-concierge/var/logs}"
RETENTION_DAYS="${LOG_RETENTION_DAYS:-30}"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

if [ ! -d "${LOG_DIR}" ]; then
    log "Log dir ${LOG_DIR} not found — nothing to purge."
    exit 0
fi

count=$(find "${LOG_DIR}" -name "transcript-*.jsonl" -mtime "+${RETENTION_DAYS}" -print -delete | wc -l)

if [ "${count}" -gt 0 ]; then
    log "Purged ${count} transcript file(s) older than ${RETENTION_DAYS} days."
else
    log "No transcript files older than ${RETENTION_DAYS} days."
fi
