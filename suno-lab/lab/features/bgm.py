"""BGM impact: the build, the breath before the drop, the drop itself, low-end weight.

All times in seconds. Works on the full mix; stems (from --ears) refine the arrangement arc.
"""

import librosa
import numpy as np

from ..audio import ANALYSIS_SR
from .humanness import _ramp, _mmss

FINE_HOP = 512  # ~23 ms at 22.05 kHz


def _fine_db(y, sr=ANALYSIS_SR):
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=FINE_HOP)[0]
    return librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=FINE_HOP), 20 * np.log10(rms + 1e-9)


def _smooth(x, n):
    n = max(1, int(n))
    return np.convolve(x, np.ones(n) / n, mode="same")


def _smooth_db(db, n):
    """Smooth loudness in the power domain, so a short silence doesn't drag the average to -90 dB."""
    return 10 * np.log10(_smooth(10 ** (db / 10), n) + 1e-12)


def _window(t, x, a, b):
    m = (t >= a) & (t < b)
    return x[m] if m.any() else np.array([np.nan])


def find_drop(y, sr=ANALYSIS_SR):
    """The moment of the biggest sustained lift in loudness + onset density."""
    t, db = _fine_db(y, sr)
    dur = t[-1]
    fps = 1 / (t[1] - t[0])
    db_s = _smooth_db(db, fps * 1.0)
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=FINE_HOP)[: len(t)]
    on_s = _smooth(onset, fps * 2.0)
    on_norm = on_s / (np.percentile(on_s, 95) + 1e-9)

    best, best_t = -np.inf, None
    step = max(1, int(fps * 0.1))
    for i in range(0, len(t), step):
        ti = t[i]
        if ti < 5 or ti > dur - 4:
            continue
        pre = _window(t, db_s, ti - 8, ti - 1.5)
        post = _window(t, db_s, ti + 0.3, ti + 4.3)
        lift = np.nanmedian(post) - np.nanmedian(pre)
        dens = np.nanmean(_window(t, on_norm, ti, ti + 4)) - np.nanmean(_window(t, on_norm, ti - 8, ti - 1.5))
        score = lift + 4 * dens
        if score > best:
            best, best_t = score, ti
    if best_t is None:
        return None, t, db
    # snap to the actual hit: steepest rise of the un-smoothed level within +-1.5 s
    m = (t >= best_t - 1.5) & (t <= best_t + 1.5)
    idx = np.where(m)[0]
    rise = np.diff(db[idx[0]:idx[-1] + 2])
    hit = t[idx[0] + int(np.argmax(rise)) + 1] if len(rise) else best_t
    return float(hit), t, db


