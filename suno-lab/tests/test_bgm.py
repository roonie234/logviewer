import pytest
import soundfile as sf

from lab import brief as brief_mod
from lab import lint, profile, prompt
from lab.analyze import analyze_clip
from tests import synth


@pytest.fixture(scope="module")
def cues(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("bgm")
    out = {}
    for name, kw in {"drop": dict(drop=True), "flat": dict(drop=False)}.items():
        p = tmp / f"{name}.wav"
        sf.write(p, synth.bgm(**kw), synth.SR)
        out[name] = analyze_clip(p, {}, {"kind": "bgm"}, kind="bgm")
    return out


def test_drop_found_with_pause(cues):
    b = cues["drop"]["bgm"]
    assert abs(b["drop"]["time_s"] - 28.5) < 1.0, b["drop"]
    assert b["drop"]["lift_db"] > 6
    assert b["pause"]["present"], b["pause"]
    assert b["build"]["rises"]
    assert b["impact"]["sub_share_drop"] > b["impact"]["sub_share_build"]


def test_flat_cue_scores_worse(cues):
    d, f = cues["drop"], cues["flat"]
    assert f["humanness"]["signals"]["weak_drop"]["score"] > d["humanness"]["signals"]["weak_drop"]["score"]
    assert f["humanness"]["score"] < d["humanness"]["score"]
    # vocal/grid signals are switched off for BGMs
    assert d["kind"] == "bgm"


def test_profile_build_and_compare(tmp_path, cues):
    refs = tmp_path / "refs"
    refs.mkdir()
    for i, (seed, bpm, at) in enumerate([(2, 138, 27.0), (3, 142, 29.0), (4, 140, 30.0)]):
        sf.write(refs / f"r{i}.wav", synth.bgm(drop=True, seed=seed, bpm=bpm, drop_at=at), synth.SR)
    path, prof = profile.build("test-mass", refs, out_dir=tmp_path / "profiles")
    assert path.exists() and prof["n_references"] == 3
    assert "drop_lift_db" in prof["metrics"] and "pause_length_s" in prof["metrics"]

    good = profile.compare(cues["drop"], prof)
    bad = profile.compare(cues["flat"], prof)
    status = lambda c, k: next(r["status"] for r in c["rows"] if r["key"] == k)
    assert status(good, "pause_length_s") == "ok"
    assert status(bad, "drop_lift_db") == "low"
    assert status(bad, "pause_length_s") == "low"


GOOD_BGM = {
    "kind": "bgm", "vibe": "hero walks out of the smoke", "title": "Smoke Walk", "cue_type": "mass-hero-entry",
    "genre": "Tamil mass film score", "twist": "trap 808s and distorted synth bass", "bpm": 140,
    "scene": "slow-motion hero walk out of the smoke, crowd erupting",
    "instrumentation": ["thavil and parai drums", "heroic brass stabs on the off-beat", "whistle lead hook"],
    "exclude": ["vocals", "singing", "lyrics"],
    "sections": [
        {"tag": "Intro: lone thavil roll over a low drone, 4 bars", "energy": "low"},
        {"tag": "Build: parai accelerating, riser, sub swells", "energy": "mid"},
        {"tag": "Silence: 1 beat", "energy": "silence"},
        {"tag": "Drop: full thavil and 808s, distorted bass, brass stabs, whistle hook", "energy": "peak"},
        {"tag": "Outro: brass hit, ring out", "energy": "low"},
        {"tag": "End"},
    ],
}


def test_bgm_brief_valid_without_lyrics():
    brief_mod.validate(dict(GOOD_BGM))
    with pytest.raises(brief_mod.BriefError):
        brief_mod.validate({**GOOD_BGM, "kind": "film"})


def test_bgm_prompt_is_tags_only_and_clean():
    p = prompt.build(dict(GOOD_BGM))
    assert p["lyrics"].startswith("[Intro: lone thavil roll")
    assert all(l.startswith("[") for l in p["lyrics"].splitlines() if l.strip())
    assert "instrumental, no vocals" in p["style"] and "140 BPM" in p["style"]
    assert not [f for f in p["lint"]["findings"] if f["severity"] in ("warn", "error")], p["lint"]["findings"]


def test_bgm_toggle_method_folds_arrangement_into_style():
    p = prompt.build({**GOOD_BGM, "instrumental_method": "toggle"})
    assert p["lyrics"] == "" and "structure: intro -> build -> silence -> drop -> outro" in p["style"]


def test_bgm_lint_flags_artist_and_missing_pause():
    r = lint.lint("[Intro]\n[Build]\n[Drop]\nhey hey\n", "Anirudh style mass bgm, 140 BPM", "", mode="bgm")
    techs = {f["technique"] for f in r["findings"]}
    assert {"describe-dont-name-artists", "silence-before-drop", "designed-ending",
            "name-indian-percussion", "instrumental-method"} <= techs


def test_song_brief_still_uses_mode_for_key():
    p = prompt.build({"vibe": "x", "title": "t", "genre": "soft rock", "bpm": 92, "key": "A", "mode": "major",
                      "sections": [{"tag": "Verse"}], "lyrics": "[Verse]\nhello there\n"})
    assert "92 BPM, A major" in p["style"]
