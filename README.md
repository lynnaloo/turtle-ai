# 🐢 Turtle AI — Smart Turtle Monitoring System

Turtle AI is an AI-powered wildlife monitoring system designed for rehabilitation environments. It captures snapshots from live RTSP camera feeds and uses a local LLM (Gemma via Ollama) to detect signs of turtles in distress. When distress is detected, it sends alerts via Twilio and displays messages in the web interface.

---

## 🔧 Setup & Installation

### Prerequisites

Twilio Account with:
- Account SID
- Auth Token

You must install the following before running this project:

- [Python 3.9+](https://www.python.org/downloads/)
- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2
- [FFmpeg](https://ffmpeg.org/download.html)
- [Ollama](https://ollama.com/) (must be running locally)
- Gemma 3n model installed:
  ```bash
  ollama run gemma:3n:e4b
  ```

### Installation

- Create a file named `docker-compose.override.yml` and add your specifiic environment variables (see docker-compose for format and examples)

```bash
git clone https://github.com/lynnaloo/turtle-ai.git
cd turtle-ai
```

---

## 🏃‍♀️ Run the Application

```bash
docker compose up --build
```

✔️ The app will now:

- Capture a frame from your RTSP camera every 10 minutes (or your custom interval)
- Analyze the image using Gemma via Ollama
- Alert you if a turtle appears distressed (via WhatsApp)

---

## 📷 System Architecture

<img width="756" height="424" alt="smart-monitoring" src="https://github.com/user-attachments/assets/faee898b-6529-4da9-8298-46bf6f5da0f0" />

## 📰 Presentation

Here is a [YouTube teaser](https://www.youtube.com/watch?v=OuIkNih7N2I&ab_channel=ThePurringTurtle) and demo of the project!
