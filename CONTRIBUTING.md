# Contributing to Turtle AI

Thank you for your interest in turtle-ai! This is an open-source project of [Southeastern Reptile Conservation (SERC)](https://www.southeastreptile.org), a 501(c)(3) nonprofit in Hampton Roads, Virginia. Contributions from rehabbers, developers, zoo and wildlife-center staff, and anyone who cares about animal welfare are welcome.

## What turtle-ai is (and isn't)

turtle-ai is a "raise a hand when something looks wrong" detector for wildlife rehabilitation. It captures frames from RTSP cameras, analyzes them with a local vision model, and sends an alert when it sees signs of distress. It is **not** a census tool and never certifies that animals are healthy. See *Model Limitations* in [CLAUDE.md](CLAUDE.md) for measured accuracy caveats.

SERC runs it with 8 cameras covering both terrestrial and aquatic turtles, with a priority on threatened species. The code is designed to loop through any number of cameras and to work for many different species, enclosures, and organizations, from a single home rehabber to a large wildlife center.

## Design principles

Changes should preserve these goals:

- **Always local.** AI inference runs on the operator's own hardware. No images or data go to a cloud AI service. Docs, defaults, and examples must only point at local model servers.
- **Push only.** turtle-ai sends data out; nothing connects in. No feature should require an external service to call turtle-ai or to tunnel to it.
- **Free to run.** No API tokens, subscriptions, or per-inference costs.
- **Runs on modest hardware.** The production target is the best Gemma model that runs on a laptop, so the project stays accessible to small organizations. Larger models on bigger servers are supported but never required.
- **Open source.** MIT licensed.
- **Everything external is optional.** Alerts and the TurtleVision push can be turned off, and the system must work correctly with no outbound data at all. Operators working with threatened species may need that.
- **Generic code, specific prompts.** Species, enclosure types, and what to expect in each camera view belong in `scheduler/prompts.py`, which is the operator's customization point. Don't hardcode species or setup assumptions in code.

## Ways to contribute

- **Report bugs** and **suggest features** by opening a GitHub issue. Include your hardware, model, and server (Ollama, vLLM, etc.), plus relevant `docker compose logs`. Remove camera URLs, passwords, and API keys first.
- **Share prompts** that work for other species or enclosure types. Documenting what worked, and what the model got wrong, is valuable.
- **Report model results.** Notes on which models run well on which hardware help everyone.
- **Improve the docs.** Clearer setup steps for other camera brands, operating systems, and model servers are always welcome.
- **Send code.** Pull requests are welcome; for anything large, open an issue first so we can talk through the approach.

## Development setup

1. Install [Docker](https://docs.docker.com/get-docker/) with Compose v2, and a local model server with vision support (for example [Ollama](https://ollama.com/)):

   ```bash
   ollama pull gemma4:e4b
   ```

2. Fork and clone the repository.
3. Create a git-ignored `docker-compose.override.yml` with your camera URLs and settings. See the [README](README.md#4-configuration) and the full list of variables in `docker-compose.yml`.
4. Build and run:

   ```bash
   docker compose up --build
   ```

To run the services outside Docker, create a virtual environment and install `capture/requirements.txt` and `scheduler/requirements.txt`.

Never commit `docker-compose.override.yml`, camera URLs, Twilio credentials, ingest keys, or captured images.

## Pull request guidelines

- Keep changes focused. One concern per pull request.
- Explain what changed and why, and how you tested it. If you can't test with a real camera, say so.
- Update the README and the relevant docs when you add or change configuration.
- New settings should be environment variables with sensible defaults, documented in `docker-compose.yml`.
- Don't mount the Docker socket or add inbound dependencies.
- If you change `scheduler/prompts.py`, keep the "REPORT ONLY WHAT YOU CAN CLEARLY SEE" block. It stops the model from claiming animals are present, well, or absent when it can't tell.
- Habitat problems such as low water or dry substrate go in `warnings` and do not count as distress, so they never trigger alerts.

## About AI-assisted contributions

You're welcome to use AI tools. You are responsible for what you submit: read it, run it, and be able to explain it.

## Conduct

Be kind and respectful. This project exists to help animals and the people caring for them. Harassment and personal attacks aren't tolerated, and maintainers may remove comments or contributions that cross the line.

## License

By contributing, you agree that your contributions are licensed under the project's [MIT License](LICENSE).

## Questions

Open a GitHub issue, or reach SERC through [southeastreptile.org](https://www.southeastreptile.org).
