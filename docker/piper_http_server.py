#!/usr/bin/env python3
"""Small HTTP wrapper around Piper TTS CLI."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = os.environ.get("PIPER_HTTP_HOST", "0.0.0.0")
PORT = int(os.environ.get("PIPER_HTTP_PORT", "8995"))
VOICE_DIR = Path(os.environ.get("PIPER_VOICE_DIR", "/voices"))
DEFAULT_VOICE = os.environ.get("PIPER_DEFAULT_VOICE", "en_US-lessac-medium")
TIMEOUT_SECONDS = int(os.environ.get("PIPER_TIMEOUT_SECONDS", "60"))


def voice_model_path(voice: str) -> Path:
    """Resolve a voice name or path and constrain names to the voice directory."""
    candidate = Path(voice)
    if candidate.suffix == ".onnx" and candidate.is_absolute():
        return candidate

    # Voice names map to <voice>.onnx in configured voice directory.
    voice_name = candidate.name
    if voice_name.endswith(".onnx"):
        model_file = voice_name
    else:
        model_file = f"{voice_name}.onnx"
    return VOICE_DIR / model_file


def list_voices() -> list[str]:
    if not VOICE_DIR.exists():
        return []
    return sorted(p.stem for p in VOICE_DIR.glob("*.onnx"))


class PiperHandler(BaseHTTPRequestHandler):
    server_version = "opensim-piper/0.1"

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        data = self.rfile.read(content_length)
        if not data:
            return {}
        return json.loads(data.decode("utf-8"))

    def _not_found(self) -> None:
        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(
                {
                    "status": "ok",
                    "default_voice": DEFAULT_VOICE,
                    "voices": list_voices(),
                }
            )
            return

        if self.path == "/voices":
            self._send_json({"voices": list_voices(), "default_voice": DEFAULT_VOICE})
            return

        self._not_found()

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in ("/tts", "/v1/tts"):
            self._not_found()
            return

        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body"}, HTTPStatus.BAD_REQUEST)
            return

        text = str(payload.get("text", "")).strip()
        if not text:
            self._send_json({"error": "Missing required field: text"}, HTTPStatus.BAD_REQUEST)
            return

        voice = str(payload.get("voice", DEFAULT_VOICE)).strip() or DEFAULT_VOICE
        model_path = voice_model_path(voice)
        if not model_path.exists():
            self._send_json(
                {
                    "error": f"Voice model not found: {model_path}",
                    "available_voices": list_voices(),
                },
                HTTPStatus.BAD_REQUEST,
            )
            return

        cmd = ["piper", "--model", str(model_path)]

        for key, flag in (
            ("speaker", "--speaker"),
            ("length_scale", "--length_scale"),
            ("noise_scale", "--noise_scale"),
            ("noise_w", "--noise_w"),
            ("sentence_silence", "--sentence_silence"),
        ):
            value = payload.get(key)
            if value is not None:
                cmd.extend([flag, str(value)])

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="/tmp/piper-http") as wav_file:
            wav_path = Path(wav_file.name)

        cmd.extend(["--output_file", str(wav_path)])

        try:
            subprocess.run(
                cmd,
                check=True,
                input=text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=TIMEOUT_SECONDS,
            )
            audio = wav_path.read_bytes()
        except subprocess.TimeoutExpired:
            self._send_json({"error": "TTS request timed out"}, HTTPStatus.GATEWAY_TIMEOUT)
            return
        except subprocess.CalledProcessError as exc:
            self._send_json(
                {
                    "error": "Piper synthesis failed",
                    "details": exc.stderr.decode("utf-8", errors="replace"),
                },
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        finally:
            wav_path.unlink(missing_ok=True)

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)

    def log_message(self, fmt: str, *args) -> None:
        # Keep container logs compact but still useful for request debugging.
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")


def main() -> None:
    if not VOICE_DIR.exists():
        VOICE_DIR.mkdir(parents=True, exist_ok=True)

    server = ThreadingHTTPServer((HOST, PORT), PiperHandler)
    print(f"opensim-piper HTTP server listening on {HOST}:{PORT}")
    print(f"voice dir: {VOICE_DIR}")
    print(f"default voice: {DEFAULT_VOICE}")
    server.serve_forever()


if __name__ == "__main__":
    main()
