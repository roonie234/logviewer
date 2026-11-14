"""Song structure: section boundaries, repeat labels (A/B/C...), intro and ending shape."""

import string

import librosa
import numpy as np
from scipy.ndimage import median_filter, uniform_filter1d
from scipy.signal import find_peaks

from ..audio import ANALYSIS_SR
from .basics import HOP

MIN_SECTION_S = 8.0
SMOOTH_S = 4.0  # average features over ~2 bars so chord changes don't look like section changes
KERNEL_HALF_S = 8.0


def beat_features(y, beats, sr=ANALYSIS_SR):
    """Beat-synchronous chroma + timbre features, each frame L2-normalised."""
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=HOP)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=HOP)[1:]  # drop loudness coef
    mfcc = (mfcc - mfcc.mean(axis=1, keepdims=True)) / (mfcc.std(axis=1, keepdims=True) + 1e-9)
    n = min(chroma.shape[1], mfcc.shape[1])
    unit = lambda m: m / (np.linalg.norm(m, axis=0, keepdims=True) + 1e-9)
    # equal say for harmony (chroma) and timbre (mfcc); rows 0-11 chroma, 12+ mfcc
    feats = np.vstack([unit(chroma[:, :n]), unit(mfcc[:, :n])])
    if len(beats) < 16:  # no reliable beat: fall back to ~0.5 s frames
        beats = np.arange(0, n, int(0.5 * sr / HOP))
    sync = librosa.util.sync(feats, beats, aggregate=np.median)
    sync /= np.linalg.norm(sync, axis=0, keepdims=True) + 1e-9
    bounds = librosa.util.fix_frames(beats, x_min=0, x_max=n)
    times = librosa.frames_to_time(bounds, sr=sr, hop_length=HOP)
    return sync, times  # times has len(sync.T) + 1 boundaries


def self_similarity(feats):
    ssm = feats.T @ feats
    return median_filter(ssm, size=(1, 5))  # smooth along diagonals a little


def novelty(ssm, half=8):
    """Foote checkerboard novelty along the diagonal."""
    k = np.ones((2 * half, 2 * half))
    k[:half, half:] = -1
    k[half:, :half] = -1
    g = np.outer(np.hanning(2 * half), np.hanning(2 * half))
    k *= g
    n = ssm.shape[0]
    padded = np.pad(ssm, half, mode="edge")
    nov = np.array([np.sum(padded[i:i + 2 * half, i:i + 2 * half] * k) for i in range(n)])
    nov = np.maximum(nov, 0)
    return nov / (nov.max() + 1e-9)


def aligned_similarity(feats, seg_a, seg_b, max_lag=4):
    """Mean per-beat cosine similarity of two segments, best over small time offsets.

    Compares equal-length windows (the shorter segment's length) so an exact
    copy scores ~1.0 even if a detected boundary is a beat or two off.
    """
    (a0, a1), (b0, b1) = seg_a, seg_b
    length = min(a1 - a0, b1 - b0) - max_lag
    if length < 4:
        length = min(a1 - a0, b1 - b0)
        max_lag = 0
    best = -1.0
    n = feats.shape[1]
    for lag in range(-max_lag, max_lag + 1):
        sa, sb = a0, b0 + lag
        if sb < 0 or sb + length > n or sa + length > n:
            continue
        s = float(np.mean(np.sum(feats[:, sa:sa + length] * feats[:, sb:sb + length], axis=0)))
        best = max(best, s)
    return best


def _refine(cuts, feats, beat_s, window_s=3.0):
    """Snap each coarse boundary to the sharpest local timbre change within +-window_s."""
    timbre = feats[12:] / (np.linalg.norm(feats[12:], axis=0, keepdims=True) + 1e-9)
    fine = novelty(self_similarity(timbre), half=max(2, int(round(1.5 / beat_s))))
    w = max(1, int(round(window_s / beat_s)))
    out = []
    for c in cuts:
        lo, hi = max(1, c - w), min(len(fine) - 1, c + w + 1)
        out.append(int(lo + np.argmax(fine[lo:hi])) if hi > lo else c)
    return out


def _smooth(feats, beat_s):
    w = max(1, int(round(SMOOTH_S / beat_s)))
    sm = uniform_filter1d(feats, size=w, axis=1, mode="nearest")
    return sm / (np.linalg.norm(sm, axis=0, keepdims=True) + 1e-9)


