"""Reference profiles: measure a folder of reference tracks the user owns, keep only the numbers.

    python -m lab profile build mass-hero references/mass-hero [--ears]
    python -m lab profile show mass-hero

The profile stores ranges (10th-50th-90th percentile) of each metric plus, with --ears, a CLAP
centroid. No audio, file names or melodies are kept. New cues are compared against it with
`python -m lab analyze <dir> --profile mass-hero`.
"""

from datetime import date
from pathlib import Path

import numpy as np
import yaml

PROFILES = Path(__file__).resolve().parent.parent / "playbook" / "profiles"

# (key, label, getter)
METRICS = [
    ("bpm", "tempo (BPM)", lambda m: m["basics"]["bpm"]),
    ("duration_s", "length (s)", lambda m: m["duration_s"]),
    ("lufs", "loudness (LUFS)", lambda m: m["basics"]["lufs"]),
    ("loudness_range_lu", "loudness range (LU)", lambda m: m["basics"]["loudness_range_lu"]),
    ("crest_factor_db", "crest factor (dB)", lambda m: m["basics"]["crest_factor_db"]),
    ("brightness_hz", "brightness (Hz)", lambda m: m["basics"]["brightness_hz"]),
    ("n_impacts", "impact points", lambda m: m["bgm"]["n_impacts"]),
    ("first_impact_s", "first impact (s)", lambda m: m["bgm"]["first_impact_s"]),
    ("drop_time_s", "main drop time (s)", lambda m: m["bgm"]["drop"]["time_s"]),
    ("drop_position", "drop position (fraction)", lambda m: m["bgm"]["drop"]["position"]),
    ("drop_lift_db", "drop lift (dB)", lambda m: m["bgm"]["drop"]["lift_db"]),
    ("build_length_s", "build length (s)", lambda m: m["bgm"]["build"]["length_s"]),
    ("build_slope", "build slope (dB/s)", lambda m: m["bgm"]["build"]["slope_db_per_s"]),
    ("pause_length_s", "pause before drop (s)", lambda m: m["bgm"]["pause"]["length_s"]),
    ("pause_depth_db", "pause depth (dB)", lambda m: m["bgm"]["pause"]["depth_db"]),
    ("hits_per_s_drop", "hits/s in drop", lambda m: m["bgm"]["impact"]["hits_per_s_drop"]),
    ("sub_share_drop", "sub-bass share in drop", lambda m: m["bgm"]["impact"]["sub_share_drop"]),
    ("sub_share_build", "sub-bass share in build", lambda m: m["bgm"]["impact"]["sub_share_build"]),
    ("drums_intro_db", "drums level in intro (dB vs peak)", lambda m: m["bgm"]["stems_arc"]["drums"]["intro"]),
    ("drums_drop_db", "drums level in drop (dB vs peak)", lambda m: m["bgm"]["stems_arc"]["drums"]["drop"]),
    ("bass_intro_db", "bass level in intro (dB vs peak)", lambda m: m["bgm"]["stems_arc"]["bass"]["intro"]),
    ("bass_drop_db", "bass level in drop (dB vs peak)", lambda m: m["bgm"]["stems_arc"]["bass"]["drop"]),
]


def _get(fn, m):
    try:
        v = fn(m)
    except (KeyError, TypeError):
        return None
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / (np.linalg.norm(v) + 1e-9)


def summarize(metrics_list, name, embeddings=None):
    out = {"name": name, "created": date.today().isoformat(), "n_references": len(metrics_list), "metrics": {}}
    for key, label, fn in METRICS:
        vals = [v for v in (_get(fn, m) for m in metrics_list) if v is not None]
        if not vals:
            continue
        lo, mid, hi = (np.percentile(vals, [10, 50, 90]) if len(vals) >= 5 else (min(vals), float(np.median(vals)), max(vals)))
        out["metrics"][key] = {"label": label, "p10": round(float(lo), 3), "p50": round(float(mid), 3), "p90": round(float(hi), 3), "n": len(vals)}
    if embeddings:
        c = _unit(np.mean([_unit(e) for e in embeddings], axis=0))
        out["clap_centroid"] = [round(float(x), 5) for x in c]
        out["clap_ref_similarity"] = [round(float(_unit(e) @ c), 3) for e in embeddings]
    return out


