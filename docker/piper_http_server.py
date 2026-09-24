#!/usr/bin/env python3
"""Small HTTP wrapper around Piper TTS CLI."""

from __future__ import annotations

import audioop
import io
import json
import os
import subprocess
import tempfile
import wave
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = os.environ.get("PIPER_HTTP_HOST", "0.0.0.0")
PORT = int(os.environ.get("PIPER_HTTP_PORT", "8995"))
VOICE_DIR = Path(os.environ.get("PIPER_VOICE_DIR", "/voices"))
DEFAULT_VOICE = os.environ.get("PIPER_DEFAULT_VOICE", "en_US-lessac-medium")
TIMEOUT_SECONDS = int(os.environ.get("PIPER_TIMEOUT_SECONDS", "60"))
DEFAULT_OUTPUT_SAMPLE_RATE = int(os.environ.get("PIPER_OUTPUT_SAMPLE_RATE", "0"))


def resolve_output_sample_rate(payload: dict) -> int:
    """Resolve output sample rate from request or env default (0 = model default)."""
    raw = payload.get("output_sample_rate", DEFAULT_OUTPUT_SAMPLE_RATE)
    if raw in (None, ""):
        return 0

    try:
        sample_rate = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("output_sample_rate must be an integer >= 0") from exc

    if sample_rate < 0:
        raise ValueError("output_sample_rate must be >= 0")

    return sample_rate


def inspect_wav_sample_rate(audio: bytes) -> int:
    with wave.open(io.BytesIO(audio), "rb") as wav:
        return int(wav.getframerate())


def resample_wav_pcm(audio: bytes, target_sample_rate: int) -> tuple[bytes, int, bool]:
    """Resample PCM WAV bytes to target rate using stdlib audioop.ratecv.

    Returns (audio_bytes, effective_sample_rate, was_resampled).
    """
    if target_sample_rate <= 0:
        return audio, inspect_wav_sample_rate(audio), False

    with wave.open(io.BytesIO(audio), "rb") as wav:
        channels = wav.getnchannels()
        sampwidth = wav.getsampwidth()
        source_sample_rate = int(wav.getframerate())
        comptype = wav.getcomptype()
        compname = wav.getcompname()
        frames = wav.readframes(wav.getnframes())

    if source_sample_rate == target_sample_rate:
        return audio, source_sample_rate, False

    if comptype != "NONE":
        raise ValueError(f"Unsupported WAV compression for resample: {comptype}/{compname}")

    converted, _ = audioop.ratecv(frames, sampwidth, channels, source_sample_rate, target_sample_rate, None)

    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sampwidth)
        wav.setframerate(target_sample_rate)
        wav.writeframes(converted)

    return out.getvalue(), target_sample_rate, True


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
                    "default_output_sample_rate": DEFAULT_OUTPUT_SAMPLE_RATE,
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

        try:
            output_sample_rate = resolve_output_sample_rate(payload)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
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
        if output_sample_rate > 0:
            cmd.extend(["--output_sample_rate", str(output_sample_rate)])

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

        effective_sample_rate = 0
        source_sample_rate = 0
        was_resampled = False
        if output_sample_rate > 0:
            try:
                source_sample_rate = inspect_wav_sample_rate(audio)
                audio, effective_sample_rate, was_resampled = resample_wav_pcm(audio, output_sample_rate)
            except Exception as exc:
                self._send_json(
                    {
                        "error": "WAV sample-rate conversion failed",
                        "details": str(exc),
                    },
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return
        else:
            effective_sample_rate = inspect_wav_sample_rate(audio)
            source_sample_rate = effective_sample_rate

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(audio)))
        self.send_header("X-Audio-Sample-Rate", str(effective_sample_rate))
        self.send_header("X-Audio-Source-Sample-Rate", str(source_sample_rate))
        self.send_header("X-Audio-Resampled", "true" if was_resampled else "false")
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
