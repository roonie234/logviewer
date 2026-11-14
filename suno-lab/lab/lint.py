"""Prompt linter: flags what makes a Suno prompt read generic or machine-written."""

import re
from functools import lru_cache
from pathlib import Path

import yaml

PLAYBOOK = Path(__file__).resolve().parent.parent / "playbook"
STYLE_LIMIT, LYRICS_LIMIT, TITLE_LIMIT = 1000, 5000, 80
TAG_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
KNOWN_SECTIONS = {
    "intro", "verse", "pre-chorus", "prechorus", "chorus", "final chorus", "post-chorus",
    "hook", "bridge", "break", "instrumental break", "instrumental", "solo", "drop", "build",
    "outro", "fade out", "end", "interlude", "refrain",
}


@lru_cache(maxsize=1)
def cliches():
    return yaml.safe_load((PLAYBOOK / "cliches.yaml").read_text())


def syllables(word):
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 0
    groups = re.findall(r"[aeiouy]+", word)
    n = len(groups)
    if word.endswith("e") and not word.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(1, n)


def rhyme_key(line):
    words = re.findall(r"[a-z']+", line.lower())
    if not words:
        return None
    w = words[-1].strip("'")
    m = re.search(r"[aeiouy]+[^aeiouy]*$", w)
    return m.group(0) if m else w


def parse_lyrics(lyrics):
    """-> list of {tag, lines}; text before the first tag goes under tag None."""
    sections, cur = [], {"tag": None, "lines": []}
    for raw in (lyrics or "").splitlines():
        m = TAG_RE.match(raw)
        if m:
            if cur["tag"] is not None or cur["lines"]:
                sections.append(cur)
            cur = {"tag": m.group(1).strip(), "lines": []}
        elif raw.strip():
            cur["lines"].append(raw.strip())
    if cur["tag"] is not None or cur["lines"]:
        sections.append(cur)
    return sections


def _section_kind(tag):
    base = tag.split(":")[0].strip().lower()
    base = re.sub(r"\s*\d+$", "", base)
    return base


def find_cliches(text):
    text_l = " " + re.sub(r"\s+", " ", text.lower()) + " "
    taken = [False] * len(text_l)
    hits = []
    for item in sorted(cliches()["lyric_cliches"], key=lambda c: -len(c["phrase"])):
        for m in re.finditer(r"\b%s\b" % re.escape(item["phrase"]), text_l):
            if any(taken[m.start():m.end()]):
                continue
            for k in range(m.start(), m.end()):
                taken[k] = True
            hits.append({"phrase": item["phrase"], "weight": item["weight"]})
    return hits


