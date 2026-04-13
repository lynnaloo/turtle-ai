# Turtle AI

AI-powered turtle rehabilitation monitor. Captures RTSP camera frames, analyzes them locally with Ollama, and sends Twilio SMS/WhatsApp alerts when turtle distress is detected.

## Services

Two Docker microservices sharing an `/images` volume:
- **capture** (port 5001) — grabs frames from RTSP streams via FFmpeg
- **scheduler** (port 5050) — runs on a timer, triggers captures, runs LLM analysis, sends alerts

Ollama runs on the **host machine**, not in Docker.

## Running

```bash
ollama pull gemma4:e4b     # pull model first
docker compose up --build
```

Configuration lives in a git-ignored `docker-compose.override.yml` — see `docker-compose.yml` for the full list of env vars (camera URLs, Twilio credentials, Ollama model, interval).

## Key Files

- `scheduler/prompts.py` — LLM prompt for turtle analysis; edit to tune detection behavior
- `scheduler/scheduler.py` — main orchestration loop
- `capture/capture_image.py` — RTSP capture service

## Distress Detection

The LLM returns JSON. An alert fires when the response contains `"turtle_well_being": "distressed"`.
