# booking-concierge

**Voice concierge agent for Villa Eden Bleu** — a portfolio demo of a real-time voice AI
for a holiday rental. A visitor opens a password-protected HTTPS link, speaks to the agent
in English, asks about the villa and availability, and books a stay.

Built with [Pipecat](https://github.com/pipecat-ai/pipecat) · OpenAI Realtime API · SmallWebRTCTransport · Google Sheets · Gmail

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
                        (Google Sheet read)         (Sheet write + Gmail)
                              │                              │
                         availability               booking request row
                           answer                    + confirmation email
```

---

## Stack

| Component | Role |
|---|---|
| `pipecat-ai 1.4.0` | Real-time audio pipeline orchestration |
| `SmallWebRTCTransport` | Browser P2P WebRTC (no key, no 3rd-party relay) |
| OpenAI Realtime API (`gpt-realtime-2`) | Speech-to-speech LLM + function calling |
| Google Sheets API | Availability calendar + booking log |
| Gmail API | Booking confirmation email |
| Caddy | HTTPS reverse proxy + Basic Auth on VPS |
| systemd | Process supervision on VPS |

---

## Project structure

```
booking-concierge/
├── bot.py                  # Pipecat pipeline entry point
├── prompts/
│   ├── system_en.md        # Villa knowledge prompt (English)
│   └── system_fr.md        # Villa knowledge prompt (French)
├── flows/
│   └── booking_flow.py     # State machine (Sprint 3)
├── tools/
│   ├── disponibilites.py   # get_disponibilites → Google Sheet
│   └── reservation.py      # creer_reservation → Sheet + Gmail
├── frontend/
│   └── index.html          # Branded "Talk to the concierge" page
├── deploy/
│   ├── remote.sh           # Idempotent VPS deploy script
│   ├── booking-concierge.service  # systemd unit
│   └── Caddyfile           # HTTPS + Basic Auth
├── docs/
│   └── SETUP.md            # Tutorial-grade setup guide
├── requirements.txt
├── .env.example
└── README.md
```

---

## Services

| Service | Role | Port |
|---|---|---|
| `booking-concierge` | Pipecat bot + FastAPI signaling server | 7861 (VPS) / 7860 (local) |
| Caddy | TLS termination + Basic Auth | 443 |

```bash
systemctl status booking-concierge
systemctl restart booking-concierge
```

---

## Setup

See [docs/SETUP.md](docs/SETUP.md) for the full tutorial. Quick start:

```bash
git clone https://github.com/patw47/booking-concierge.git && cd booking-concierge
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in OPENAI_API_KEY
python bot.py --transport webrtc
# Open http://localhost:7860/client/
```

---

## Environment variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Dedicated demo key — set a spend limit at platform.openai.com |
| `GOOGLE_SHEET_ID` | ID of the Villa Eden Bleu calendar sheet (Sprint 2) |
| `GOOGLE_CREDENTIALS_FILE` | Path to OAuth2 Desktop client JSON (Sprint 2) |
| `GMAIL_SENDER` | Gmail address for booking confirmations (Sprint 2) |
| `SESSION_TIMEOUT_SECS` | Max session length in seconds (default 300) |

---

## Rules

- **One concurrent session max** in demo mode — no multi-tenant load balancing.
- **Dedicated API key with spend limit** — never share the production key.
- `.env` is git-ignored. Never commit secrets.
- Pipecat version is **pinned to 1.4.0** — do not upgrade without ear-testing audio quality.
- All business logic lives in `tools/` — `bot.py` stays pipeline-only.

---

## Deployment

Sprint 4 will wire up the VPS deploy. The flow mirrors `property-cm`:

```bash
rsync -az . acer@vps:/opt/apps/booking-concierge/
ssh acer@vps "bash /opt/apps/booking-concierge/deploy/remote.sh"
```

---

## License

MIT © 2026 Patricia Wintrebert
