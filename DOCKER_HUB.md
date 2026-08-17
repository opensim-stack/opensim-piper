# opensim-piper

`opensim-piper` is a containerized Piper TTS image tailored for the OpenSim AI stack.

It is intended to be used as part of the **OpenSim Stack** project:
**"A docker stack to get an AI integrated virtual world up and running in minutes."**

## What This Image Does

- Runs an HTTP service for Piper text-to-speech requests
- Exposes API endpoints on container port `8995`
- Pre-installs two US English voices:
  - `en_US-lessac-medium` (female)
  - `en_US-ryan-medium` (male)
- Supports adding additional voices via mounted `/voices` directory

## Required Volume Mounts

- `piper-voices` -> `/voices`

Bundled default voices are seeded into `/voices` on startup when they are missing.

## Quick Start

```bash
docker run --rm \
  -e PIPER_HTTP_HOST=0.0.0.0 \
  -e PIPER_HTTP_PORT=8995 \
  -e PIPER_DEFAULT_VOICE=en_US-lessac-medium \
  -p 8995:8995 \
  -v piper-voices:/voices \
  bithatch/opensim-piper:latest
```

## Test Synthesis

```bash
curl -sS -X POST "http://localhost:8995/tts" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello from OpenSim stack."}' \
  --output hello.wav
```

## Project Links

- Main AI Stack (`opensim-ai-docker`): https://github.com/opensim-stack/opensim-ai-docker
- `opensim-piper` on GitHub: https://github.com/opensim-stack/opensim-piper
- Piper project: https://github.com/OHF-Voice/piper1-gpl
- Related services:
  - `opensim-console2mcp`: https://github.com/opensim-stack/opensim-console2mcp
  - `opensim-metaverse2mcp`: https://github.com/opensim-stack/opensim-metaverse2mcp
  - `opensim-opencode`: https://github.com/opensim-stack/opensim-opencode
