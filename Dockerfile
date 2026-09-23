# syntax=docker/dockerfile:1

FROM python:3.12-slim

ARG PIPER_VOICES_VERSION=v1.0.0

ENV PYTHONUNBUFFERED=1
ENV PIPER_HTTP_HOST=0.0.0.0
ENV PIPER_HTTP_PORT=8995
ENV PIPER_VOICE_DIR=/voices
ENV PIPER_PRELOAD_VOICE_DIR=/opt/piper/preloaded-voices
ENV PIPER_DEFAULT_VOICE=en_US-lessac-medium
ENV PIPER_TIMEOUT_SECONDS=60
ENV PIPER_OUTPUT_SAMPLE_RATE=0
ENV PATH="/opt/venv/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir "piper-tts"

RUN mkdir -p /opt/piper/preloaded-voices && \
    curl -fsSL "https://huggingface.co/rhasspy/piper-voices/resolve/${PIPER_VOICES_VERSION}/en/en_US/lessac/medium/en_US-lessac-medium.onnx" -o /opt/piper/preloaded-voices/en_US-lessac-medium.onnx && \
    curl -fsSL "https://huggingface.co/rhasspy/piper-voices/resolve/${PIPER_VOICES_VERSION}/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json" -o /opt/piper/preloaded-voices/en_US-lessac-medium.onnx.json && \
    curl -fsSL "https://huggingface.co/rhasspy/piper-voices/resolve/${PIPER_VOICES_VERSION}/en/en_US/ryan/medium/en_US-ryan-medium.onnx" -o /opt/piper/preloaded-voices/en_US-ryan-medium.onnx && \
    curl -fsSL "https://huggingface.co/rhasspy/piper-voices/resolve/${PIPER_VOICES_VERSION}/en/en_US/ryan/medium/en_US-ryan-medium.onnx.json" -o /opt/piper/preloaded-voices/en_US-ryan-medium.onnx.json

COPY docker/piper_http_server.py /usr/local/bin/piper-http-server.py
COPY docker/entrypoint.sh /usr/local/bin/opensim-piper-entrypoint.sh
RUN chmod +x /usr/local/bin/opensim-piper-entrypoint.sh

EXPOSE 8995/tcp

ENTRYPOINT ["/usr/local/bin/opensim-piper-entrypoint.sh"]
