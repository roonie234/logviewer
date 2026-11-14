"""Stem separation (drums / bass / other / vocals) with Hybrid Demucs from torchaudio.

Weights are downloaded once from download.pytorch.org. Stems are cached as WAV next
to the clip (git-ignored) so re-analysis is instant.
"""

from pathlib import Path

import numpy as np
import soundfile as sf

from ..audio import HIFI_SR, load

SEGMENT_S = 10.0
OVERLAP = 0.1
_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        import torch
        from torchaudio.pipelines import HDEMUCS_HIGH_MUSDB_PLUS

        torch.set_num_threads(max(1, __import__("os").cpu_count() or 1))
        _MODEL = HDEMUCS_HIGH_MUSDB_PLUS.get_model().eval()
    return _MODEL


def separate(audio_path, cache_dir, label):
    """-> {stem_name: mono float32 @44.1k}. Uses cached WAVs when present."""
    cache_dir = Path(cache_dir)
    names = ["drums", "bass", "other", "vocals"]
    cached = {n: cache_dir / f"{label}_{n}.wav" for n in names}
    if all(p.exists() for p in cached.values()):
        return {n: sf.read(p, dtype="float32")[0] for n, p in cached.items()}

    import torch

    model = _model()
    y = load(audio_path, HIFI_SR)
    x = torch.tensor(np.stack([y, y]))[None]
    ref, std = x.mean(), x.std() + 1e-8
    x = (x - ref) / std
    seg = int(SEGMENT_S * HIFI_SR)
    ov = int(OVERLAP * seg)
    total = x.shape[-1]
    out = torch.zeros(1, len(model.sources), 2, total)
    start = 0
    with torch.inference_mode():
        while start < total:
            end = min(start + seg, total)
            o = model(x[..., start:end])
            w = torch.ones(end - start)
            if start > 0:
                w[:ov] = torch.linspace(0, 1, ov)
            if end < total:
                w[-ov:] = torch.linspace(1, 0, ov)
            out[..., start:end] += o * w
            if end >= total:
                break
            start = end - ov
    out = out * std + ref
    cache_dir.mkdir(parents=True, exist_ok=True)
    stems = {}
    for i, name in enumerate(model.sources):
        mono = out[0, i].mean(0).numpy().astype(np.float32)
        stems[name] = mono
        sf.write(cache_dir / f"{label}_{name}.wav", mono, HIFI_SR)
    return stems


def activity(stems, sections, frame_s=0.5):
    """Per-stem loudness curve (dB) and per-section level of each stem relative to its own peak."""
    curves, per_section = {}, []
    hop = int(HIFI_SR * frame_s)
    for name, s in stems.items():
        n = len(s) // hop
        rms = np.sqrt(np.mean(s[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
        db = 20 * np.log10(rms)
        curves[name] = db - db.max()
    times = np.arange(len(next(iter(curves.values())))) * frame_s
    for sec in sections:
        m = (times >= sec["start"]) & (times < sec["end"])
        per_section.append({name: (round(float(c[m].mean()), 1) if m.any() else None) for name, c in curves.items()})
    return times, curves, per_section


def arrangement_summary(per_section, sections, active_db=-30.0):
    """Plain-language arrangement findings from per-section stem levels."""
    notes = []
    for name in per_section[0] if per_section else []:
        levels = [p[name] for p in per_section if p[name] is not None]
        if not levels:
            continue
        on = [l > active_db for l in levels]
        spread = max(levels) - min(levels)
        if all(on) and spread < 4:
            notes.append(f"{name}: plays in every section at nearly the same level (spread {spread:.1f} dB) - no drop-outs or builds")
        elif not any(on):
            notes.append(f"{name}: barely present anywhere")
        else:
            off = [sections[i]["label"] + "@" + f"{int(sections[i]['start'] // 60)}:{int(sections[i]['start'] % 60):02d}"
                   for i, o in enumerate(on) if not o]
            if off:
                notes.append(f"{name}: drops out in {', '.join(off[:5])} (good contrast)")
            else:
                notes.append(f"{name}: always on, level varies by {spread:.1f} dB")
    return notes


def arc(times, curves, drop_t, intro_s=8.0, drop_s=8.0):
    """Each stem's level (dB vs its own peak) in the intro and in the drop."""
    out = {}
    for name, c in curves.items():
        n = min(len(times), len(c))
        t, c = times[:n], c[:n]
        intro = c[t < intro_s]
        drop = c[(t >= drop_t) & (t < drop_t + drop_s)]
        out[name] = {"intro": round(float(np.mean(intro)), 1) if intro.size else None,
                     "drop": round(float(np.mean(drop)), 1) if drop.size else None}
    return out
