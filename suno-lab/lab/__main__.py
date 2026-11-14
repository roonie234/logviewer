"""suno-lab command line.

  python -m lab fetch    sessions/<song>/v1 <link> [<link> ...]   pull songs (+ the prompt Suno used)
  python -m lab prompt   sessions/<song>/v1                       brief.yaml -> prompt.md (+ lint)
  python -m lab lint     sessions/<song>/v1 | --text "lyrics" --style "..."
  python -m lab analyze  sessions/<song>/v1 [--ears]              -> report.md, metrics.json, plots/
  python -m lab rate     sessions/<song>/v1 a=4 b=2 [--note "..."] log ratings, update playbook
  python -m lab profile  build mass-hero references/mass-hero [--ears]   measure reference tracks -> profile
  python -m lab analyze  sessions/<cue>/v1 --kind bgm --profile mass-hero [--ears]
  python -m lab cheatsheet                                        playbook -> CHEATSHEET.md
"""

import argparse
import json
import string
import sys
from pathlib import Path

from . import analyze, brief, cheatsheet, experiment, fetch, lint, prompt


def cmd_fetch(a):
    out = Path(a.version_dir)
    existing = {p.stem.split(".")[0] for p in out.glob("*.clip.json")} if out.exists() else set()
    labels = [l for l in string.ascii_lowercase if l not in existing]
    for link, label in zip(a.links, labels):
        try:
            info = fetch.fetch(link, out, label)
        except fetch.FetchError as e:
            print(f"[{label}] FAILED: {e}", file=sys.stderr)
            continue
        head = f"[{label}] {info['title']} - {info['model_version'] or info['model_name']} - {info['duration']}s"
        if info["audio_file"]:
            print(f"{head} -> {info['audio_file']}")
        else:
            print(f"{head} -> prompt/lyrics saved, but NO downloadable audio (download disabled or protected). "
                  f"Add the MP3 to {out} as {label}.mp3 to analyze it.")


def cmd_prompt(a):
    vd = Path(a.version_dir)
    b = brief.load(vd / "brief.yaml")
    p = prompt.build(b)
    (vd / "prompt.md").write_text(prompt.to_markdown(p, b, vd.name))
    (vd / "prompt.json").write_text(json.dumps({k: v for k, v in p.items() if k != "lint"}, indent=2, ensure_ascii=False))
    print(prompt.to_markdown(p, b, vd.name))


def cmd_lint(a):
    if a.version_dir:
        b = brief.load(Path(a.version_dir) / "brief.yaml")
        p = prompt.build(b)
        print(lint.format_findings(p["lint"]))
    else:
        print(lint.format_findings(lint.lint(a.text or "", a.style or "", a.exclude or "")))


def cmd_analyze(a):
    results = analyze.analyze_version(a.version_dir, ears=a.ears, kind=a.kind, profile_name=a.profile)
    for label, m in results.items():
        print(f"[{label}] humanness {m['humanness']['score']}/100, {m['basics']['bpm']} BPM, "
              f"{m['basics']['key']} {m['basics']['mode']}, {len(m['structure']['sections'])} sections")
    print(f"report: {Path(a.version_dir) / 'report.md'}")


def cmd_rate(a):
    ratings = {}
    for item in a.ratings:
        label, _, val = item.partition("=")
        if not val.isdigit() or not 1 <= int(val) <= 5:
            raise SystemExit(f"bad rating {item!r}; use like a=4 (1-5)")
        ratings[label] = int(val)
    for tid, old, new in experiment.rate(a.version_dir, ratings, a.note or ""):
        print(f"{tid}: {old} -> {new}")
    print("logged.")


def cmd_profile(a):
    from . import profile
    if a.action == "show":
        print(profile.show(a.name))
        return
    if not a.ref_dir:
        raise SystemExit("usage: python -m lab profile build <name> <reference-folder> [--ears]")
    path, prof = profile.build(a.name, a.ref_dir, ears=a.ears)
    print(profile.show(a.name))
    print(f"saved {path}")


def cmd_cheatsheet(a):
    print(cheatsheet.build())


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m lab", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("fetch"); s.add_argument("version_dir"); s.add_argument("links", nargs="+"); s.set_defaults(fn=cmd_fetch)
    s = sub.add_parser("prompt"); s.add_argument("version_dir"); s.set_defaults(fn=cmd_prompt)
    s = sub.add_parser("lint"); s.add_argument("version_dir", nargs="?"); s.add_argument("--text"); s.add_argument("--style"); s.add_argument("--exclude"); s.set_defaults(fn=cmd_lint)
    s = sub.add_parser("analyze"); s.add_argument("version_dir"); s.add_argument("--ears", action="store_true", help="also run stem separation, sung-lyric transcription, CLAP description, vocal pitch (needs requirements-ears.txt)"); s.add_argument("--kind", choices=["song", "bgm"], help="override the brief's kind"); s.add_argument("--profile", help="compare with a reference profile, e.g. mass-hero"); s.set_defaults(fn=cmd_analyze)
    s = sub.add_parser("profile"); s.add_argument("action", choices=["build", "show"]); s.add_argument("name"); s.add_argument("ref_dir", nargs="?"); s.add_argument("--ears", action="store_true"); s.set_defaults(fn=cmd_profile)
    s = sub.add_parser("rate"); s.add_argument("version_dir"); s.add_argument("ratings", nargs="+"); s.add_argument("--note"); s.set_defaults(fn=cmd_rate)
    s = sub.add_parser("cheatsheet"); s.set_defaults(fn=cmd_cheatsheet)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
