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

- Cameras are configured via numbered env vars: `CAMERA_URL1`, `CAMERA_URL2`, etc. (both services need them)
- The shared volume path in `docker-compose.yml` is a placeholder (`/Users/username/...`) — override it with your actual local path in the override file

## Key Files

- `scheduler/prompts.py` — LLM prompt for turtle analysis; edit to tune detection behavior
- `scheduler/scheduler.py` — main orchestration loop; exposes Flask API on port 5050
- `capture/capture_image.py` — RTSP capture service
- `plan.md` — roadmap and planned features

## Distress Detection

The LLM returns JSON. An alert fires when the response contains `"turtle_well_being": "distressed"`.

## Scheduler API Endpoints

- `POST /scan` — on-demand capture + analysis across all cameras; returns per-camera JSON results; fires Twilio alerts if distress detected. Requires `X-API-Key` header when `API_KEY` env var is set.
- `GET /images/<filename>` — serve a captured image by filename from `HOST_IMAGE_DIR`; used by TurtleVision to display thumbnails. Requires `X-API-Key` header when `API_KEY` env var is set.
- `GET /image-analysis?image_path=...` — analyze a specific image file
- `GET /start-scheduler` — manually start the background scheduler loop (normally auto-starts on launch)
- `GET /health` — health check

## Roadmap

See `plan.md` for planned features including the web dashboard, MCP server integration, and future Nemotron video streaming upgrade.
