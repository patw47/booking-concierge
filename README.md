# booking-concierge

**Voice concierge agent for Villa Eden Bleu** — a portfolio demo of a real-time voice AI
for a holiday rental. A visitor opens a password-protected HTTPS link, speaks to the agent
in English or French, asks about the villa and availability, and submits a booking request.

Built with [Pipecat](https://github.com/pipecat-ai/pipecat) · OpenAI Realtime API · SmallWebRTCTransport · Google Sheets · Telegram

---

## How it works

```
Browser mic ──► SmallWebRTCTransport ──► Pipecat Pipeline
                                              │
                                    OpenAI Realtime API
                                    (speech → reason → speech)
                                              │
                              ┌───────────────┴──────────────┐
                        get_disponibilites            creer_reservation
                        (Google Sheet read)         (Telegram notification)
                              │                              │
                         availability               booking request sent
                           answer                  to owner via Telegram
```

---

## Stack

| Component | Role |
|---|---|
| `pipecat-ai 1.4.0` | Real-time audio pipeline orchestration |
| `SmallWebRTCTransport` | Browser P2P WebRTC (no key, no 3rd-party relay) |
| OpenAI Realtime API | Speech-to-speech LLM + function calling |
| Google Sheets API | Availability calendar (read-only) |
| Telegram Bot API | Booking request notification to owner |
| Traefik v3 | HTTPS reverse proxy + Basic Auth on VPS |
| systemd | Process supervision on VPS |

---

## Project structure

```
booking-concierge/
├── bot.py                  # Pipecat pipeline entry point + FastAPI routes
├── transcript_observer.py  # Per-session conversation transcript (BaseObserver)
├── event_logger.py         # Loguru file sink + startup log purge
├── prompts/
│   ├── system_en.md        # Villa knowledge prompt (English)
│   └── system_fr.md        # Villa knowledge prompt (French)
├── flows/
│   └── booking_flow.py     # State machine — language switch + flow tools
├── tools/
│   ├── disponibilites.py   # get_disponibilites → Google Sheet read
│   └── reservation.py      # creer_reservation → Telegram notification
├── frontend/
│   └── index.html          # Branded "Talk to the concierge" page
├── deploy/
│   ├── remote.sh                           # Idempotent VPS deploy script
│   ├── booking-concierge.service           # systemd unit
│   ├── traefik-booking-concierge.yml       # Traefik dynamic config (HTTPS + BasicAuth)
│   ├── booking-concierge-cleanup.service   # systemd service for log purge
│   ├── booking-concierge-cleanup.timer     # systemd daily timer for log purge
│   ├── cleanup_logs.sh                     # Log purge script
│   └── coturn.conf                         # coturn template (optional, for strict NAT)
├── var/logs/               # Runtime logs — gitignored, chmod 600
├── PRIVACY.md              # What is recorded and where
├── requirements.txt
├── .env.example
└── README.md
```

---

## Services

| Service | Role | Port |
|---|---|---|
| `booking-concierge` | Pipecat bot + FastAPI signaling server | 7861 (VPS) / 7860 (local) |
| Traefik | TLS termination + Basic Auth | 443 |

```bash
systemctl status booking-concierge
journalctl -u booking-concierge -f
```

---

## Setup

Quick start (local dev):

```bash
git clone https://github.com/patw47/booking-concierge.git && cd booking-concierge
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in OPENAI_API_KEY, GOOGLE_SHEET_ID, TELEGRAM_*
python bot.py --transport webrtc
# Open http://localhost:7860
```

VPS deploy:
```bash
ssh hetzner-vps "bash /opt/apps/booking-concierge/deploy/remote.sh"
```

---

## Environment variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Dedicated demo key — set a spend limit at platform.openai.com |
| `GOOGLE_SHEET_ID` | ID of the Villa Eden Bleu calendar sheet |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to Google service account JSON key (gitignored) |
| `TELEGRAM_TOKEN` | Telegram bot token for booking notifications |
| `TELEGRAM_CHAT_ID` | Telegram chat ID to send booking requests to |
| `SESSION_TIMEOUT_SECS` | Max idle session length in seconds (default 180) |
| `TRANSCRIPT_LOGGING` | Set to `0` to disable transcript JSONL files (default `1`) |
| `LOG_RETENTION_DAYS` | Days before logs are auto-purged (default `30`) |
| `STUN_SERVER` | STUN server for WebRTC (default: Google STUN) |
| `TURN_HOST` | Optional TURN server host for strict NAT / 4G |

---

## Privacy & Logging

The agent logs conversation transcripts (text only — no audio) and session events to local files in `var/logs/` (gitignored, `chmod 600`). See [PRIVACY.md](PRIVACY.md) for full details.

Key facts:
- **Audio is never stored.**
- Speech recognition and AI reasoning go through **OpenAI (US)** via the Realtime API.
- Booking notifications are sent via **Telegram (US)**.
- Transcripts are auto-deleted after `LOG_RETENTION_DAYS` days (default 30).
- Disable transcript files: set `TRANSCRIPT_LOGGING=0` in `.env`.

---

## Rules

- **One concurrent session max** in demo mode — no multi-tenant load balancing.
- **Dedicated API key with spend limit** — never share the production key.
- `.env` is git-ignored. Never commit secrets.
- Pipecat version is **pinned to 1.4.0** — do not upgrade without ear-testing audio quality.
- Business logic in `tools/` — `bot.py` stays pipeline-only.

---

## License

MIT © 2026 Patricia Wintrebert
