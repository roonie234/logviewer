"""Put the sound into words with CLAP (audio-text embeddings).

- what it sounds like: best-matching phrases from playbook/hearing_tags.yaml
- style adherence: was each descriptor in the Style prompt actually heard?
- per section: what makes each section sound different from the rest of the song

Scores are relative: a descriptor's percentile against the whole tag bank. CLAP is
approximate; treat this as a second opinion, not ground truth.
"""

import re
from pathlib import Path

import numpy as np
import yaml

CLAP_ID = "laion/larger_clap_music_and_speech"
CLAP_SR = 48000
WINDOW_S = 10.0
TAGS = Path(__file__).resolve().parents[2] / "playbook" / "hearing_tags.yaml"
REFERENCE = Path(__file__).resolve().parents[2] / "playbook" / "clap_reference.json"
SEED_EXAMPLES = ["brahms", "choice", "nutcracker", "pistachio", "sweetwaltz", "vibeace", "trumpet"]
_M = {}
SECTION_GROUPS = {"instruments", "vocals", "energy"}  # genre/mood per section is too noisy


def _clap():
    if "m" not in _M:
        from transformers import ClapModel, ClapProcessor

        _M["m"] = ClapModel.from_pretrained(CLAP_ID).eval()
        _M["p"] = ClapProcessor.from_pretrained(CLAP_ID)
    return _M["m"], _M["p"]


def _bank():
    data = yaml.safe_load(TAGS.read_text())
    return [(group, phrase) for group, phrases in data.items() for phrase in phrases]


def _embed_text(texts):
    import torch

    m, p = _clap()
    with torch.inference_mode():
        t = m.get_text_features(**p(text=texts, return_tensors="pt", padding=True))
    return torch.nn.functional.normalize(t, dim=-1).numpy()


def _embed_windows(y48):
    import torch

    m, p = _clap()
    n = int(WINDOW_S * CLAP_SR)
    starts = list(range(0, max(1, len(y48) - n // 2), n))
    wins = [y48[s:s + n] for s in starts]
    embs = []
    for i in range(0, len(wins), 8):
        with torch.inference_mode():
            a = m.get_audio_features(**p(audio=wins[i:i + 8], sampling_rate=CLAP_SR, return_tensors="pt"))
        embs.append(torch.nn.functional.normalize(a, dim=-1).numpy())
    return np.array(starts) / CLAP_SR, np.concatenate(embs)


def style_descriptors(style):
    parts = [p.strip(" .") for p in re.split(r"[,;\n]|\. ", style or "")]
    out = []
    for p in parts:
        if not p or re.fullmatch(r"\d{2,3}\s*bpm", p.lower()) or re.fullmatch(r"[a-g][#b]?\s*(major|minor)", p.lower()):
            continue
        out.append(p[:120])
    return out[:30]


def _unit(v):
    return v / (np.linalg.norm(v) + 1e-9)


def _load_reference():
    import json

    return json.loads(REFERENCE.read_text()) if REFERENCE.exists() else {}


def song_embedding(y_hi):
    import librosa

    y48 = librosa.resample(y_hi, orig_sr=44100, target_sr=CLAP_SR, res_type="soxr_hq")
    times, A = _embed_windows(y48)
    return times, A, _unit(A.mean(axis=0))


def add_to_reference(key, emb):
    """Remember this song so future descriptions are judged against everything heard so far."""
    import json

    ref = _load_reference()
    ref[key] = [round(float(x), 5) for x in emb]
    REFERENCE.write_text(json.dumps(ref))


def build_seed_reference():
    """Embed librosa's free example tracks as the starting 'typical music' reference."""
    import librosa

    from ..audio import load

    for ex in SEED_EXAMPLES:
        _, _, emb = song_embedding(load(librosa.ex(ex), 44100))
        add_to_reference(f"seed:{ex}", emb)


def _reference_mean(exclude_key):
    ref = {k: v for k, v in _load_reference().items() if k != exclude_key}
    if not ref:
        return None
    return np.mean(np.array(list(ref.values())), axis=0)


def describe(y_hi, sections, style="", key=None, remember=True):
    times, A, song = song_embedding(y_hi)
    ref_mean = _reference_mean(key)
    # compare against typical music, so phrases that match everything stop winning
    target = song - ref_mean if ref_mean is not None else song

    bank = _bank()
    T = _embed_text([p for _, p in bank])
    bank_sims = T @ target

    top = {}
    for (group, phrase), s in sorted(zip(bank, bank_sims), key=lambda x: -x[1]):
        top.setdefault(group, [])
        if len(top[group]) < 3:
            top[group].append({"phrase": phrase, "score": round(float(s), 3)})

    adherence = []
    desc = style_descriptors(style)
    if desc:
        D = _embed_text(desc)
        for d, s in zip(desc, D @ target):
            pct = float((bank_sims < s).mean())
            verdict = "heard" if pct >= 0.75 else ("faint" if pct >= 0.4 else "not heard")
            adherence.append({"descriptor": d, "percentile": round(pct, 2), "verdict": verdict})

    song_sims = T @ song
    per_section = []
    ok = np.array([g in SECTION_GROUPS for g, _ in bank])
    for sec in sections:
        m = (times + WINDOW_S / 2 >= sec["start"]) & (times + WINDOW_S / 2 < sec["end"])
        if not m.any():
            continue
        v = _unit(A[m].mean(axis=0))
        delta = np.where(ok, T @ v - song_sims, -1)  # what is more true here than in the song overall
        thr = max(0.03, float(np.std(delta[ok])) * 2)
        best = [i for i in np.argsort(-delta)[:3] if delta[i] > thr]
        per_section.append({"start": sec["start"], "label": sec["label"], "distinct": [bank[i][1] for i in best]})

    if remember and key:
        add_to_reference(key, song)
    return {"top": top, "style_adherence": adherence, "per_section": per_section,
            "reference_songs": len(_load_reference()) - (1 if remember and key else 0)}


def report_lines(d):
    out = [f"What it sounds like (best CLAP matches, compared with {d.get('reference_songs', 0)} reference songs):", ""]
    for group, items in d["top"].items():
        out.append(f"- {group}: " + ", ".join(i["phrase"] for i in items))
    if d["style_adherence"]:
        out += ["", "Style prompt vs what was heard (percentile against the tag bank; approximate):", "",
                "| descriptor | heard? | percentile |", "|---|---|---|"]
        for a in d["style_adherence"]:
            v = a["verdict"] if a["verdict"] == "heard" else f"**{a['verdict']}**"
            out.append(f"| {a['descriptor']} | {v} | {a['percentile']:.0%} |")
    if d["per_section"]:
        out += ["", "What stands out in each section:", ""]
        for s in d["per_section"]:
            t = f"{int(s['start'] // 60)}:{int(s['start'] % 60):02d}"
            out.append(f"- {t} [{s['label']}]: {', '.join(s['distinct']) or 'nothing distinctive vs the rest of the song'}")
    return out
