"""Tempo, key, loudness and tone colour."""

import librosa
import numpy as np
import pyloudnorm

from ..audio import ANALYSIS_SR, HIFI_SR

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Krumhansl-Kessler key profiles
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
HOP = 512


def tempo(y, sr=ANALYSIS_SR):
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    bpm, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, hop_length=HOP)
    bpm = float(np.atleast_1d(bpm)[0])
    beat_times = librosa.frames_to_time(beats, sr=sr, hop_length=HOP)
    drift = None
    if len(beat_times) > 16:
        ibi = np.diff(beat_times)
        # local tempo over 8-beat windows
        local = 60.0 / np.convolve(ibi, np.ones(8) / 8, mode="valid")
        drift = float(np.std(local))
    return {"bpm": round(bpm, 1), "tempo_drift_bpm": None if drift is None else round(drift, 2)}, beats, onset_env


def key(y, sr=ANALYSIS_SR):
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=HOP)
    profile = chroma.mean(axis=1)
    scores = []
    for i in range(12):
        scores.append((np.corrcoef(profile, np.roll(MAJOR, i))[0, 1], NOTES[i], "major"))
        scores.append((np.corrcoef(profile, np.roll(MINOR, i))[0, 1], NOTES[i], "minor"))
    scores.sort(reverse=True)
    best, second = scores[0], scores[1]
    return {
        "key": best[1],
        "mode": best[2],
        "key_confidence": round(float(best[0]), 3),
        "key_runner_up": f"{second[1]} {second[2]}",
    }, chroma


def loudness(y_hi, sr=HIFI_SR):
    meter = pyloudnorm.Meter(sr)
    lufs = float(meter.integrated_loudness(y_hi))
    # short-term (3 s) loudness -> loudness range like EBU LRA (10th..95th percentile)
    win, hop = 3 * sr, sr
    st = []
    for start in range(0, max(1, len(y_hi) - win), hop):
        seg = y_hi[start:start + win]
        try:
            v = meter.integrated_loudness(seg)
        except ValueError:
            continue
        if np.isfinite(v) and v > -70:
            st.append(v)
    lra = float(np.percentile(st, 95) - np.percentile(st, 10)) if len(st) > 3 else None
    peak = float(np.max(np.abs(y_hi)) + 1e-12)
    rms = float(np.sqrt(np.mean(y_hi ** 2)) + 1e-12)
    return {
        "lufs": round(lufs, 1),
        "loudness_range_lu": None if lra is None else round(lra, 1),
        "crest_factor_db": round(20 * np.log10(peak / rms), 1),
        "true_peak_dbfs": round(20 * np.log10(peak), 1),
    }


def energy_curve(y, sr=ANALYSIS_SR, frame_seconds=0.5):
    """RMS in dB per frame (for section energy and plots)."""
    hop = int(sr * frame_seconds)
    rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0]
    db = 20 * np.log10(rms + 1e-9)
    times = np.arange(len(db)) * frame_seconds
    return times, db


def tone(y, y_hi, sr=ANALYSIS_SR):
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=HOP)[0]
    # effective bandwidth on hi-fi signal: highest freq within 60 dB of the spectral peak
    spec = np.abs(librosa.stft(y_hi, n_fft=4096, hop_length=2048)).mean(axis=1)
    freqs = librosa.fft_frequencies(sr=HIFI_SR, n_fft=4096)
    db = 20 * np.log10(spec + 1e-12)
    above = np.where(db > db.max() - 60)[0]
    bandwidth = float(freqs[above[-1]]) if len(above) else None
    return {
        "brightness_hz": int(np.median(centroid)),
        "bandwidth_hz": None if bandwidth is None else int(bandwidth),
    }
