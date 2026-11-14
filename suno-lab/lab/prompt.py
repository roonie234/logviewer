"""Brief -> copy-paste Suno prompt (Title / Style / Exclude / Lyrics) + lint report."""

from . import lint as lint_mod
from .lint import parse_lyrics, _section_kind


def style_from(brief):
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


def section_order_check(brief):
    planned = [_section_kind(s["tag"]) for s in brief["sections"]]
    written = [_section_kind(s["tag"]) for s in parse_lyrics(brief["lyrics"]) if s["tag"]]
    if [p for p in planned if p != "end"] != [w for w in written if w != "end"]:
        return f"Lyrics section order {written} differs from the brief plan {planned}."
    return None


def build(brief):
    style = brief.get("style_override") or style_from(brief)
    exclude = ", ".join(brief.get("exclude") or [])
    result = lint_mod.lint(brief["lyrics"], style, exclude, brief.get("title", ""), brief)
    order = section_order_check(brief)
    if order:
        result["findings"].insert(0, {"severity": "warn", "technique": "explicit-sections", "message": order})
    return {"title": brief["title"], "style": style, "exclude": exclude, "lyrics": brief["lyrics"].strip(), "lint": result}


def to_markdown(p, brief, version):
    testing = ", ".join(brief.get("techniques_testing") or []) or "-"
    return f"""# {brief['title']} - {version}

Vibe: {brief['vibe']}
Testing techniques: {testing}

Paste into Suno (Custom mode):

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
{p['lyrics']}
```

## Lint
```
{lint_mod.format_findings(p['lint'])}
```
"""
