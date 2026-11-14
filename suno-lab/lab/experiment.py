"""Ratings + playbook learning.

`rate` stores the user's 1-5 ratings for a version, appends to the session log,
and credits/blames the techniques that version was testing by comparing it with
the previous version (best clip vs best clip).
"""

import json
import re
from datetime import date
from pathlib import Path

import yaml

PLAYBOOK = Path(__file__).resolve().parent.parent / "playbook" / "techniques.yaml"
MIN_EVIDENCE = 3


def _vnum(path):
    m = re.search(r"v(\d+)$", Path(path).name)
    return int(m.group(1)) if m else None


def _best(version_dir):
    """(best rating, humanness of that clip) for a rated version, else None."""
    version_dir = Path(version_dir)
    rp, mp = version_dir / "rating.json", version_dir / "metrics.json"
    if not rp.exists():
        return None
    ratings = json.loads(rp.read_text())["ratings"]
    metrics = json.loads(mp.read_text()) if mp.exists() else {}
    label = max(ratings, key=ratings.get)
    hum = (metrics.get(label) or {}).get("humanness", {}).get("score")
    return ratings[label], hum


def status_for(evidence):
    if len(evidence) < MIN_EVIDENCE:
        return "testing"
    r = sum(e["rating_delta"] for e in evidence) / len(evidence)
    hs = [e["humanness_delta"] for e in evidence if e.get("humanness_delta") is not None]
    h = sum(hs) / len(hs) if hs else 0
    if r >= 0.5 and h >= -2:
        return "proven"
    if r <= -0.5:
        return "busted"
    return "testing"


def rate(version_dir, ratings, note=""):
    version_dir = Path(version_dir)
    session = version_dir.parent
    (version_dir / "rating.json").write_text(json.dumps({"ratings": ratings, "note": note}, indent=2, ensure_ascii=False))

    brief_path = version_dir / "brief.yaml"
    tested = []
    if brief_path.exists():
        tested = (yaml.safe_load(brief_path.read_text()) or {}).get("techniques_testing") or []

    log = session / "log.md"
    entry = [f"\n## {version_dir.name} - rated {date.today().isoformat()}",
             f"Ratings: {', '.join(f'{k}={v}' for k, v in ratings.items())}"]
    if note:
        entry.append(f"Note: {note}")

    n = _vnum(version_dir)
    prev = session / f"v{n - 1}" if n and n > 1 else None
    cur, base = _best(version_dir), _best(prev) if prev else None
    updates = []
    if tested and cur and base:
        r_delta = cur[0] - base[0]
        h_delta = None if cur[1] is None or base[1] is None else cur[1] - base[1]
        entry.append(f"vs {prev.name}: rating {r_delta:+}, humanness {h_delta if h_delta is None else f'{h_delta:+}'}; tested: {', '.join(tested)}")
        updates = record_evidence(tested, session.name, version_dir.name, r_delta, h_delta)
    elif tested:
        entry.append(f"Tested {', '.join(tested)} (no rated previous version to compare with yet).")
    with open(log, "a") as f:
        f.write("\n".join(entry) + "\n")
    return updates


def record_evidence(technique_ids, song, version, rating_delta, humanness_delta):
    data = yaml.safe_load(PLAYBOOK.read_text())
    changed = []
    for t in data["techniques"]:
        if t["id"] not in technique_ids:
            continue
        t.setdefault("evidence", [])
        t["evidence"] = [e for e in t["evidence"] if not (e["song"] == song and e["version"] == version)]
        t["evidence"].append({"song": song, "version": version, "rating_delta": rating_delta, "humanness_delta": humanness_delta})
        old, t["status"] = t.get("status"), status_for(t["evidence"])
        changed.append((t["id"], old, t["status"]))
    header = PLAYBOOK.read_text().split("\ntechniques:")[0]
    PLAYBOOK.write_text(header + "\n" + yaml.safe_dump({"techniques": data["techniques"]}, sort_keys=False, allow_unicode=True, width=120))
    return changed
