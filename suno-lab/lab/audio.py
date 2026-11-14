"""Audio loading via ffmpeg (handles Suno's m4a/opus streams, mp3 and wav)."""

import shutil
import subprocess

import numpy as np

ANALYSIS_SR = 22050  # most features
HIFI_SR = 44100  # loudness and high-frequency checks


def load(path, sr=HIFI_SR):
    """Decode any audio file to mono float32 at `sr`."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required but was not found on PATH")
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(path),
        "-ac", "1", "-ar", str(sr), "-f", "f32le", "-",
    ]
    out = subprocess.run(cmd, capture_output=True, check=False)
    if out.returncode != 0:
        raise RuntimeError(f"ffmpeg could not decode {path}: {out.stderr.decode(errors='ignore')[:300]}")
    y = np.frombuffer(out.stdout, dtype=np.float32).copy()
    if y.size == 0:
        raise RuntimeError(f"{path} decoded to silence / no samples")
    return y


def load_pair(path):
    """Return (y_hifi @44.1k, y @22.05k) from one decode."""
    import librosa

    y_hi = load(path, HIFI_SR)
    y = librosa.resample(y_hi, orig_sr=HIFI_SR, target_sr=ANALYSIS_SR, res_type="soxr_hq")
    return y_hi, y
