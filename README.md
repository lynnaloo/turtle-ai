# 🐢 Turtle AI — Smart Turtle Monitoring System

Turtle AI is an AI-powered wildlife monitoring system designed for rehabilitation environments. It runs locally, capturing snapshots from live RTSP camera feeds and using an open-source LLM (Gemma 4 via Ollama) to detect signs of turtles in distress. When distress is detected, it sends alerts via Twilio (SMS/WhatsApp).

---

## ✨ Features

- **Automated Monitoring**: Captures frames from RTSP-enabled cameras at configurable intervals.
- **AI Analysis**: Uses local LLMs (via Ollama) to analyze images for specific distress indicators:
  - Carapace-up positioning (flipped over)
  - Entrapment
  - Unusual inactivity
  - Aggressive interactions
- **Instant Alerts**: Sends notifications via Twilio when distress is detected.
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
      - OLLAMA_MODEL=gemma4:e4b    # Match the model you pulled
      - INTERVAL=10                 # Minutes between checks
      - CAPTURE_TIMEOUT=60          # Seconds to wait for a frame grab; raise for low-framerate cameras
      - LLM_TIMEOUT=120             # Seconds to wait for one Ollama analysis
      - API_KEY=                    # Optional: secures /scan, /image-analysis and /images
    volumes:
      - /your/local/path/images:/images
```

> **Note:** The volume path in `docker-compose.yml` is a placeholder — override it here with your actual local path. On Linux, you may also need to change `OLLAMA_HOST` from `host.docker.internal` to your host's IP address.

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
3. The **Scheduler** sends each image to your local Ollama instance for analysis.
4. If the LLM detects distress, a Twilio message is sent to your phone, naming the camera it was seen on.
5. You can also trigger an on-demand scan at any time via `POST http://localhost:5050/scan`.

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

## 📷 System Architecture

<img width="756" height="424" alt="smart-monitoring" src="https://github.com/user-attachments/assets/faee898b-6529-4da9-8298-46bf6f5da0f0" />

## 📰 Presentation

Check out the project presentation at the TSA symposium on [YouTube](https://www.youtube.com/watch?v=VVEy0L_SDww&t=372s&ab_channel=ThePurringTurtle).
