# Privacy Notice — Villa Eden Bleu Voice Concierge

This document describes what data the voice concierge records, where it is stored, and how it is handled. This is a demo/portfolio deployment — it is not a formal GDPR compliance document, but it reflects the actual system behaviour accurately.

---

## What is recorded

| Data | Recorded? | Notes |
|---|---|---|
| Your speech (audio) | **No** | Audio is processed in real time and never written to disk |
| Your speech converted to text (transcript) | **Yes** | Final transcription of what you said |
| Agent responses (text) | **Yes** | Text of what the agent said, reconstructed from streamed fragments |
| Booking details (name, email, dates, guests) | **Yes** | Included in the transcript when you provide them |
| Tool calls (availability checks, booking submission) | **Yes** | Logged as events (tool name, outcome — no audio, no personal data beyond what you provided) |
| Session events (connect, disconnect, duration, errors) | **Yes** | Operational log, no personal data |
| IP address | **No** | Not logged at application level (may appear in Traefik access logs, retained separately) |

---

## Where data is stored

- **Location**: Local files on the VPS (`/opt/apps/booking-concierge/var/logs/`), operated by the villa owner.
- **Format**: One JSONL file per session (role + text + timestamp), plus a rotating daily event log.
- **Access**: Files are `chmod 600` — readable only by the service account. Not accessible to third parties, not synced to cloud storage, not included in git.

---

## Why

- Debug and quality improvement for the voice concierge service.
- Backup of booking requests submitted through the agent.

---

## Data transfers outside the EU

By using this service, your voice and conversation data passes through two US-based processors:

1. **OpenAI (US)** — The OpenAI Realtime API processes your speech in real time (speech recognition + AI reasoning + speech synthesis). OpenAI's data processing is governed by their [privacy policy](https://openai.com/policies/privacy-policy) and API terms. Per OpenAI's API terms, data submitted via the API is not used to train models by default.

2. **Telegram (US)** — When a booking request is submitted, a notification including your name and email is sent to the villa owner via Telegram Bot API. Telegram's privacy policy applies.

No other third-party services receive your data.

---

## Retention

- Transcript files are automatically deleted after **30 days** (configurable via `LOG_RETENTION_DAYS`).
- Event logs are rotated daily and retained for the same period (managed by loguru).
- The daily purge runs via a systemd timer on the VPS (`booking-concierge-cleanup.timer`). A startup-time purge also runs each time the bot restarts, so the system works without systemd.

---

## Your rights

To request a copy of data recorded during your session, or to request deletion before the automatic retention period, contact:

**villaedenbleu@gmail.com**

Please include the approximate date and time of your call. Requests are processed within 30 days.

---

## What is NOT done

- No audio is stored at any point.
- No analytics or tracking platform (Google Analytics, Mixpanel, etc.) is used.
- Data is not sold or shared with third parties beyond OpenAI and Telegram as described above.
- Data is not used to train AI models (OpenAI API terms prohibit this by default).
