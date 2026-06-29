"""
event_logger — sets up loguru file sink for booking-concierge events.

Call setup_event_log() once at process startup. The loguru file sink
handles daily rotation and auto-retention of the events log. Transcript
JSONL files (managed by TranscriptObserver) are purged here on startup
since loguru doesn't know about them.

Log directory: var/logs/ (gitignored, chmod 600 on files)
"""

import os
import stat
import time
from pathlib import Path

from loguru import logger

_SINK_ADDED = False


def setup_event_log(log_dir: Path, retention_days: int = 30) -> None:
    """Add loguru file sink and purge stale log files.

    Safe to call multiple times — only the first call adds the sink.
    """
    global _SINK_ADDED
    log_dir.mkdir(parents=True, exist_ok=True)

    if not _SINK_ADDED:
        log_file = log_dir / "events.log"
        logger.add(
            str(log_file),
            rotation="00:00",       # rotate daily at midnight
            retention=f"{retention_days} days",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
            level="INFO",
            enqueue=True,           # non-blocking, thread-safe queue
            encoding="utf-8",
        )
        _SINK_ADDED = True
        logger.info(f"[event_log] sink → {log_file} (retention {retention_days}d)")

    _purge_transcripts(log_dir, retention_days)
    _chmod_existing(log_dir)


def _purge_transcripts(log_dir: Path, retention_days: int) -> None:
    """Delete transcript-*.jsonl files older than retention_days."""
    cutoff = time.time() - retention_days * 86400
    purged = 0
    for f in log_dir.glob("transcript-*.jsonl"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                purged += 1
        except OSError:
            pass
    if purged:
        logger.info(f"[event_log] purged {purged} transcript(s) older than {retention_days}d")


def _chmod_existing(log_dir: Path) -> None:
    """Ensure existing log files are 600 (may be created before chmod was applied)."""
    for f in log_dir.glob("*"):
        if f.is_file():
            try:
                f.chmod(stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
