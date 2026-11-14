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


def _hit(n, f0, decay, rng, noise=0.3):
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f0 * t) + noise * rng.standard_normal(n)) * np.exp(-t * decay)


def bgm(drop=True, seed=1, bpm=140, drop_at=28.5):
    """Mass-entry style cue: drone intro, accelerating build, 0.5 s silence, loud drop with sub bass.
    drop=False gives the same material at one flat level with no pause."""
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    total = drop_at + 20.0 + 4.0
    y = np.zeros(int(total * SR))
    t_all = np.arange(len(y)) / SR

    def add(at, sig, gain):
        i = int(at * SR)
        j = min(len(y), i + len(sig))
        if i < len(y):
            y[i:j] += gain * sig[: j - i]

    build_start, pause = 8.0, 0.5
    # drone through intro + build
    drone = 0.05 * np.sin(2 * np.pi * 55 * t_all) * (t_all < drop_at - pause)
    y += drone if drop else 0.0
    # intro: sparse low toms
    for k in np.arange(0.0, build_start, beat * 2):
        add(k, _hit(int(0.3 * SR), 90, 12, rng), 0.15 if drop else 0.6)
    # build: hits accelerating and getting louder, plus a noise riser
    k = build_start
    while k < drop_at - pause:
        prog = (k - build_start) / (drop_at - pause - build_start)
        add(k, _hit(int(0.2 * SR), 140, 20, rng), (0.12 + 0.45 * prog) if drop else 0.6)
        k += beat * (1.0 - 0.75 * prog)
    if drop:
        rm = (t_all >= build_start) & (t_all < drop_at - pause)
        y[rm] += rng.standard_normal(rm.sum()) * 0.08 * ((t_all[rm] - build_start) / (drop_at - pause - build_start)) ** 2
    # drop: kick + sub on beats, dense 16th percussion, brass-like stabs
    k = drop_at if drop else 0.0
    end = drop_at + 20.0
    g = 1.0 if drop else 0.6
    while k < end:
        add(k, _hit(int(0.5 * SR), 45, 4, rng, noise=0.05), 0.9 * g)
        for s in range(4):
            add(k + s * beat / 4, _hit(int(0.08 * SR), 300, 60, rng, noise=1.0), 0.25 * g)
        if int((k - drop_at) / beat) % 2 == 1:
            n = int(0.15 * SR)
            tt = np.arange(n) / SR
            add(k + beat / 2, sum(np.sin(2 * np.pi * f * h * tt) / h for f in (233, 294, 349) for h in (1, 2, 3)) * np.exp(-tt * 8), 0.12 * g)
        k += beat
    if not drop:  # flat: no silence, constant bed
        y += 0.05 * np.sin(2 * np.pi * 55 * t_all)
    # outro decay
    y += 0.0
    y += rng.standard_normal(len(y)) * 0.001
    return (0.9 * y / np.max(np.abs(y))).astype(np.float32)
