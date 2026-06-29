"""
TranscriptObserver — per-session conversation transcript writer.

What is captured:
  - User speech → text:  TranscriptionFrame (final only, not interim),
    pushed UPSTREAM by OpenAIRealtimeLLMService when InputAudioTranscription()
    is enabled. Reliable, complete, timestamped.

  - Assistant speech → text: LLMTextFrame fragments, accumulated in memory.
    There is no BotTranscriptionFrame or assistant .done event in Pipecat 1.4.0
    with OpenAI Realtime. Fragments are flushed as one entry when:
      (a) the next user TranscriptionFrame arrives, OR
      (b) flush_pending() is called at session end.
    This means the assistant entry arrives with a slight delay (after the next
    user turn starts) and may occasionally be split if flush_pending() is the
    only trigger. The text content is correct; only the timing is approximate.

What is NOT captured:
  - Audio (never — no AudioRawFrame in the observer path)
  - Interim transcriptions (InterimTranscriptionFrame, separate class)
  - Tool call inputs/outputs (those are in the event log via loguru)

Output: var/logs/transcript-<session_id>.jsonl, one JSON object per line,
chmod 600. Toggle with env var TRANSCRIPT_LOGGING=1 (default) / =0.
"""

import asyncio
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from pipecat.frames.frames import LLMTextFrame, TranscriptionFrame
from pipecat.observers.base_observer import BaseObserver, FramePushed


class TranscriptObserver(BaseObserver):
    def __init__(self, session_id: str, log_dir: Path) -> None:
        self._enabled = os.getenv("TRANSCRIPT_LOGGING", "1") == "1"
        self._path = log_dir / f"transcript-{session_id}.jsonl"
        self._assistant_buf: list[str] = []
        self._lock = asyncio.Lock()
        if self._enabled:
            log_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"[transcript] Session {session_id} → {self._path}")

    async def on_push_frame(self, data: FramePushed) -> None:
        if not self._enabled:
            return
        frame = data.frame

        if isinstance(frame, TranscriptionFrame):
            # Flush any pending assistant text before writing the user turn.
            await self._flush_assistant()
            if frame.text and frame.text.strip():
                await self._write("user", frame.text.strip())

        elif isinstance(frame, LLMTextFrame):
            # Accumulate assistant text fragments — no end-of-turn signal exists.
            async with self._lock:
                self._assistant_buf.append(frame.text)

    async def flush_pending(self) -> None:
        """Call at session end to ensure last assistant turn is written."""
        await self._flush_assistant()

    async def _flush_assistant(self) -> None:
        async with self._lock:
            if not self._assistant_buf:
                return
            text = "".join(self._assistant_buf)
            self._assistant_buf.clear()
        if text.strip():
            await self._write("assistant", text.strip())

    async def _write(self, role: str, text: str) -> None:
        entry = json.dumps(
            {
                "role": role,
                "text": text,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        )
        # Await directly (no create_task) to preserve chronological order in file.
        # File write via to_thread is ~0.1 ms and does not block the event loop.
        await self._append_line(entry)

    async def _append_line(self, line: str) -> None:
        def _do() -> None:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            os.chmod(self._path, stat.S_IRUSR | stat.S_IWUSR)  # 600

        try:
            await asyncio.to_thread(_do)
        except Exception as exc:
            logger.error(f"[transcript] write failed: {exc}")
