# Turtle AI

AI-powered turtle rehabilitation monitor. Captures RTSP camera frames, analyzes them locally with Ollama, and sends Twilio SMS/WhatsApp alerts when turtle distress is detected.

## Core Principles

These goals are non-negotiable and must be preserved in all future development:

- **Always local** — AI inference runs on the user's own hardware via Ollama. No images or data are ever sent to a cloud AI service or third-party datacenter for analysis.
- **Push only, never pull** — turtle-ai pushes data outbound (scan results, images) to dashboards or other services. External services cannot tunnel into or call turtle-ai. There are no inbound API dependencies.
- **Free to run** — no API tokens, no subscriptions, no per-inference cost. Users pay only for their own hardware and internet.
- **Runs on modest hardware** — designed to work on a MacBook or similar consumer hardware using small efficient models (e.g. `gemma4:e4b`). Larger models on beefier hardware are supported but never required.
- **Always open-source** — MIT licensed and free to use, modify, and self-host. Accessibility to small nonprofits is a design constraint, not an afterthought.

## Services

Two Docker microservices sharing an `/images` volume:
- **capture** (port 5001) — grabs frames from RTSP streams via FFmpeg
- **scheduler** (port 5050) — runs on a timer, triggers captures, runs LLM analysis, sends alerts

Ollama runs on the **host machine**, not in Docker.

Neither service needs the Docker socket — they talk to each other over the Compose network, so do
not mount `/var/run/docker.sock` or install `docker.io` into the images.

## Running

```bash
ollama pull gemma4:e4b     # pull model first
docker compose up --build
```

Configuration lives in a git-ignored `docker-compose.override.yml` — see `docker-compose.yml` for the full list of env vars (camera URLs, Twilio credentials, Ollama model, interval).

- Cameras are configured via numbered env vars: `CAMERA_URL1`, `CAMERA_URL2`, etc. (both services need them)
- The shared volume path in `docker-compose.yml` is a placeholder (`/Users/username/...`) — override it with your actual local path in the override file

## Timeouts

Three nested timeouts guard the pipeline; each must stay below the one that wraps it, or the outer
layer gives up before the inner one can report a useful failure:

| Setting | Default | Where | Guards |
|---|---|---|---|
| `RTSP_TIMEOUT` | 20s | constant in `capture/capture_image.py` | ffmpeg socket inactivity on one RTSP grab |
| `CAPTURE_TIMEOUT` | 60s | env var | scheduler's HTTP call to the capture service |
| `LLM_TIMEOUT` | 120s | env var | one Ollama analysis call |

`RTSP_TIMEOUT` is passed to ffmpeg as `-timeout` (microseconds). It was named `-stimeout` before
ffmpeg 5.0 — most RTSP examples online still show the old name, which errors out with
`Unrecognized option 'stimeout'` on modern builds.

## Key Files

- `scheduler/prompts.py` — LLM prompt for turtle analysis; edit to tune detection behavior
- `scheduler/scheduler.py` — main orchestration loop; exposes Flask API on port 5050
- `capture/capture_image.py` — RTSP capture service
- `plan.md` — roadmap and planned features

## Distress Detection

The LLM returns JSON. An alert fires when the response contains `"turtle_well_being": "distressed"`.

Habitat problems (low water, dry substrate, etc.) are deliberately *not* distress. They go into the
`warnings` array and leave the status `"good"`, so they never fire a Twilio alert — see
`scheduler/prompts.py`. Alert texts include the camera number the distress was seen on.

## Scheduler API Endpoints

- `POST /scan` — on-demand capture + analysis across all cameras; returns per-camera JSON results; fires Twilio alerts if distress detected. Requires `X-API-Key` header when `API_KEY` env var is set.
- `GET /images/<filename>` — serve a captured image by filename from `HOST_IMAGE_DIR`; used by TurtleVision to display thumbnails. Requires `X-API-Key` header when `API_KEY` env var is set.
- `GET /image-analysis?image_path=...` — analyze a specific image file. Requires `X-API-Key` header when `API_KEY` env var is set.
- `GET /start-scheduler` — manually start the background scheduler loop (normally auto-starts on launch)
- `GET /health` — health check

## Roadmap

See `plan.md` for planned features including the web dashboard, MCP server integration, and future Nemotron video streaming upgrade.
