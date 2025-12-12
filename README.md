# 🐢 Turtle AI — Smart Turtle Monitoring System

Turtle AI is an AI-powered wildlife monitoring system designed for rehabilitation environments. It runs locally, capturing snapshots from live RTSP camera feeds and using an open-source LLM (Gemma 3 via Ollama) to detect signs of turtles in distress. When distress is detected, it sends alerts via Twilio (SMS/WhatsApp).

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

Ensure Ollama is running and pull the model you intend to use. We recommend `gemma2` or `gemma:3n` depending on your hardware capabilities.

```bash
# Example: Pulling Gemma 2 (9B)
ollama pull gemma2

# Or Gemma 3n if available/preferred
ollama pull gemma:3n
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
      - CAMERA_URL=rtsp://username:password@192.168.1.x:554/stream

  scheduler:
    environment:
      - TWILIO_ACCOUNT_SID=your_sid_here
      - TWILIO_AUTH_TOKEN=your_auth_token_here
      - TWILIO_PHONE_NUMBER=+15551234567
      - RECIPIENT_PHONE_NUMBER=+15559876543
      - OLLAMA_MODEL=gemma2:latest  # Match the model you pulled
      - INTERVAL=10                 # Minutes between checks
```

> **Note:** If you are running Docker on Linux, you might need to adjust `OLLAMA_HOST` in `docker-compose.yml` to point to your host's IP address instead of `host.docker.internal`.

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

1. The **Scheduler** service waits for the configured `INTERVAL`.
2. It triggers the **Capture** service to grab a frame from the RTSP stream.
3. The image is saved to the shared `./images` directory.
4. The **Scheduler** sends the image to your local Ollama instance for analysis.
5. If the LLM detects "distress", a Twilio message is sent to your phone.

---

## 📷 System Architecture

<img width="756" height="424" alt="smart-monitoring" src="https://github.com/user-attachments/assets/faee898b-6529-4da9-8298-46bf6f5da0f0" />

## 📰 Presentation

Check out the project presentation at the TSA symposium on [YouTube](https://www.youtube.com/watch?v=VVEy0L_SDww&t=372s&ab_channel=ThePurringTurtle).
