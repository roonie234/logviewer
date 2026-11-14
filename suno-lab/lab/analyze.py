"""Analyze every clip in a version folder -> metrics.json, report.md, plots/."""

import json
from pathlib import Path

import librosa
import numpy as np
import yaml

from . import brief as brief_mod
from . import compare, lint, plots
from .audio import ANALYSIS_SR, load_pair
from .features import basics, humanness, structure

AUDIO_EXT = (".m4a", ".mp3", ".wav", ".ogg", ".flac", ".opus")
WEIGHTS_FILE = Path(__file__).resolve().parent.parent / "playbook" / "weights.yaml"


def _mmss(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def weights():
    if WEIGHTS_FILE.exists():
        return {**humanness.WEIGHTS, **(yaml.safe_load(WEIGHTS_FILE.read_text()) or {})}
    return humanness.WEIGHTS


def analyze_clip(audio_path, clip=None, brief=None, plots_dir=None, label="a"):
    clip = clip or {}
    y_hi, y = load_pair(audio_path)
    duration = len(y) / ANALYSIS_SR

    t, beats, _ = basics.tempo(y)
    k, _ = basics.key(y)
    loud = basics.loudness(y_hi)
    tone = basics.tone(y, y_hi)
    e_times, e_db = basics.energy_curve(y)

    sections, ssm, nov, feats, segs, beat_times = structure.segment(y, beats)
    structure.add_energy(sections, e_times, e_db)
    structure.guess_roles(sections)
    ending = structure.ending_shape(e_times, e_db, duration)

    lyrics = clip.get("lyrics") or (brief or {}).get("lyrics") or ""
    lint_res = lint.lint(lyrics, clip.get("style", ""), clip.get("exclude", ""), clip.get("title") or "") if (lyrics or clip.get("style")) else None

    signals = {
        "copy_paste_repetition": humanness.copy_paste_repetition(sections, y),
        "flat_dynamics": humanness.flat_dynamics(sections, loud),
        "static_arrangement": humanness.static_arrangement(feats, segs, sections),
        "harmonic_autopilot": humanness.harmonic_autopilot(y, beats),
        "grid_rigidity": humanness.grid_rigidity(y, beats),
        "artifact_sheen": humanness.artifact_sheen(y_hi),
        "lyric_cliches": humanness.lyric_cliches(lint_res if lyrics else None),
    }
    m = {
        "label": label,
        "clip": {k_: v for k_, v in clip.items() if k_ != "audio_url"},
        "duration_s": round(duration, 1),
        "basics": {**t, **k, **loud, **tone},
        "structure": {"sections": sections, "ending": ending},
        "humanness": {"score": humanness.combine(signals, weights()), "signals": signals},
        "lint": lint_res,
    }
    if brief:
        m["brief_check"] = compare.against_brief(m, brief)

    if plots_dir:
        plots_dir = Path(plots_dir)
        plots_dir.mkdir(parents=True, exist_ok=True)
        title = clip.get("title") or Path(audio_path).stem
        plots.overview(plots_dir / f"{label}_overview.png", y, sections, e_times, e_db, nov, beat_times, f"[{label}] {title}")
        plots.similarity(plots_dir / f"{label}_similarity.png", ssm, beat_times, sections, f"[{label}] {title}")
    return m


def find_clips(version_dir):
    version_dir = Path(version_dir)
    clips = []
    for audio in sorted(p for p in version_dir.iterdir() if p.suffix.lower() in AUDIO_EXT):
        meta = version_dir / f"{audio.stem}.clip.json"
        clips.append((audio.stem, audio, json.loads(meta.read_text()) if meta.exists() else {}))
    return clips


def analyze_version(version_dir):
    version_dir = Path(version_dir)
    brief_path = version_dir / "brief.yaml"
    brief = brief_mod.load(brief_path) if brief_path.exists() else None
    clips = find_clips(version_dir)
    if not clips:
        raise SystemExit(f"No audio in {version_dir}. Fetch songs first: python -m lab fetch {version_dir} <link>")
    results = {}
    for label, audio, clip in clips:
        print(f"analyzing {label} ({audio.name})...")
        results[label] = analyze_clip(audio, clip, brief, version_dir / "plots", label)
    (version_dir / "metrics.json").write_text(json.dumps(results, indent=2, ensure_ascii=False, default=_json_default))
    (version_dir / "report.md").write_text(report(results, brief, version_dir.name))
    return results


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    raise TypeError(type(o))


def report(results, brief, version):
    out = [f"# Analysis - {version}", ""]
    if brief:
        out += [f"Vibe: {brief['vibe']}  ", f"Testing: {', '.join(brief.get('techniques_testing') or []) or '-'}", ""]
    if len(results) > 1:
        out += ["## Clips side by side", "", compare.clips_table(results), ""]
    for label, m in results.items():
        c = m["clip"]
        b = m["basics"]
        out += [f"## Clip {label}: {c.get('title') or label}", ""]
        if c.get("link"):
            out.append(f"Link: {c['link']} - model {c.get('model_version') or c.get('model_name') or '?'}  ")
        out += [
            f"Duration {_mmss(m['duration_s'])} | {b['bpm']} BPM (drift {b['tempo_drift_bpm']}) | "
            f"{b['key']} {b['mode']} (conf {b['key_confidence']}) | {b['lufs']} LUFS | "
            f"LRA {b['loudness_range_lu']} LU | crest {b['crest_factor_db']} dB | brightness {b['brightness_hz']} Hz | "
            f"bandwidth {b['bandwidth_hz']} Hz",
            "",
            f"### Humanness: {m['humanness']['score']}/100",
            "",
        ]
        sigs = sorted(m["humanness"]["signals"].items(), key=lambda kv: -(kv[1]["score"] if kv[1]["score"] is not None else -1))
        for name, s in sigs:
            score = "n/a " if s["score"] is None else f"{s['score']:.2f}"
            out.append(f"- **{name}** {score} - {s['evidence']}")
        out.append("")
        if m.get("brief_check"):
            out += ["### Against the brief", "", "| aspect | target | measured | ok |", "|---|---|---|---|"]
            for r in m["brief_check"]:
                out.append(f"| {r['aspect']} | {r['target']} | {r['measured']}{r['note']} | {'yes' if r['ok'] else '**NO**'} |")
            out.append("")
        out += ["### Structure", "", "| # | time | label | role? | energy vs median | repeat similarity |", "|---|---|---|---|---|---|"]
        for i, s in enumerate(m["structure"]["sections"], 1):
            sim = "-" if s["similarity_to_first"] is None else f"{s['similarity_to_first']:.0%}"
            out.append(f"| {i} | {_mmss(s['start'])}-{_mmss(s['end'])} | {s['label']} | {s['role_guess']} | {s['energy_db']:+} dB | {sim} |")
        e = m["structure"]["ending"]
        out += ["", f"Ending: {e['ending']} (last 10 s slope {e['ending_slope_db_per_s']} dB/s)", ""]
        if c.get("style"):
            out += ["### Prompt Suno actually used", "", "Style:", "```", c["style"], "```"]
            if c.get("exclude"):
                out += ["Exclude:", "```", c["exclude"], "```"]
        if m.get("lint"):
            out += ["", "Prompt lint:", "```", lint.format_findings(m["lint"]), "```"]
        out += ["", f"Plots: `plots/{label}_overview.png`, `plots/{label}_similarity.png`", ""]
    return "\n".join(out)
