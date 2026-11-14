"""Synthetic test songs with known tempo, key and form."""

import numpy as np

SR = 44100
BPM = 120
BEAT = 60 / BPM
NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def chord_freqs(name):
    root = NOTE[name[0]]
    third = 3 if name.endswith("m") else 4
    return [261.63 * 2 ** ((root + iv) / 12) for iv in (0, third, 7)] + [130.81 * 2 ** (root / 12)]


def tone(freqs, dur, bright, rng, detune=0.0):
    t = np.arange(int(dur * SR)) / SR
    env = np.exp(-t * (1.5 if bright < 0.5 else 0.6))
    out = np.zeros_like(t)
    for f in freqs:
        f = f * (1 + detune * rng.standard_normal() * 0.002)
        for h in range(1, 6):
            out += (bright ** (h - 1)) / h * np.sin(2 * np.pi * f * h * t)
    return out * env


def drums(n_beats, accent, rng, jitter_ms=0.0):
    out = np.zeros(int(n_beats * BEAT * SR) + SR)
    t = np.arange(int(0.12 * SR)) / SR
    kick = np.sin(2 * np.pi * 60 * t) * np.exp(-t * 30)
    hat = rng.standard_normal(int(0.03 * SR)) * np.exp(-np.arange(int(0.03 * SR)) / SR * 150) * 0.3
    for b in range(n_beats * 2):
        pos = b * BEAT / 2 + rng.normal(0, jitter_ms / 1000)
        i = max(0, int(pos * SR))
        if b % 2 == 0:
            out[i:i + len(kick)] += kick * accent
        out[i:i + len(hat)] += hat * accent
    return out[: int(n_beats * BEAT * SR)]


def section(chords, beats_per_chord, bright, gain, rng, jitter_ms=0.0, detune=0.0):
    parts = [tone(chord_freqs(c), beats_per_chord * BEAT, bright, rng, detune) for c in chords]
    harm = np.concatenate(parts)
    d = drums(len(chords) * beats_per_chord, 0.8, rng, jitter_ms)
    n = min(len(harm), len(d))
    return gain * (0.25 * harm[:n] + d[:n])


def song(dynamic=True, exact_repeat=True, seed=0):
    rng = np.random.default_rng(seed)
    verse = ["C", "G", "Am", "F"] * 2   # 8 chords x 4 beats = 32 beats = 16 s
    chorus = ["F", "C", "G", "C"] * 2
    g_low, g_high = (0.35, 1.0) if dynamic else (0.8, 0.85)
    a1 = section(verse, 4, 0.3, g_low, rng)
    b1 = section(chorus, 4, 0.8, g_high, rng)
    if exact_repeat:
        a2, b2 = a1.copy(), b1.copy()
    else:  # same harmony, different texture/rhythm/brightness on the return
        a2 = section(verse, 4, 0.45, g_low * 1.2, rng, jitter_ms=15, detune=1.0)
        b2 = section(chorus, 4, 0.65, g_high * 0.9, rng, jitter_ms=15, detune=1.0)
    y = np.concatenate([a1, b1, a2, b2])
    y += rng.standard_normal(len(y)) * 0.002
    if not dynamic:
        y = np.tanh(3 * y) / 3  # squash it
    return (0.9 * y / np.max(np.abs(y))).astype(np.float32)
