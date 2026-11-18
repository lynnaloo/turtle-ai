# 🐢 Turtle AI — Smart Turtle Monitoring System

Turtle AI is an AI-powered wildlife monitoring system designed for rehabilitation environments. It runs locally, capturing snapshots from live RTSP camera feeds and using an open-source LLM (Gemma 4 via Ollama) to detect signs of turtles in distress. When distress is detected, it sends alerts via Twilio (SMS/WhatsApp).

A project of [Southeastern Reptile Conservation (SERC)](https://www.southeastreptile.org) — a 501(c)(3) nonprofit in Hampton Roads, Virginia.

---

## ✨ Features

- **Automated Monitoring**: Captures frames from RTSP-enabled cameras at configurable intervals.
- **AI Analysis**: Uses local LLMs (via Ollama) to analyze images for specific distress indicators:
  - Carapace-up positioning (flipped over)
  - Entrapment
  - Unusual inactivity
  - Aggressive interactions
- **Instant Alerts**: Sends notifications via Twilio when distress is detected.
- **Optional Visual Portal**: Partners who want a dashboard can enable an outbound push to [TurtleVision](#-turtlevision-dashboard-optional). Nothing is sent unless you configure it, so fully on-premises setups are unaffected.
- **Privacy First**: All processing happens locally on your machine; images are not sent to the cloud for analysis.

---

## 🔧 Setup & Installation

### Prerequisites

1. **Hardware**:
   - An RTSP-enabled camera (e.g., [Ubiquity](https://ui.com/physical-security/special-devices/compact-cameras)).
   - A computer capable of running Docker and Ollama (with sufficient RAM for the LLM).

2. **Software**:
   - [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2
   - [Ollama](https://ollama.com/) (must be running locally on the host)

3. **Services**:
   - **Twilio Account**: You need an Account SID, Auth Token, and a sender phone number.

### 1. Prepare the AI Model

Ensure Ollama is running and pull the model you intend to use. We recommend `gemma4:e4b` as a good balance of performance and hardware requirements.

```bash
ollama pull gemma4:e4b
```

#### Using a different model server

turtle-ai talks to the model through the standard **OpenAI chat-completions API** (with image input), so it isn't tied to Ollama. Point `LLM_BASE_URL` at any compatible server that runs a vision model — LM Studio, vLLM, llama.cpp's server, LocalAI, and so on — and set `LLM_MODEL` to the name that server uses. `LLM_API_KEY` is only needed if your server requires one.

#### Linux hosts and vLLM

On Linux, Docker doesn't define `host.docker.internal` for you. Add it to the `scheduler` service in your override so the container can reach a model server running on the host:

```yaml
  scheduler:
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - LLM_BASE_URL=http://host.docker.internal:8000/v1   # your vLLM port
      - LLM_MODEL=your-served-model-name                    # vLLM's --served-model-name
```

[vLLM](https://docs.vllm.ai/) works as-is: start it with a vision-capable model and a `--served-model-name` (for example `vllm serve <your-vision-model> --served-model-name my-vision-model`), then set `LLM_MODEL` to that served name. If the server runs on a different machine, use its address in `LLM_BASE_URL` instead.

For a long-running server install, also set `restart: unless-stopped` on both services, and bind the ports to localhost (`ports: !override` with `"127.0.0.1:5050:5000"`) since turtle-ai only pushes data out and never needs inbound access.

> **Ollama context size:** Ollama's OpenAI endpoint can't set the context window per request, and its default may be too small for the prompt plus an image. If analyses come back empty or truncated, start Ollama with a larger window, e.g. `OLLAMA_CONTEXT_LENGTH=10000 ollama serve`.

> **Upgrading:** `OLLAMA_HOST` and `OLLAMA_MODEL` are replaced by `LLM_BASE_URL` (note the `/v1` suffix) and `LLM_MODEL`.

### 2. Clone the Repository

```bash
git clone https://github.com/lynnaloo/turtle-ai.git
cd turtle-ai
```

### 3. Set up Virtual Environment (Optional)

If you plan to run scripts locally or contribute to development, it's recommended to use a virtual environment:

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r capture/requirements.txt
pip install -r scheduler/requirements.txt
```

### 4. Configuration

Create a `docker-compose.override.yml` file in the root directory to set your private environment variables. This file is git-ignored and will override the defaults in `docker-compose.yml`.

**`docker-compose.override.yml` example:**

```yaml
services:
  capture:
    environment:
      - CAMERA_URL1=rtsp://username:password@192.168.1.x:554/stream
      - CAMERA_URL2=rtsp://username:password@192.168.1.y:554/stream  # add more as needed
    volumes:
      - /your/local/path/images:/images

  scheduler:
    environment:
      - CAMERA_URL1=rtsp://username:password@192.168.1.x:554/stream
      - CAMERA_URL2=rtsp://username:password@192.168.1.y:554/stream
      - TWILIO_ACCOUNT_SID=your_sid_here
      - TWILIO_AUTH_TOKEN=your_auth_token_here
      - TWILIO_PHONE_NUMBER=+15551234567
      - RECIPIENT_PHONE_NUMBER=+15559876543
      - LLM_BASE_URL=http://host.docker.internal:11434/v1  # Any OpenAI-compatible endpoint
      - LLM_MODEL=gemma4:e4b       # Match the model your server has loaded
      - INTERVAL=10                 # Minutes between checks
      - CAPTURE_TIMEOUT=60          # Seconds to wait for a frame grab; raise for low-framerate cameras
      - LLM_TIMEOUT=120             # Seconds to wait for one analysis
      - API_KEY=                    # Optional: secures /scan, /image-analysis and /images
    volumes:
      - /your/local/path/images:/images
```

> **Note:** The volume path in `docker-compose.yml` is a placeholder — override it here with your actual local path. On Linux, see [Linux hosts and vLLM](#linux-hosts-and-vllm) for reaching a model server on the host.

---

## 🏃‍♀️ Run the Application

Start the system with Docker Compose:

```bash
docker compose up --build
```

To view logs and see what's happening:

```bash
docker compose logs -f
```

### What happens next?

1. The **Scheduler** starts immediately, triggers the **Capture** service to grab a frame from each RTSP stream, then sleeps for the configured `INTERVAL`.
2. Each captured image is saved to the shared `./images` directory.
3. The **Scheduler** sends each image to your local model server (Ollama by default) for analysis.
4. If the LLM detects distress, a Twilio message is sent to your phone, naming the camera it was seen on.
5. You can also trigger a manual scan at any time from the machine running turtle-ai via `POST http://localhost:5050/scan`.

> **Sizing `INTERVAL`:** cameras are analyzed one at a time, and a single analysis typically takes
> 30–40 seconds on modest hardware. Eight cameras is therefore a ~5 minute sweep. Keep `INTERVAL`
> comfortably longer than one full sweep, or the next cycle starts while the previous one is still
> running.

---

## 🛠 Troubleshooting

### Testing Camera Feed

If you are unsure if your `CAMERA_URL` is correct, you can test it using `ffmpeg`.

> **UniFi Protect users:** The URL shown in the UniFi console looks like
> `rtsps://192.168.1.1:7441/kBCncnfNOsSzkrgM?enableSrtp`. Keep the `rtsps://` scheme — port
> **7441 is TLS-only**, so `rtsp://...:7441/...` fails with
> `Failed reading RTSP data: End of file`. The `?enableSrtp` suffix is optional and can be dropped:
>
> - `rtsps://192.168.1.1:7441/kBCncnfNOsSzkrgM` ✅
> - `rtsp://192.168.1.1:7447/kBCncnfNOsSzkrgM` ✅ (plain RTSP lives on port 7447)
> - `rtsp://192.168.1.1:7441/kBCncnfNOsSzkrgM` ❌ scheme/port mismatch

**Option 1: Using Docker (Recommended)**
Run this command to attempt a capture from inside the container (replace the URL with your actual RTSP URL):

```bash
docker compose exec capture ffmpeg -rtsp_transport tcp -i "rtsp://192.168.1.x:554/stream" -vframes 1 -q:v 2 /images/test_manual.jpg
```

Check the `images/` folder for `test_manual.jpg`.

**Option 2: Running Locally**
If you have `ffmpeg` installed on your machine:

```bash
ffmpeg -rtsp_transport tcp -i "rtsp://192.168.1.x:554/stream" -vframes 1 -q:v 2 test_manual.jpg
```

### `Unrecognized option 'stimeout'`

If every capture fails instantly with this in the `capture` logs:

```
Unrecognized option 'stimeout'.
Error splitting the argument list: Option not found
```

…the RTSP socket timeout is being passed under its pre-ffmpeg-5.0 name. It was renamed to plain
`-timeout` (still in microseconds), which is what `capture/capture_image.py` uses. Most RTSP guides
online still show `-stimeout`, so it is an easy one to reintroduce by copy-paste. Check your image's
version with `docker compose exec capture ffmpeg -version`, and confirm which options that build
actually accepts with:

```bash
docker compose exec capture ffmpeg -hide_banner -h demuxer=rtsp | grep -i timeout
```

---

## 📊 TurtleVision Dashboard (Optional)

turtle-ai can push scan results and captured images to [TurtleVision](https://turtlevision.org), a web dashboard built by SERC that shows the live state of your enclosures and keeps a scan history. This is entirely optional and intended for partners who want a visual portal — turtle-ai runs fine without it, sending only Twilio alerts.

To enable the push, set these three variables in your `docker-compose.override.yml`:

```yaml
  scheduler:
    environment:
      - TURTLEVISION_ENABLED=true
      - TURTLEVISION_WEBHOOK_URL=https://turtlevision.org/api/ingest
      - TURTLEVISION_INGEST_KEY=your_ingest_key_here
```

To disable it, set `TURTLEVISION_ENABLED=false` (or simply leave `TURTLEVISION_WEBHOOK_URL` blank — no push will happen either way).

> **Privacy note:** Some rehabilitators work with endangered or sensitive species and should not expose animal locations or images to any external service. If that applies to you, leave `TURTLEVISION_ENABLED=false`. All analysis stays on-device; only Twilio alerts leave your network.

---

## 📷 System Architecture

![Turtle AI architecture: cameras feed the capture service, the scheduler sends frames to the local model, and distress triggers a Twilio alert](docs/architecture.png)

## 🤝 Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## 📰 Presentation

Check out the project presentation at the TSA symposium on [YouTube](https://www.youtube.com/watch?v=VVEy0L_SDww&t=372s&ab_channel=ThePurringTurtle).