def build(name, ref_dir, ears=False, out_dir=PROFILES):
    from .analyze import AUDIO_EXT, analyze_clip

    ref_dir = Path(ref_dir)
    files = sorted(p for p in ref_dir.iterdir() if p.suffix.lower() in AUDIO_EXT)
    if not files:
        raise SystemExit(f"No audio files in {ref_dir}")
    metrics, embs = [], []
    for i, f in enumerate(files, 1):
        print(f"[{i}/{len(files)}] measuring reference {i}...")
        m = analyze_clip(f, {}, {"kind": "bgm"}, plots_dir=None, label=f"ref{i}", ears=ears,
                         kind="bgm", remember=False, stems_dir=ref_dir / ".stems")
        metrics.append(m)
        emb = ((m.get("ears") or {}).get("description") or {}).get("embedding")
        if emb:
            embs.append(emb)
    prof = summarize(metrics, name, embs or None)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.yaml"
    path.write_text(yaml.safe_dump(prof, sort_keys=False, width=200))
    return path, prof


def load(name, out_dir=PROFILES):
    path = Path(name) if str(name).endswith(".yaml") else Path(out_dir) / f"{name}.yaml"
    return yaml.safe_load(path.read_text())


def compare(m, prof):
    """-> rows [{label, target, measured, status}] and style similarity (if both have CLAP data)."""
    rows = []
    for key, label, fn in METRICS:
        tgt = prof["metrics"].get(key)
        v = _get(fn, m)
        if not tgt or v is None:
            continue
        span = max(tgt["p90"] - tgt["p10"], 1e-9)
        # tolerance: a quarter of the reference spread plus 5% of the median, so a few
        # near-identical references don't flag every tiny difference
        tol = 0.25 * span + 0.05 * abs(tgt["p50"])
        if v < tgt["p10"] - tol:
            status = "low"
        elif v > tgt["p90"] + tol:
            status = "high"
        else:
            status = "ok"
        rows.append({"key": key, "label": label, "target": f"{tgt['p10']:g} - {tgt['p90']:g} (median {tgt['p50']:g})",
                     "measured": round(v, 3), "status": status,
                     "off_by": 0.0 if status == "ok" else round(abs(v - (tgt["p10"] if status == "low" else tgt["p90"])) / span, 2)})
    sim = None
    emb = ((m.get("ears") or {}).get("description") or {}).get("embedding")
    if emb and prof.get("clap_centroid"):
        from .ears.describe import _reference_mean
        ref = _reference_mean(None)
        e, c = np.asarray(emb, float), np.asarray(prof["clap_centroid"], float)
        if ref is not None:
            e, c = e - ref, c - ref
        sim = round(float(_unit(e) @ _unit(c)), 3)
    return {"rows": rows, "style_similarity": sim,
            "reference_similarity_range": [min(prof.get("clap_ref_similarity") or [0]), max(prof.get("clap_ref_similarity") or [0])]}


def report_lines(cmp, prof):
    out = [f"Compared with profile **{prof['name']}** ({prof['n_references']} references):", "",
           "| metric | references | this cue | |", "|---|---|---|---|"]
    for r in sorted(cmp["rows"], key=lambda r: -r["off_by"]):
        flag = "ok" if r["status"] == "ok" else f"**{r['status']}**"
        out.append(f"| {r['label']} | {r['target']} | {r['measured']:g} | {flag} |")
    if cmp["style_similarity"] is not None:
        out += ["", f"Sound similarity to the references (CLAP, relative to generic music): **{cmp['style_similarity']}** "
                f"(1 = same character; for scale, each reference vs the reference average: "
                f"{cmp['reference_similarity_range'][0]}-{cmp['reference_similarity_range'][1]} before generic-music correction)."]
    return out


def show(name):
    prof = load(name)
    lines = [f"# Profile {prof['name']} - {prof['n_references']} references, built {prof['created']}", ""]
    for key, v in prof["metrics"].items():
        lines.append(f"- {v['label']}: {v['p10']:g} - {v['p90']:g} (median {v['p50']:g})")
    if prof.get("clap_centroid"):
        lines.append("- CLAP sound centroid: stored")
    return "\n".join(lines)
