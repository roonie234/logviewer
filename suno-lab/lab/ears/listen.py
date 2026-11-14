"""Run all ears on one clip and turn the results into humanness signals and report text."""

import time
from pathlib import Path

from ..features.humanness import _ramp
from . import describe, lyrics, stems, vocals


def listen(audio_path, y_hi, sections, clip, brief, out_dir, label, whisper_size="small"):
    out_dir = Path(out_dir)
    timings = {}
    t = time.time()
    st = stems.separate(audio_path, out_dir / "stems", label)
    timings["stems_s"] = round(time.time() - t, 1)

    times, curves, per_section = stems.activity(st, sections)
    res = {"arrangement": {"per_section": per_section, "notes": stems.arrangement_summary(per_section, sections)}}

    t = time.time()
    res["vocals"] = vocals.analyze(st["vocals"])
    timings["vocals_s"] = round(time.time() - t, 1)

    written = clip.get("lyrics") or (brief or {}).get("lyrics") or ""
    instrumental = clip.get("instrumental") or (res["vocals"].get("sung_ratio", 0) < 0.05)
    if not instrumental:
        t = time.time()
        heard = lyrics.transcribe(st["vocals"], whisper_size)
        timings["lyrics_s"] = round(time.time() - t, 1)
        res["lyrics"] = {"heard_words": heard}
        if written.strip():
            res["lyrics"]["comparison"] = lyrics.compare(written, heard)

    t = time.time()
    key = clip.get("id") or f"{out_dir.parent.name}/{out_dir.name}/{label}"
    res["description"] = describe.describe(y_hi, sections, clip.get("style") or "", key=key)
    timings["describe_s"] = round(time.time() - t, 1)
    res["timings"] = timings
    res["_curves"] = (times, curves)  # for plotting; not serialised
    return res


def signals(res):
    out = {}
    cmp = (res.get("lyrics") or {}).get("comparison")
    if cmp:
        conf = cmp["mean_confidence"] or 0
        score = max(_ramp(conf, 0.85, 0.55), _ramp(cmp["heard_ratio"], 0.85, 0.5))
        out["slurred_lyrics"] = {
            "score": score, "value": cmp["heard_ratio"],
            "evidence": (f"{cmp['heard_ratio']:.0%} of written words recognisably sung, average word confidence {conf:.2f}, "
                         f"{cmp['mumbled_words']} unclear words."),
        }
    v = res.get("vocals") or {}
    if v.get("pitch_offset_cents_median") is not None:
        dev = v["pitch_offset_cents_median"]
        out["pitch_snapped_vocals"] = {
            "score": _ramp(dev, 16.0, 6.0), "value": dev,
            "evidence": f"Held notes sit a median {dev} cents from exact pitch (under ~8 = auto-tune-like; humans drift 15-30).",
        }
    return out


def report_lines(res):
    out = ["### What the ears heard", ""]
    out += describe.report_lines(res["description"]) + [""]
    out += ["**Arrangement (from separated stems)**", ""] + [f"- {n}" for n in res["arrangement"]["notes"]] + [""]
    out += ["**Vocals**", ""] + vocals.report_lines(res["vocals"]) + [""]
    lyr = res.get("lyrics")
    if lyr and lyr.get("comparison"):
        out += ["**Lyrics: written vs sung**", ""] + lyrics.report_lines(lyr["comparison"]) + [""]
    elif lyr:
        out += ["**Lyrics heard** (no written lyrics to compare)", ""]
        out += [f"- {int(t // 60)}:{int(t % 60):02d} {text}" for t, text in lyrics.plain_transcript(lyr["heard_words"])[:40]] + [""]
    out.append(f"_ears timings: {res['timings']}_")
    return out
