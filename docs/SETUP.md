# Setup — booking-concierge

Step-by-step walkthrough to run the voice concierge locally and deploy to VPS.

## 0. Overview

| System | Auth | Used for |
|---|---|---|
| OpenAI Realtime API | API Key | Speech-to-speech LLM (voice in, voice out) |
| Pipecat `SmallWebRTCTransport` | None (P2P) | Browser WebRTC audio transport |
| Google Sheets API | OAuth2 Desktop | Read availability calendar (Sprint 2) |
| Gmail API | OAuth2 Desktop | Send booking confirmation emails (Sprint 2) |
| Caddy | Basic Auth | HTTPS reverse proxy on VPS (Sprint 4) |

---

## 1. Prerequisites

- Python 3.11+
- Git
- A dedicated OpenAI API key **with a spend limit** (create at platform.openai.com → API keys)
- A modern browser with microphone access (Chrome or Firefox recommended)

---

## 2. Clone & virtualenv

```bash
git clone https://github.com/patw47/booking-concierge.git
cd booking-concierge
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Pipecat version pinned to 1.4.0.** Do not upgrade without testing audio quality.
> Versions 0.0.62 through 1.1.x have a known choppy/robotic audio regression
> with `SmallWebRTCTransport` (GitHub issue #1530, fixed in 1.2.0).

---

## 4. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in:
#   OPENAI_API_KEY=sk-...
```

---

## 5. Run locally

```bash
python bot.py --transport webrtc
```

Server starts at `http://localhost:7860`.
Open `http://localhost:7860/client/` (prebuilt Pipecat UI) **or** open `frontend/index.html`
directly in a browser (custom branded page).

> **Microphone permission**: browser will prompt on first connect. Allow it.

---

## 6. Test the audio loop

1. Open `http://localhost:7860/client/`
2. Click **Connect**
3. Speak — the bot should greet you and respond in real time
4. Verify: no robotic artifacts, no audio cutoffs, natural turn-taking

If audio is choppy, check `OPENAI_API_KEY` is valid and the model is `gpt-realtime-2`
(default since Pipecat 1.2.0). Do not downgrade Pipecat below 1.2.0.

---

## 7. Google Sheets & Gmail setup (Sprint 2)

_To be completed in Sprint 2._

Steps will cover:
- Creating a Google Cloud project (no billing required for Sheets + Gmail)
- OAuth2 Desktop client credentials
- Running the authorization flow once to generate `token.json`
- Setting `GOOGLE_SHEET_ID` and `GMAIL_SENDER` in `.env`

---

## 8. VPS deployment (Sprint 4)

_To be completed in Sprint 4._

Steps will cover:
- `rsync` + `deploy/remote.sh`
- `systemctl enable booking-concierge`
- Caddy config (`deploy/Caddyfile`) with TLS auto + Basic Auth
- Session timeout and spend limit guard-rails

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: pipecat` | venv not activated | `source .venv/bin/activate` |
| `OpenAIRealtimeBetaLLMService` import error | Old example / tutorial code | Use `OpenAIRealtimeLLMService` from `pipecat.services.openai.realtime.llm` |
| Robotic / choppy audio | Pipecat < 1.2.0 | Pin to 1.4.0 (`pip install "pipecat-ai[webrtc,runner]==1.4.0"`) |
| Double responses / missed turns | `realtime_service_mode` missing | Ensure `LLMContextAggregatorPair(..., realtime_service_mode=True)` |
| Browser no audio output | Microphone permission denied | Allow mic in browser; reload page |
| `409 Conflict` on WebRTC offer | Two bots running on same port | Kill other process: `lsof -ti:7860 \| xargs kill` |
