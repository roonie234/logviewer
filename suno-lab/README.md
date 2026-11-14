# Suno Lab - the Suno Prompt Cheat Engine

Give it one vibe line. It writes the Suno prompt, analyzes what Suno makes, says where it went
wrong (structure, style, "sounds AI"), and learns which prompt techniques actually make your
songs sound more human, based on your own ears.

```
vibe line ──> brief.yaml ──> prompt.md (copy into Suno) ──> you generate 2 clips
   ▲                                                          │
   │                                                     paste links
   │                                                          ▼
playbook learns <── you rate 1-5 <── report.md + plots <── fetch + analyze
```

## The loop
1. **You:** one vibe line, e.g. *"my grandma's kitchen in monsoon"*.
2. **Claude:** expands it into `sessions/<song>/v1/brief.yaml` (genre + twist, tempo, key,
   instruments, recording space, voice, section plan, story, lyrics) and shows you a 3-line
   direction. Say "go" or redirect in a few words.
3. `python -m lab prompt sessions/<song>/v1` writes `prompt.md`: Title / Style / Exclude / Lyrics,
   ready to paste into Suno's Custom mode, already linted for clichés and AI giveaways.
4. **You:** generate on suno.com, then paste the two song links back.
5. `python -m lab fetch sessions/<song>/v1 <link-a> <link-b>` saves the exact style, lyrics and
   model Suno used, plus the audio when Suno offers a plain download (see *Audio* below).
6. `python -m lab analyze sessions/<song>/v1` writes `report.md`, `metrics.json` and `plots/`.
   Claude reads them and tells you the top problems with timestamps.
7. **You:** listen and rate: `python -m lab rate sessions/<song>/v1 a=4 b=2 --note "chorus too polite"`.
8. Claude writes v2, changing one or two things at a time. Ratings feed the playbook.

## What gets measured
| Area | Checks |
|---|---|
| Style | BPM (and drift), key/mode, loudness (LUFS), loudness range, brightness, bandwidth vs the brief |
| Structure | detected sections + repeats (A/B/C), intro length, chorus lift, ending (abrupt / fade / clean) |
| Humanness 0-100 | copy-paste repeats, flat dynamics, static arrangement, 4-chord autopilot, grid-locked timing, hissy top end, lyric clichés |

### The ears (`--ears`)
`python -m lab analyze sessions/<song>/v1 --ears` adds model-based listening (about a minute per
song on CPU; first run downloads ~2 GB of models; install `requirements-ears.txt`):

| Ear | Model | What it tells you |
|---|---|---|
| Stems | Hybrid Demucs (torchaudio) | which instruments play when; sections where nothing drops out or builds |
| Lyrics | Whisper small, on the vocal stem | where each written section is actually sung, lines that were slurred, skipped or invented, word confidence |
| Describe | CLAP (`larger_clap_music_and_speech`) | what it sounds like in words; **which Style-prompt descriptors Suno ignored**; what changes per section |
| Vocals | pYIN pitch on the vocal stem | auto-tune-like pitch snapping vs natural drift, vibrato, range |

The describe ear judges phrases relative to `playbook/clap_reference.json` (seeded with free
example tracks); every analyzed song is added to it, so descriptions sharpen as you go.
The ears add two humanness signals: `slurred_lyrics` and `pitch_snapped_vocals`.

Deliberately not included: AI-music detectors. The goal is songs that sound better to a
listener, not songs tuned to slip past AI-content labelling.

Humanness signals are heuristics, shown with their evidence, not verdicts. Their weights live in
`playbook/weights.yaml` (create it to override) and get calibrated against your ratings.

## The playbook
`playbook/techniques.yaml` holds every prompt technique with a status:
**lore** (untested) -> **testing** -> **proven** / **busted**. Each brief lists the 1-2
techniques it tests (`techniques_testing`). When you rate a version, the change vs the
previous version is credited to those techniques. After 3+ results a technique is promoted or
busted. `python -m lab cheatsheet` renders `playbook/CHEATSHEET.md`.

Also: `playbook/cliches.yaml` (AI-lyric clichés, empty style words, genre list) and
`playbook/tags.md` (section/delivery tag reference).

## Audio: what works and what doesn't
- **Song links always give** the title, model version, the exact Style, Exclude and Lyrics used.
- **Audio from a link** only works when Suno serves a plain file for that song (an enabled
  `audio_url` or the public CDN MP3). The web player's stream is **encrypted** and suno-lab
  deliberately does not touch it.
- If a link has no plain audio, drop the MP3 into the version folder as `a.mp3` / `b.mp3`
  (or share a Google Drive folder with Claude) and run `analyze` again.
- Fully automatic option: a sunoapi.org key (third-party, separate credits), not built yet.

Audio files are git-ignored; reports, metrics, plots, briefs and ratings are kept.

## Setup
```
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt     # also needs ffmpeg on PATH
python -m pytest -q                 # synthetic-audio + linter tests
```

`sessions/example-exit-14/v1` is a worked example of a brief and its generated prompt.
