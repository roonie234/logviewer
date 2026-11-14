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
"""

from pathlib import Path

import yaml

REQUIRED = ["vibe", "title", "genre", "bpm", "sections", "lyrics"]
ENERGIES = {"low", "mid", "high"}


class BriefError(ValueError):
    pass


def load(path):
    data = yaml.safe_load(Path(path).read_text()) or {}
    validate(data)
    return data


def validate(b):
    missing = [k for k in REQUIRED if not b.get(k)]
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
