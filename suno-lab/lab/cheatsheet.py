"""Render the playbook into a one-page cheat sheet (Markdown)."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ORDER = ["proven", "testing", "lore", "busted"]
TITLES = {
    "proven": "Proven on our songs",
    "testing": "Being tested",
    "lore": "Untested lore (try these)",
    "busted": "Busted - didn't help",
}


def build():
    data = yaml.safe_load((ROOT / "playbook" / "techniques.yaml").read_text())
    by_status = {s: [] for s in ORDER}
    for t in data["techniques"]:
        by_status.setdefault(t.get("status", "lore"), []).append(t)
    out = ["# Suno Prompt Cheat Sheet", "",
           "Generated from `playbook/techniques.yaml`. Status changes as our rated songs pile up.", ""]
    for status in ORDER:
        items = by_status.get(status) or []
        if not items:
            continue
        out += [f"## {TITLES[status]}", ""]
        for t in items:
            ev = t.get("evidence") or []
            proof = ""
            if ev:
                r = sum(e["rating_delta"] for e in ev) / len(ev)
                proof = f" _(n={len(ev)}, avg rating {r:+.1f})_"
            out += [f"**{t['id']}** ({t['category']}){proof}  ",
                    f"{t['rule']}  ",
                    f"Do: `{t['example']}`  ",
                    f"Not: `{t['anti_example']}`", ""]
    path = ROOT / "playbook" / "CHEATSHEET.md"
    path.write_text("\n".join(out))
    return path
