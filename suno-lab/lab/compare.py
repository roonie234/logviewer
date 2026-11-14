"""Brief vs measured, clip vs clip, version vs version."""

import numpy as np

from .features.basics import NOTES
from .lint import _section_kind


def _relative(key, mode):
    i = NOTES.index(key)
    return (NOTES[(i + 9) % 12], "minor") if mode == "major" else (NOTES[(i + 3) % 12], "major")


def against_brief(m, brief):
    """List of {aspect, target, measured, ok, note}."""
    out = []
    if brief.get("bpm"):
        target, got = float(brief["bpm"]), m["basics"]["bpm"]
        ratios = {1.0: "", 2.0: " (detected at double time)", 0.5: " (detected at half time)"}
        ok, note = False, ""
        for r, n in ratios.items():
            if abs(got / (target * r) - 1) <= 0.05:
                ok, note = True, n
        out.append({"aspect": "tempo", "target": f"{target:g} BPM", "measured": f"{got} BPM", "ok": ok, "note": note})
    if brief.get("key"):
        tk, tm = brief["key"], brief.get("mode", "major")
        gk, gm = m["basics"]["key"], m["basics"]["mode"]
        if (tk, tm) == (gk, gm):
            ok, note = True, ""
        elif (gk, gm) == _relative(tk, tm):
            ok, note = True, " (relative key - same notes, check the mood)"
        else:
            ok, note = False, f" (runner-up: {m['basics']['key_runner_up']})"
        out.append({"aspect": "key", "target": f"{tk} {tm}", "measured": f"{gk} {gm}", "ok": ok, "note": note})

    planned = [s for s in brief.get("sections", []) if _section_kind(s["tag"]) != "end"]
    detected = m["structure"]["sections"]
    if planned:
        ok = abs(len(detected) - len(planned)) <= 2
        out.append({"aspect": "section count", "target": len(planned), "measured": len(detected), "ok": ok,
                    "note": "" if ok else " (sections merged or extra parts invented)"})
        first = planned[0]
        if _section_kind(first["tag"]) == "intro" and detected:
            intro_len = detected[0]["end"] - detected[0]["start"]
            ok = intro_len <= 20
            out.append({"aspect": "intro length", "target": "<= 20 s", "measured": f"{intro_len:.0f} s", "ok": ok, "note": ""})
        if any(_section_kind(s["tag"]) in ("outro", "fade out") for s in brief["sections"]):
            ending = m["structure"]["ending"]["ending"]
            out.append({"aspect": "ending", "target": "designed outro", "measured": ending,
                        "ok": not ending.startswith("abrupt"), "note": ""})

        energies = [s.get("energy") for s in planned]
        if "high" in energies and "low" in energies:
            chorus = [s["energy_db"] for s in detected if s["role_guess"] == "chorus?" and s["energy_db"] is not None]
            others = [s["energy_db"] for s in detected if s["role_guess"] != "chorus?" and s["energy_db"] is not None]
            if chorus and others:
                lift = float(np.mean(chorus) - np.mean(others))
                out.append({"aspect": "chorus lift", "target": ">= 2 dB louder than the rest",
                            "measured": f"{lift:+.1f} dB", "ok": lift >= 2, "note": ""})
    return out


KEY_METRICS = [
    ("humanness", lambda m: m["humanness"]["score"]),
    ("bpm", lambda m: m["basics"]["bpm"]),
    ("key", lambda m: f"{m['basics']['key']} {m['basics']['mode']}"),
    ("LUFS", lambda m: m["basics"]["lufs"]),
    ("loudness range LU", lambda m: m["basics"]["loudness_range_lu"]),
    ("sections", lambda m: len(m["structure"]["sections"])),
    ("ending", lambda m: m["structure"]["ending"]["ending"]),
]


def clips_table(metrics_by_label):
    labels = list(metrics_by_label)
    rows = ["| metric | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for name, fn in KEY_METRICS:
        vals = []
        for l in labels:
            try:
                vals.append(str(fn(metrics_by_label[l])))
            except (KeyError, TypeError):
                vals.append("-")
        rows.append(f"| {name} | " + " | ".join(vals) + " |")
    for sig in metrics_by_label[labels[0]]["humanness"]["signals"]:
        vals = []
        for l in labels:
            s = metrics_by_label[l]["humanness"]["signals"][sig]["score"]
            vals.append("-" if s is None else f"{s:.2f}")
        rows.append(f"| ai-ish: {sig} | " + " | ".join(vals) + " |")
    return "\n".join(rows)