def lint(lyrics="", style="", exclude="", title="", brief=None):
    findings = []

    def add(severity, technique, message):
        findings.append({"severity": severity, "technique": technique, "message": message})

    # ---- limits
    if len(style) > STYLE_LIMIT:
        add("error", None, f"Style is {len(style)} chars (limit ~{STYLE_LIMIT}).")
    if len(lyrics) > LYRICS_LIMIT:
        add("error", None, f"Lyrics are {len(lyrics)} chars (limit ~{LYRICS_LIMIT}).")
    if len(title) > TITLE_LIMIT:
        add("error", None, f"Title is {len(title)} chars (limit ~{TITLE_LIMIT}).")

    # ---- style
    style_l = style.lower()
    generic = [w for w in cliches()["generic_style_words"] if re.search(r"\b%s\b" % re.escape(w), style_l)]
    if generic:
        add("warn", "sound-not-adjectives",
            f"Style uses quality/mood words that describe no sound: {', '.join(generic)}. Replace with instruments, playing style, room, era.")
    genres = sorted({g for g in cliches()["genres"] if re.search(r"(?<![a-z])%s(?![a-z])" % re.escape(g), style_l)})
    if len(genres) > 3:
        add("warn", "focused-style", f"Style mixes {len(genres)} genres ({', '.join(genres)}); pick one anchor + one twist or it blurs into generic.")
    if style and not re.search(r"\b\d{2,3}\s*bpm\b", style_l):
        add("info", "tempo-key-in-style", "No BPM in style; add one to pin the tempo.")
    if style and not re.search(r"\b(live|room|tape|analog|vintage|recorded|lo-fi|close-mic|demo)\b", style_l):
        add("info", "recording-space", "Style says nothing about recording space or era; this often helps it sound captured, not generated.")
    if not exclude.strip():
        add("info", "exclude-the-defaults", "Exclude field is empty; consider excluding default sounds you don't want.")
    if brief and brief.get("bpm") and str(brief["bpm"]) not in style:
        add("warn", "tempo-key-in-style", f"Brief asks for {brief['bpm']} BPM but the style doesn't say it.")

    # ---- lyrics
    sections = parse_lyrics(lyrics)
    lyric_lines = [l for s in sections for l in s["lines"]]
    words = re.findall(r"[A-Za-z']+", " ".join(lyric_lines))
    hits = find_cliches(" ".join(lyric_lines)) if lyric_lines else []
    weighted = sum(h["weight"] for h in hits)
    density = round(weighted * 100 / max(1, len(words)), 2)
    if hits:
        add("warn" if density >= 1 else "info", "concrete-specifics",
            f"Cliches: {', '.join(sorted({h['phrase'] for h in hits}))}. Swap each for a concrete, specific detail.")

    stats = {"lines": len(lyric_lines), "words": len(words), "sections": [s["tag"] for s in sections]}
    if lyric_lines:
        tags = [s["tag"] for s in sections if s["tag"]]
        kinds = [_section_kind(t) for t in tags]
        if not tags:
            add("warn", "explicit-sections", "No section tags. Tag [Verse]/[Chorus]/[Bridge]/[Outro] in order.")
        unknown = [t for t, k in zip(tags, kinds) if k not in KNOWN_SECTIONS and not k.endswith("solo")]
        if unknown:
            add("info", None, f"Non-standard tags (fine if they are delivery cues): {', '.join(unknown[:6])}")
        if tags and not any(k in ("outro", "end", "fade out") for k in kinds):
            add("warn", "designed-ending", "No [Outro]/[End]; songs often end abruptly or ramble without one.")
        if tags and kinds[0] == "intro" and ":" not in tags[0]:
            add("info", "short-described-intro", "Describe the intro, e.g. [Intro: solo piano, 4 bars], to keep it short.")
        if kinds and not any("instrumental" in k or "solo" in k or k == "break" for k in kinds):
            add("info", "instrumental-moment", "No instrumental moment; a named solo/break adds a human, band-like feel.")

        choruses = [tuple(s["lines"]) for s in sections if s["tag"] and "chorus" in _section_kind(s["tag"]) and s["lines"]]
        if len(choruses) >= 2 and len(set(choruses)) == 1:
            add("warn", "vary-the-repeat", f"All {len(choruses)} choruses are word-for-word identical. Change a line or a delivery cue on the return.")

        syl = [sum(syllables(w) for w in re.findall(r"[A-Za-z']+", l)) for l in lyric_lines]
        mean = sum(syl) / len(syl)
        cv = (sum((s - mean) ** 2 for s in syl) / len(syl)) ** 0.5 / (mean or 1)
        stats.update({"syllables_mean": round(mean, 1), "syllable_variation": round(cv, 2)})
        if len(syl) >= 8 and cv < 0.18:
            add("warn", "uneven-lines", f"Lines are very uniform in length (variation {cv:.2f}); vary them so phrasing sounds human.")
        long = [l for l in lyric_lines if len(l.split()) > 14]
        if long:
            add("info", None, f"{len(long)} line(s) over 14 words may get rushed: \"{long[0][:60]}...\"")

        keys = [rhyme_key(l) for l in lyric_lines]
        pairs = [(keys[i], keys[i + 1]) for i in range(0, len(keys) - 1, 2) if keys[i] and keys[i + 1]]
        if len(pairs) >= 6:
            perfect = sum(a == b for a, b in pairs) / len(pairs)
            stats["couplet_rhyme_ratio"] = round(perfect, 2)
            if perfect > 0.75:
                add("info", "uneven-lines", f"{perfect:.0%} of line pairs are perfect rhymes; some slant or broken rhymes read more human.")

    return {
        "findings": findings,
        "cliches": hits,
        "cliche_per_100_words": density,
        "stats": stats,
    }


def format_findings(result):
    icons = {"error": "ERROR", "warn": "WARN ", "info": "info "}
    lines = []
    for f in sorted(result["findings"], key=lambda f: ["error", "warn", "info"].index(f["severity"])):
        tech = f" [{f['technique']}]" if f["technique"] else ""
        lines.append(f"{icons[f['severity']]} {f['message']}{tech}")
    return "\n".join(lines) or "No issues found."
