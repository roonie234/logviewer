"""Heuristic "AI-ish" signals. Each returns a 0..1 score (1 = more machine-like)
with the measured value and human-readable evidence. They are signals for a
diagnosis, not verdicts; the weights get calibrated against the user's ratings.
"""

import librosa
import numpy as np

from ..audio import ANALYSIS_SR, HIFI_SR
from .basics import HOP, NOTES

# default weights; override with playbook/weights.yaml once calibrated
WEIGHTS = {
    "copy_paste_repetition": 1.0,
    "flat_dynamics": 1.0,
    "static_arrangement": 0.8,
    "harmonic_autopilot": 0.8,
    "grid_rigidity": 0.6,
    "artifact_sheen": 0.3,
    "lyric_cliches": 1.0,
}


def _ramp(x, good, bad):
    """0 at `good`, 1 at `bad`, linear between (works for either direction)."""
    if x is None:
        return None
    t = (x - good) / (bad - good)
    return float(min(1.0, max(0.0, t)))


def _mmss(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def _logmel(y, sr=ANALYSIS_SR):
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64, hop_length=HOP)
    return librosa.power_to_db(S, ref=np.max)


def _window_corr(M, a_start, b_start, length, max_lag):
    """Best Pearson correlation of two equal-length log-mel windows over small lags."""
    best = -1.0
    a = M[:, a_start:a_start + length]
    if a.shape[1] < length:
        return None
    a = (a - a.mean()) / (a.std() + 1e-9)
    for lag in range(-max_lag, max_lag + 1):
        s = b_start + lag
        if s < 0 or s + length > M.shape[1]:
            continue
        b = M[:, s:s + length]
        b = (b - b.mean()) / (b.std() + 1e-9)
        best = max(best, float(np.mean(a * b)))
    return best


def copy_paste_repetition(sections, y, sr=ANALYSIS_SR):
    """How identical are repeated sections at the spectrogram level?
    A re-performed chorus differs in tiny details; a looped/pasted one does not."""
    M = _logmel(y, sr)
    fps = sr / HOP
    first = {}
    pairs = []
    for s in sections:
        if s["label"] not in first:
            first[s["label"]] = s
            continue
        f = first[s["label"]]
        dur = min(f["end"] - f["start"], s["end"] - s["start"], 12.0)
        if dur < 4:
            continue
        c = _window_corr(M, int(f["start"] * fps), int(s["start"] * fps), int(dur * fps), int(3.0 * fps))
        if c is not None:
            pairs.append((s, f, c))
    if not pairs:
        return {"score": 0.0, "value": None, "evidence": "No repeated sections to compare."}
    vals = [c for _, _, c in pairs]
    s, f, c = max(pairs, key=lambda p: p[2])
    m = float(np.mean(vals))
    return {
        "score": _ramp(m, 0.80, 0.98),  # calibrate on real songs
        "value": round(m, 3),
        "evidence": (f"{len(pairs)} repeat(s); spectrogram match {m:.0%} on average. Closest copy: "
                     f"{s['label']} at {_mmss(s['start'])} vs {_mmss(f['start'])} ({c:.0%}). "
                     "Near 100% = pasted loop, no re-performance."),
    }


def flat_dynamics(sections, loud):
    energies = [s["energy_db"] for s in sections if s.get("energy_db") is not None]
    spread = float(np.std(energies)) if len(energies) > 1 else 0.0
    parts = [_ramp(spread, 4.0, 1.5)]
    if loud.get("loudness_range_lu") is not None:
        parts.append(_ramp(loud["loudness_range_lu"], 8.0, 3.0))
    parts.append(_ramp(loud["crest_factor_db"], 14.0, 8.0))
    return {
        "score": float(np.mean(parts)),
        "value": round(spread, 2),
        "evidence": (f"Section loudness spread {spread:.1f} dB, loudness range "
                     f"{loud.get('loudness_range_lu')} LU, crest factor {loud['crest_factor_db']} dB "
                     "(low numbers = same intensity throughout, no build and release)."),
    }


def static_arrangement(feats, segs, sections):
    timbre = feats[12:]  # MFCC rows of the beat features
    means = [timbre[:, a:b].mean(axis=1) for a, b in segs]
    sims = []
    for i in range(len(means)):
        for j in range(i + 1, len(means)):
            if sections[i]["label"] != sections[j]["label"]:
                a, b = means[i], means[j]
                sims.append(float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)))
    if not sims:
        return {"score": None, "value": None, "evidence": "Only one kind of section found."}
    m = float(np.mean(sims))
    return {
        "score": _ramp(m, 0.3, 0.9),
        "value": round(m, 3),
        "evidence": (f"Timbre similarity between different sections: {m:.2f} on a -1..1 scale "
                     "(near 1 = same instruments and texture all song)."),
    }


