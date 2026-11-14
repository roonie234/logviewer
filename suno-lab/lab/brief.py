"""The song brief: what the song should be. Claude writes it from the user's one vibe line.

Example (sessions/<slug>/brief.yaml):

    vibe: "late-night drive after a breakup, but hopeful"
    direction: |
      Warm 80s-tinged soft rock, half-whispered verses, a chorus that finally exhales.
    title: "Exit 14"
    genre: "soft rock"
    twist: "Afrobeat guitar picking"
    bpm: 92
    key: "A"
    mode: "major"
    instrumentation: ["clean electric guitar, palm-muted", "Rhodes", "live drums with brushes"]
    production: "recorded live in a small room, 1980s tape, slight hiss"
    vocals: "husky male tenor, close-mic, tired but warm"
    energy_arc: "sparse verses, chorus opens up, stripped bridge, quiet final chorus"
    sections:
      - {tag: "Intro: solo Rhodes, 4 bars", energy: low}
      - {tag: "Verse 1", energy: low}
      - {tag: "Chorus", energy: high}
      ...
    story: "..."
    lyric_angle: "..."
    exclude: ["auto-tune", "EDM drop"]
    lyrics: |
      [Intro: solo Rhodes, 4 bars]
      ...
    techniques_testing: ["recording-space"]

BGM (instrumental cue) briefs set `kind: bgm`; `sections` is then the arrangement:

    kind: bgm
    cue_type: mass-hero-entry
    scene: "slow-motion hero walk out of the smoke, crowd erupting"
    duration_s: 120
    instrumental_method: tags        # tags (lyrics box = tags only) | toggle (Suno Instrumental switch)
    sections:
      - {tag: "Intro: lone thavil roll over a low drone, 4 bars", energy: low}
      - {tag: "Build: parai accelerating, riser, sub swells", energy: mid}
      - {tag: "Silence: 1 beat", energy: silence}
      - {tag: "Drop: full thavil and 808s, distorted bass, brass stabs, whistle hook", energy: peak}
      - {tag: "Outro: brass hit, ring out", energy: low}
      - {tag: "End"}
"""

from pathlib import Path

import yaml

REQUIRED = {
    "song": ["vibe", "title", "genre", "bpm", "sections", "lyrics"],
    # instrumental cue: `sections` is the arrangement (tags carry the description), lyrics optional
    "bgm": ["vibe", "title", "genre", "bpm", "sections"],
}
ENERGIES = {"silence", "low", "mid", "high", "peak"}
CUE_TYPES = {"mass-hero-entry", "villain", "action", "emotional"}


class BriefError(ValueError):
    pass


def load(path):
    data = yaml.safe_load(Path(path).read_text()) or {}
    validate(data)
    return data


def kind(b):
    """Brief type: 'song' (default) or 'bgm'. (`mode` is the key's major/minor.)"""
    return (b or {}).get("kind", "song")


def validate(b):
    if kind(b) not in REQUIRED:
        raise BriefError(f"kind must be one of {sorted(REQUIRED)}")
    if kind(b) == "bgm" and b.get("cue_type") and b["cue_type"] not in CUE_TYPES:
        raise BriefError(f"cue_type must be one of {sorted(CUE_TYPES)}")
    missing = [k for k in REQUIRED[kind(b)] if not b.get(k)]
    if missing:
        raise BriefError(f"brief is missing: {', '.join(missing)}")
    try:
        bpm = float(b["bpm"])
    except (TypeError, ValueError):
        raise BriefError("bpm must be a number")
    if not 40 <= bpm <= 220:
        raise BriefError("bpm should be between 40 and 220")
    if b.get("mode") and b["mode"] not in ("major", "minor"):
        raise BriefError("mode must be 'major' or 'minor'")
    for s in b["sections"]:
        if not isinstance(s, dict) or not s.get("tag"):
            raise BriefError("each section needs a tag, e.g. {tag: 'Verse 1', energy: low}")
        if s.get("energy") and s["energy"] not in ENERGIES:
            raise BriefError(f"section energy must be one of {sorted(ENERGIES)}")
    return b