def analyze(y, y_hi=None, sr=ANALYSIS_SR):
    drop_t, t, db = find_drop(y, sr)
    dur = float(t[-1])
    if drop_t is None:
        return {"drop": None, "note": "Track too short to judge a drop."}
    fps = 1 / (t[1] - t[0])
    db_s = _smooth_db(db, fps * 1.0)

    build_level = float(np.nanmedian(_window(t, db, drop_t - 4, drop_t - 1.2)))
    drop_level = float(np.nanmedian(_window(t, db_s, drop_t + 0.3, drop_t + 6)))
    pre_level = float(np.nanmedian(_window(t, db_s, drop_t - 8, drop_t - 1.5)))

    # breath before the hit: how far and how long the level dips in the last ~1.5 s
    gap = _window(t, db, drop_t - 1.5, drop_t - 0.02)
    depth = float(build_level - np.nanmin(gap)) if gap.size else 0.0
    low = gap < build_level - 10
    run = 0
    for v in low[::-1]:  # contiguous quiet right before the hit
        if not v:
            break
        run += 1
    pause_len = run / fps

    # build: from the quietest point in the 40 s before, up to the pause
    w = (t >= max(0, drop_t - 40)) & (t < drop_t - 1.5)
    if w.any():
        i_min = np.where(w)[0][np.argmin(db_s[w])]
        b0 = float(t[i_min])
    else:
        b0 = max(0.0, drop_t - 8)
    bm = (t >= b0) & (t < drop_t - 1.5)
    slope = float(np.polyfit(t[bm], db_s[bm], 1)[0]) if bm.sum() > 10 else 0.0

    # low end and hits: drop vs build
    def band_share(a, b, lo=20, hi=60):
        seg = y[int(a * sr):int(b * sr)]
        if len(seg) < 2048:
            return None
        S = np.abs(librosa.stft(seg, n_fft=4096, hop_length=2048)) ** 2
        f = librosa.fft_frequencies(sr=sr, n_fft=4096)
        return float(S[(f >= lo) & (f < hi)].sum() / (S.sum() + 1e-12))

    def onset_rate(a, b):
        seg = y[int(a * sr):int(b * sr)]
        if len(seg) < sr:
            return None
        return float(len(librosa.onset.onset_detect(y=seg, sr=sr)) / (len(seg) / sr))

    drop_end = min(dur, drop_t + 8)
    seg = (y_hi if y_hi is not None else y)
    k = 44100 if y_hi is not None else sr
    dseg = seg[int(drop_t * k):int(drop_end * k)]
    crest = float(20 * np.log10((np.max(np.abs(dseg)) + 1e-9) / (np.sqrt(np.mean(dseg ** 2)) + 1e-9))) if len(dseg) else None

    return {
        "drop": {
            "time_s": round(drop_t, 2),
            "lift_db": round(drop_level - pre_level, 1),
            "position": round(drop_t / dur, 2),
        },
        "build": {
            "start_s": round(b0, 1),
            "length_s": round(drop_t - 1.5 - b0, 1),
            "slope_db_per_s": round(slope, 2),
            "rises": bool(slope > 0.15),
        },
        "pause": {
            "depth_db": round(depth, 1),
            "length_s": round(pause_len, 2),
            "present": bool(depth >= 10 and pause_len >= 0.12),
        },
        "impact": {
            "crest_db": None if crest is None else round(crest, 1),
            "hits_per_s_drop": None if onset_rate(drop_t, drop_end) is None else round(onset_rate(drop_t, drop_end), 2),
            "hits_per_s_build": None if onset_rate(b0, drop_t - 1.5) is None else round(onset_rate(b0, drop_t - 1.5), 2),
            "sub_share_drop": None if band_share(drop_t, drop_end) is None else round(band_share(drop_t, drop_end), 3),
            "sub_share_build": None if band_share(b0, drop_t - 1.5) is None else round(band_share(b0, drop_t - 1.5), 3),
        },
        "duration_s": round(dur, 1),
    }


def weak_drop(b):
    """Humanness-style signal for BGMs: 1 = the drop doesn't land."""
    if not b or not b.get("drop"):
        return {"score": None, "value": None, "evidence": "No drop analysis."}
    d, p, bl = b["drop"], b["pause"], b["build"]
    score = 0.6 * _ramp(d["lift_db"], 9.0, 3.0) + 0.25 * (0.0 if p["present"] else 1.0) + 0.15 * (0.0 if bl["rises"] else 1.0)
    return {
        "score": float(score),
        "value": d["lift_db"],
        "evidence": (f"Drop at {_mmss(d['time_s'])} lifts {d['lift_db']:+.1f} dB over the build; "
                     f"pause before it: {'yes' if p['present'] else 'no'} ({p['length_s']} s, {p['depth_db']} dB dip); "
                     f"build {'rises' if bl['rises'] else 'does not rise'} ({bl['slope_db_per_s']} dB/s over {bl['length_s']} s)."),
    }


def report_lines(b):
    if not b or not b.get("drop"):
        return [b.get("note", "No drop found.") if b else "No drop found."]
    d, p, bl, im = b["drop"], b["pause"], b["build"], b["impact"]
    return [
        f"- **Drop** at {_mmss(d['time_s'])} ({d['position']:.0%} into the cue), lift **{d['lift_db']:+.1f} dB** over the build",
        f"- **Build** {_mmss(bl['start_s'])} -> {_mmss(d['time_s'])} ({bl['length_s']} s), slope {bl['slope_db_per_s']} dB/s - {'rising' if bl['rises'] else '**not really rising**'}",
        f"- **Breath before the drop**: {'yes' if p['present'] else '**none**'} - {p['length_s']} s, {p['depth_db']} dB dip",
        f"- **Impact**: crest {im['crest_db']} dB, hits/s build {im['hits_per_s_build']} -> drop {im['hits_per_s_drop']}, "
        f"sub-bass share build {im['sub_share_build']} -> drop {im['sub_share_drop']}",
    ]
