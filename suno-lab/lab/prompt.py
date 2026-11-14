"""Brief -> copy-paste Suno prompt (Title / Style / Exclude / Lyrics) + lint report."""

from . import lint as lint_mod
from .lint import parse_lyrics, _section_kind


def style_from(brief):
    if brief.get("kind") == "bgm":
        return bgm_style_from(brief)
    parts = [brief["genre"]]
    if brief.get("twist"):
        parts[0] = f"{brief['genre']} with {brief['twist']}"
    parts += list(brief.get("instrumentation") or [])
    for key in ("production", "vocals", "energy_arc"):
        if brief.get(key):
            parts.append(brief[key])
    tempo = f"{int(float(brief['bpm']))} BPM"
    if brief.get("key"):
        tempo += f", {brief['key']} {brief.get('mode', '')}".rstrip()
    parts.append(tempo)
    return ", ".join(p.strip().rstrip(",") for p in parts if p and p.strip())


def bgm_style_from(brief):
    parts = [brief["genre"]]
    if brief.get("twist"):
        parts[0] = f"{brief['genre']} fused with {brief['twist']}"
    parts.append("instrumental, no vocals")
    if brief.get("scene"):
        parts.append(f"scene: {brief['scene']}")
    parts += list(brief.get("instrumentation") or [])
    for key in ("production", "energy_arc"):
        if brief.get(key):
            parts.append(brief[key])
    if brief.get("instrumental_method") == "toggle":
        # with the Instrumental switch on there is no lyrics box: fold the arrangement into the style
        arc = " -> ".join(s["tag"].split(":")[0].strip().lower() for s in brief["sections"] if s["tag"].lower() != "end")
        parts.append(f"structure: {arc}")
    tempo = f"{int(float(brief['bpm']))} BPM"
    if brief.get("key"):
        tempo += f", {brief['key']} {brief.get('mode', '')}".rstrip()
    parts.append(tempo)
    return ", ".join(p.strip().rstrip(",") for p in parts if p and p.strip())


def bgm_lyrics_from(brief):
    """Arrangement tags only - the tag descriptions carry the instructions, no sung words."""
    return "\n\n".join(f"[{s['tag']}]" for s in brief["sections"])


def section_order_check(brief):
    if brief.get("kind") == "bgm":
        return None
    planned = [_section_kind(s["tag"]) for s in brief["sections"]]
    written = [_section_kind(s["tag"]) for s in parse_lyrics(brief["lyrics"]) if s["tag"]]
    if [p for p in planned if p != "end"] != [w for w in written if w != "end"]:
        return f"Lyrics section order {written} differs from the brief plan {planned}."
    return None


def build(brief):
    style = brief.get("style_override") or style_from(brief)
    exclude = ", ".join(brief.get("exclude") or [])
    if brief.get("kind") == "bgm":
        lyrics = (brief.get("lyrics") or bgm_lyrics_from(brief)).strip()
        if brief.get("instrumental_method") == "toggle":
            lyrics = ""
    else:
        lyrics = brief["lyrics"].strip()
    result = lint_mod.lint(lyrics, style, exclude, brief.get("title", ""), brief)
    order = section_order_check(brief)
    if order:
        result["findings"].insert(0, {"severity": "warn", "technique": "explicit-sections", "message": order})
    return {"title": brief["title"], "style": style, "exclude": exclude, "lyrics": lyrics, "lint": result}


def suno_switches(brief):
    if brief.get("kind") != "bgm":
        return "Custom mode."
    if brief.get("instrumental_method") == "toggle":
        return "Custom mode, **Instrumental: ON** (no lyrics box; the arrangement is folded into the style)."
    return "Custom mode, **Instrumental: OFF**, and the lyrics box holds only the [tags] below (no words)."


def to_markdown(p, brief, version):
    testing = ", ".join(brief.get("techniques_testing") or []) or "-"
    return f"""# {brief['title']} - {version}

Vibe: {brief['vibe']}
Testing techniques: {testing}

Paste into Suno - {suno_switches(brief)}

**Title**
```
{p['title']}
```

**Style of Music** ({len(p['style'])} chars)
```
{p['style']}
```

**Exclude Styles**
```
{p['exclude'] or '(none)'}
```

**Lyrics** ({len(p['lyrics'])} chars)
```
{p['lyrics'] or '(none - Instrumental switch on)'}
```

## Lint
```
{lint_mod.format_findings(p['lint'])}
```
"""
