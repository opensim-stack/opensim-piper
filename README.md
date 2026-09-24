# opensim-piper

[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-bithatch%2Fopensim--piper-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/r/bithatch/opensim-piper)
[![Docker Publish](https://github.com/opensim-stack/opensim-piper/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/opensim-stack/opensim-piper/actions/workflows/docker-publish.yml)

`opensim-piper` is a containerized HTTP wrapper for the [Piper](https://github.com/OHF-Voice/piper1-gpl) TTS engine.

It runs a lightweight web server in front of Piper so other services can request speech by HTTP.

*This is part of the [opensim-stack](https://opensim-stack.github.io/) and is intended to be used in conjunction with other parts of the stack. See [Docs](https://opensim-stack.github.io/docs/index.html) for full details.*

## What this image does

- Installs `piper-tts` and starts an HTTP server for synthesis requests
- Pre-installs two US English voices:
  - `en_US-lessac-medium` (female)
  - `en_US-ryan-medium` (male)
- Serves health and voice listing endpoints for easy wiring/debugging
- Uses environment variables for host, port, default voice, and timeout controls

## Runtime defaults

- `PIPER_HTTP_HOST=0.0.0.0`
- `PIPER_HTTP_PORT=8995`
- `PIPER_VOICE_DIR=/voices`
- `PIPER_DEFAULT_VOICE=en_US-lessac-medium`
- `PIPER_TIMEOUT_SECONDS=60`
- `PIPER_OUTPUT_SAMPLE_RATE=0` (`0` uses model default; set `48000` for 48 kHz output)

## Required volume mappings

- `piper-voices` -> `/voices` (recommended, for custom voices and persistence)

At startup, bundled default voices are copied into `/voices` if missing.

## Build local image

```bash
docker build -t opensim-piper:local .
```

## Run local image

```bash
docker run --rm \
  -e PIPER_HTTP_HOST=0.0.0.0 \
  -e PIPER_HTTP_PORT=8995 \
  -e PIPER_DEFAULT_VOICE=en_US-lessac-medium \
  -e PIPER_OUTPUT_SAMPLE_RATE=48000 \
  -p 8995:8995 \
  -v piper-voices:/voices \
  opensim-piper:local
```

## HTTP API quick reference

- `GET /health` basic status and loaded voices
- `GET /voices` list available voices and current default
- `POST /tts` (or `POST /v1/tts`) synthesize text, returns `audio/wav`
- Optional request field: `output_sample_rate` (integer, `0` for model default)

Response headers on `/tts`:

- `X-Audio-Sample-Rate` effective WAV sample rate returned
- `X-Audio-Source-Sample-Rate` Piper output sample rate before any wrapper resample
- `X-Audio-Resampled` `true` when the wrapper resampled PCM WAV to requested rate

Example request:

```bash
curl -sS -X POST "http://localhost:8995/tts" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello from OpenSim stack.","voice":"en_US-ryan-medium","output_sample_rate":48000}' \
  --output hello.wav
```

## Add a new voice model

1. Download both files for a Piper voice into your mounted `/voices` directory:
   - `<voice-name>.onnx`
   - `<voice-name>.onnx.json`
2. Set `PIPER_DEFAULT_VOICE=<voice-name>` if you want it as the default.
3. Restart the container, then verify with `GET /voices`.

Example (inside mounted voice directory):

```bash
curl -fsSLO "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/medium/en_GB-alan-medium.onnx"
curl -fsSLO "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json"
```

## Optional environment variables

- `PIPER_HTTP_HOST` HTTP bind host
- `PIPER_HTTP_PORT` HTTP bind port
- `PIPER_VOICE_DIR` voice model directory
- `PIPER_PRELOAD_VOICE_DIR` internal bundled voice directory used for first-run seeding
- `PIPER_DEFAULT_VOICE` default voice name (without `.onnx`) or absolute model path
- `PIPER_TIMEOUT_SECONDS` synthesis timeout
- `PIPER_OUTPUT_SAMPLE_RATE` default output sample rate (`0` keeps voice-model default)
- `PIPER_SERVER_EXTRA_ARGS` extra args passed to the Python HTTP server process

## Building and publishing

See `BUILDING.md` for local build/run steps, manual multiarch publish commands, and automated GitHub Actions publish details.