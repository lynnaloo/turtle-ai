# Turtle AI — Project Plan

## In Progress

### On-Demand Scan API
Make the scheduler externally callable so web frontends and other agents can trigger a capture + analysis cycle and receive structured results.

**What was added:**
- `POST /scan` endpoint on the scheduler service (port 5050) — triggers capture across all configured cameras, runs LLM analysis on each, fires Twilio alerts for any distress detected, and returns a JSON response
- CORS enabled globally so browser-based frontends can call the API directly
- Optional API key auth via `X-API-Key` request header — set `API_KEY` in `docker-compose.override.yml` to enable

**Response shape:**
```json
{
  "cameras": [
    {
      "camera_index": 1,
      "camera_url": "rtsp://...",
      "image_path": "/images/...",
      "analysis": {
        "turtles_visible": 0,
        "turtle_well_being": "good" | "distressed",
        "carapace_up": true | false,
        "plastron_visible": true | false,
        "entrapment": true | false,
        "unusual_inactivity": true | false,
        "aggressive_interactions": true | false,
        "eggs_present": true | false,
        "warnings": ["..."],
        "additional_notes": "..."
      },
      "alert_sent": true | false,
      "error": null | "message"
    }
  ]
}
```

**Example call:**
```bash
curl -X POST http://localhost:5050/scan \
  -H "X-API-Key: your_key_here"
```

### TurtleVision Push
After every scan — scheduled or on-demand — the scheduler pushes results outbound to the TurtleVision
dashboard, preserving the push-only principle: nothing tunnels back in.

**What was added:**
- `push_to_turtlevision()` in `scheduler/scheduler.py`, called at the end of each scan
- Sends `{scannedAt, cameras[]}` with each camera's analysis, plus the captured frame resized and
  encoded inline so the dashboard can show thumbnails without reaching back into turtle-ai
- Authenticated with an `X-Ingest-Key` header — set `TURTLEVISION_WEBHOOK_URL` and
  `TURTLEVISION_INGEST_KEY` to enable; leave either unset and the push is skipped entirely
- Fire-and-forget: a dashboard outage logs a warning and never interrupts the scan loop

Alternatively the dashboard can pull on demand via `POST /scan` and fetch frames from
`GET /images/<filename>`, both gated by `API_KEY`.

---

## Planned

### Web Dashboard — Remaining Work
The ingest path and image display are done (above). Still open:

- Visual treatment of distress indicators (flipped, entrapment, inactivity) rather than raw JSON
- Surfacing the advisory `warnings` array — habitat issues that are worth a caregiver's attention
  but deliberately do not trigger a Twilio alert
- Showing `turtles_visible`, so an empty bin reads as "nothing to monitor" rather than looking
  identical to an occupied bin that is doing fine
- History/trend view across scans, so gradual changes are visible

### MCP Server (Multi-Agent Use)
Wrap the scheduler as an [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server so other AI agents can call `scan_cameras` as a native tool.

- Exposes `scan_cameras` as an MCP tool backed by `POST /scan`
- Lets Claude agents (or any MCP-compatible agent) trigger scans, receive structured results, and act on them — e.g., escalate alerts, log to a database, notify a vet
- Most future-proof path for agent-to-agent integration as the ecosystem matures

### Native Video Streaming (Nemotron-3-Nano Omni)
Once Ollama (or an equivalent local runtime) supports true streaming video input — not just frame-by-frame images — migrate to [NVIDIA Nemotron-3-Nano Omni](https://blogs.nvidia.com/blog/nemotron-3-nano-omni-multimodal-ai-agents/).

**Why this model:**
- Native multimodal support: video, audio, images, and text in one model
- 33B MoE architecture with Conv3D — understands motion and temporal behavior across a clip
- Can detect subtler distress: unusual stillness over time, abnormal swimming patterns, behavioral changes
- Audio input could monitor tank environment (splashing, impact sounds)
- Available as open weights on Hugging Face and via Ollama (`nemotron3`)

**Blocker:** Ollama must support native video clip input (not just image frames). The model itself is available now — the runtime support is the missing piece.

**When ready:**
- Update `capture/capture_image.py` to record short video clips (10–30s) instead of stills
- Update `scheduler/scheduler.py` to pass clips to the LLM
- Set `OLLAMA_MODEL=nemotron3` — requires ~20 GB VRAM; NVIDIA GPU recommended for good performance (hardware is available)