def _chords(y, beats, sr=ANALYSIS_SR):
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=HOP)
    if len(beats) >= 8:
        chroma = librosa.util.sync(chroma, beats, aggregate=np.median)
    names, templates = [], []
    for i in range(12):
        for quality, iv in (("", (0, 4, 7)), ("m", (0, 3, 7))):
            t = np.zeros(12)
            t[[(i + k) % 12 for k in iv]] = 1
            names.append(NOTES[i] + quality)
            templates.append(t / np.linalg.norm(t))
    templates = np.array(templates)
    c = chroma / (np.linalg.norm(chroma, axis=0, keepdims=True) + 1e-9)
    idx = np.argmax(templates @ c, axis=0)
    # smooth: majority over 2-beat windows (cheap chord stabilisation)
    seq = [names[i] for i in idx]
    collapsed = [ch for k, ch in enumerate(seq) if k == 0 or ch != seq[k - 1]]
    # drop flickers (chords lasting 1 beat between same neighbours)
    return seq, collapsed


def harmonic_autopilot(y, beats):
    seq, changes = _chords(y, beats)
    unique = sorted(set(seq), key=seq.count, reverse=True)
    if len(changes) < 8:
        return {"score": _ramp(len(unique), 6, 2), "value": len(unique),
                "evidence": f"Very few chord changes detected ({len(changes)}).", "progression": changes}
    grams = {}
    for k in range(len(changes) - 3):
        g = tuple(changes[k:k + 4])
        grams[g] = grams.get(g, 0) + 1
    top, count = max(grams.items(), key=lambda kv: kv[1])
    coverage = min(1.0, count * 4 / len(changes))
    common = [u for u in unique if seq.count(u) / len(seq) >= 0.03]
    score = 0.7 * _ramp(coverage, 0.3, 0.75) + 0.3 * _ramp(len(common), 7, 3)
    return {
        "score": float(score),
        "value": round(coverage, 2),
        "evidence": (f"Most common loop {' - '.join(top)} covers ~{coverage:.0%} of chord changes; "
                     f"{len(common)} chords in regular use (estimated from audio, approximate)."),
        "progression": changes[:32],
    }


def grid_rigidity(y, beats, sr=ANALYSIS_SR):
    if len(beats) < 16:
        return {"score": None, "value": None, "evidence": "No steady beat found."}
    bt = librosa.frames_to_time(beats, sr=sr, hop_length=HOP)
    # fit a perfectly steady grid to the beats, then measure onsets against its 16th notes
    k = np.arange(len(bt))
    period, offset = np.polyfit(k, bt, 1)
    onsets = librosa.onset.onset_detect(y=y, sr=sr, hop_length=HOP, units="time", backtrack=False)
    sub = period / 4
    pos = (onsets - offset) / sub
    dev_ms = np.abs(pos - np.round(pos)) * sub * 1000
    dev_ms = dev_ms[dev_ms < sub * 1000 * 0.35]  # ignore onsets far off-grid (fills, tuplets)
    if len(dev_ms) < 20:
        return {"score": None, "value": None, "evidence": "Too few onsets to judge timing."}
    med = float(np.median(dev_ms))
    return {
        "score": _ramp(med, 18.0, 6.0),
        "value": round(med, 1),
        "evidence": f"Median onset offset from a perfect 16th-note grid: {med:.1f} ms (very low = quantised, no push and pull).",
    }


def artifact_sheen(y_hi, sr=HIFI_SR):
    S = np.abs(librosa.stft(y_hi, n_fft=2048, hop_length=1024))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    band = S[(freqs >= 10000) & (freqs <= 16000)]
    if band.size == 0 or band.mean() < 1e-6:
        return {"score": 0.0, "value": None, "evidence": "Little energy above 10 kHz (rolled-off or band-limited top end)."}
    flat = librosa.feature.spectral_flatness(S=band)[0]
    loud = S.sum(axis=0)
    quiet = loud < np.percentile(loud, 25)
    m = float(np.mean(flat[quiet])) if quiet.any() else float(np.mean(flat))
    return {
        "score": _ramp(m, 0.15, 0.45),
        "value": round(m, 3),
        "evidence": (f"High-band (10-16 kHz) noise flatness in quiet passages: {m:.2f} "
                     "(high = hissy, shimmery top end; experimental signal)."),
    }


def lyric_cliches(lint_result):
    if lint_result is None:
        return {"score": None, "value": None, "evidence": "No lyrics available."}
    density = lint_result["cliche_per_100_words"]
    hits = ", ".join(sorted({h["phrase"] for h in lint_result["cliches"]})[:8]) or "none"
    return {
        "score": _ramp(density, 0.0, 3.0),
        "value": density,
        "evidence": f"{density} cliches per 100 words ({hits}).",
    }


def combine(signals, weights=None):
    weights = weights or WEIGHTS
    num = den = 0.0
    for name, sig in signals.items():
        if sig.get("score") is None:
            continue
        w = weights.get(name, 0.0)
        num += w * sig["score"]
        den += w
    return None if den == 0 else round(100 * (1 - num / den))
