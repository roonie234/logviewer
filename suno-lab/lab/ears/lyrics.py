"""Hear the sung lyrics (Whisper on the vocal stem) and compare with the lyrics that were written.

No lyric hint is given to Whisper, so it reports what it actually hears: slurred or
invented words show up as mismatches and low word confidence.
"""

import re
from difflib import SequenceMatcher

import numpy as np

from ..lint import parse_lyrics, _section_kind

WHISPER_SR = 16000
_MODEL = {}


def _model(size):
    if size not in _MODEL:
        from faster_whisper import WhisperModel

        import os
        _MODEL[size] = WhisperModel(size, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    return _MODEL[size]


def transcribe(vocals_44k, size="small"):
    """-> list of {word, start, end, prob}."""
    import librosa

    y = librosa.resample(vocals_44k, orig_sr=44100, target_sr=WHISPER_SR, res_type="soxr_hq")
    segments, _ = _model(size).transcribe(
        y, language="en", word_timestamps=True, vad_filter=True,
        condition_on_previous_text=False, beam_size=5,
    )
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"word": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2), "prob": round(w.probability, 3)})
    return words


def _norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'"))


def _short(text, n=90):
    return text if len(text) <= n else text[: n - 3] + "..."


def _mmss(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def compare(written_lyrics, heard_words):
    """Align written lyrics with what was sung.

    -> {lines: [...], sections: [...], mismatches: [...], heard_ratio, mean_confidence, mumbled}
    """
    sections = parse_lyrics(written_lyrics)
    w_words, w_line = [], []  # flat written words + which (section, line) they belong to
    lines = []
    for si, sec in enumerate(sections):
        for line in sec["lines"]:
            # parenthesised text = backing vocals; often inaudible after separation, don't penalise
            main = re.sub(r"\([^)]*\)", " ", line)
            toks = [t for t in (_norm(x) for x in main.split()) if t]
            if not toks:
                continue
            lines.append({"section": sec["tag"] or "(untagged)", "sec_idx": si, "text": line, "n": len(toks), "matched": 0, "times": []})
            for t in toks:
                w_words.append(t)
                w_line.append(len(lines) - 1)

    h_norm = [_norm(w["word"]) for w in heard_words]
    keep = [i for i, t in enumerate(h_norm) if t]
    h_tokens = [h_norm[i] for i in keep]
    sm = SequenceMatcher(a=w_words, b=h_tokens, autojunk=False)
    mismatches = []
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op == "equal":
            for k in range(a1 - a0):
                ln = lines[w_line[a0 + k]]
                ln["matched"] += 1
                hw = heard_words[keep[b0 + k]]
                ln["times"].append((hw["start"], hw["end"], hw["prob"]))
        else:
            written = " ".join(w_words[a0:a1])
            heard = " ".join(heard_words[keep[k]]["word"] for k in range(b0, b1))
            t = heard_words[keep[b0]]["start"] if b1 > b0 else (heard_words[keep[b0 - 1]]["end"] if b0 > 0 else 0)
            kind = {"replace": "sang differently", "delete": "not heard", "insert": "sung but not written"}[op]
            if (a1 - a0) + (b1 - b0) >= 2 or op == "replace":
                mismatches.append({"time": round(t, 1), "kind": kind, "written": written, "heard": heard})

    for ln in lines:
        ln["status"] = "ok" if ln["matched"] >= 0.7 * ln["n"] else ("partial" if ln["matched"] >= 0.3 * ln["n"] else "missing")
        ln["start"] = round(min(t[0] for t in ln["times"]), 1) if ln["times"] else None
        ln["confidence"] = round(float(np.mean([t[2] for t in ln["times"]])), 2) if ln["times"] else None
        del ln["times"]

    # where each written section was actually sung
    sec_times = []
    cur = None
    for ln in lines:
        if cur is None or ln["sec_idx"] != cur["sec_idx"]:
            cur = {"section": ln["section"], "sec_idx": ln["sec_idx"], "start": ln["start"], "end": ln["start"], "lines": 0, "ok": 0}
            sec_times.append(cur)
        cur["lines"] += 1
        cur["ok"] += ln["status"] == "ok"
        if ln["start"] is not None:
            cur["start"] = ln["start"] if cur["start"] is None else min(cur["start"], ln["start"])
            cur["end"] = ln["start"] if cur["end"] is None else max(cur["end"], ln["start"])

    total = sum(l["n"] for l in lines) or 1
    probs = [w["prob"] for w in heard_words]
    return {
        "lines": lines,
        "sections": sec_times,
        "mismatches": mismatches,
        "heard_ratio": round(sum(l["matched"] for l in lines) / total, 3),
        "mean_confidence": round(float(np.mean(probs)), 3) if probs else None,
        "mumbled_words": sum(p < 0.5 for p in probs),
        "words_heard": len(heard_words),
    }


def report_lines(cmp):
    out = [f"Heard {cmp['heard_ratio']:.0%} of the written words; average word confidence "
           f"{cmp['mean_confidence']}; {cmp['mumbled_words']} of {cmp['words_heard']} sung words unclear (<50% confidence).", ""]
    if cmp["sections"]:
        out += ["| written section | sung at | lines clear |", "|---|---|---|"]
        for s in cmp["sections"]:
            at = "-" if s["start"] is None else f"{_mmss(s['start'])}-{_mmss(s['end'])}"
            out.append(f"| {s['section']} | {at} | {s['ok']}/{s['lines']} |")
        out.append("")
    if cmp["mismatches"]:
        out += ["Mismatches (written vs sung):", ""]
        for m in cmp["mismatches"][:25]:
            out.append(f"- {_mmss(m['time'])} {m['kind']}: written \"{_short(m['written'])}\" / heard \"{_short(m['heard'])}\"")
        if len(cmp["mismatches"]) > 25:
            out.append(f"- ... {len(cmp['mismatches']) - 25} more in metrics.json")
    return out


def plain_transcript(heard_words, gap=1.2):
    """Group heard words into lines (for instrumental-less checks or when no lyrics were written)."""
    out, cur, last = [], [], None
    for w in heard_words:
        if last is not None and w["start"] - last > gap and cur:
            out.append((cur[0]["start"], " ".join(x["word"] for x in cur)))
            cur = []
        cur.append(w)
        last = w["end"]
    if cur:
        out.append((cur[0]["start"], " ".join(x["word"] for x in cur)))
    return out