def same_section_threshold(M):
    """A repeat must stand out from this song's typical section-to-section similarity."""
    off = M[~np.eye(len(M), dtype=bool)]
    if off.size < 2:
        return 0.8
    return float(np.clip(off.mean() + 1.0 * off.std(), 0.6, 0.9))


def segment(y, beats, sr=ANALYSIS_SR):
    feats, times = beat_features(y, beats, sr)
    n = feats.shape[1]
    beat_s = float(np.median(np.diff(times))) if len(times) > 1 else 0.5
    ssm = self_similarity(_smooth(feats, beat_s))
    half = max(4, min(int(round(KERNEL_HALF_S / beat_s)), n // 4))
    nov = novelty(ssm, half=half)
    min_beats = max(4, int(round(MIN_SECTION_S / beat_s)))
    peaks, _ = find_peaks(nov, distance=min_beats, height=0.2, prominence=0.1)
    inner = _refine([int(p) for p in peaks if min_beats <= p <= n - min_beats], feats, beat_s)
    cuts = [0] + sorted(set(inner)) + [n]
    segs = list(zip(cuts[:-1], cuts[1:]))

    # pairwise similarity (unsmoothed features keep the detail), symmetrised
    M = np.array([[aligned_similarity(feats, a, b) for b in segs] for a in segs])
    M = (M + M.T) / 2
    threshold = same_section_threshold(M)

    # label: each section joins the most similar earlier label if it clears the threshold
    labels, sims, first_idx = [], [], {}
    for i in range(len(segs)):
        best_label, best_sim = None, -1.0
        for label, j in first_idx.items():
            if M[i, j] > best_sim:
                best_label, best_sim = label, float(M[i, j])
        if best_sim >= threshold:
            labels.append(best_label)
            sims.append(best_sim)
        else:
            label = string.ascii_uppercase[len(first_idx) % 26]
            first_idx[label] = i
            labels.append(label)
            sims.append(None)

    # merge neighbours that got the same label (one long section, not two)
    merged = []
    for seg, label, sim in zip(segs, labels, sims):
        if merged and merged[-1][1] == label:
            (a, _), _, first_sim = merged[-1]
            merged[-1] = ((a, seg[1]), label, first_sim)
        else:
            merged.append((seg, label, sim))
    segs = [m[0] for m in merged]
    labels = [m[1] for m in merged]
    sims = [m[2] for m in merged]

    sections = []
    for (a, b), label, sim in zip(segs, labels, sims):
        sections.append({
            "start": round(float(times[a]), 1),
            "end": round(float(times[min(b, len(times) - 1)]), 1),
            "label": label,
            "similarity_to_first": None if sim is None else round(sim, 3),
        })
    return sections, ssm, nov, feats, segs, times


def add_energy(sections, energy_times, energy_db):
    median = float(np.median(energy_db))
    for s in sections:
        m = (energy_times >= s["start"]) & (energy_times < s["end"])
        s["energy_db"] = round(float(energy_db[m].mean()) - median, 1) if m.any() else None
    return sections


def guess_roles(sections):
    """Heuristic: loudest repeated label = chorus, other repeated = verse, edges = intro/outro."""
    counts = {}
    energy = {}
    for s in sections:
        counts[s["label"]] = counts.get(s["label"], 0) + 1
        energy.setdefault(s["label"], []).append(s["energy_db"] or 0)
    repeated = sorted([l for l, c in counts.items() if c >= 2], key=lambda l: -np.mean(energy[l]))
    roles = {}
    if repeated:
        roles[repeated[0]] = "chorus?"
        for l in repeated[1:]:
            roles[l] = "verse?"
    for i, s in enumerate(sections):
        role = roles.get(s["label"])
        if role is None:
            if i == 0:
                role = "intro?"
            elif i == len(sections) - 1:
                role = "outro?"
            else:
                role = "bridge/break?"
        s["role_guess"] = role
    return sections


def ending_shape(energy_times, energy_db, duration):
    median = float(np.median(energy_db))
    tail = energy_times >= duration - 10
    last = energy_times >= duration - 1.5
    slope = float(np.polyfit(energy_times[tail], energy_db[tail], 1)[0]) if tail.sum() > 3 else 0.0
    last_level = float(energy_db[last].mean() - median) if last.any() else 0.0
    if last_level > -6:
        shape = "abrupt (still loud in the final second)"
    elif slope < -1.5:
        shape = "fade-out"
    else:
        shape = "clean ending"
    return {"ending": shape, "ending_slope_db_per_s": round(slope, 2), "final_second_vs_median_db": round(last_level, 1)}
