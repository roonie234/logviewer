"""Pure-logic tests for the ears (no models needed)."""

from lab.ears import lyrics
from lab.ears.describe import style_descriptors

WRITTEN = """[Verse]
Petrol station coffee gone cold by the bridge
your hair tie still looped on the gear stick
[Chorus]
Exit fourteen I know every turn
I keep driving on
[Chorus]
Exit fourteen I know every turn
I keep driving on
"""


def _words(text, start=0.0, prob=0.9):
    out, t = [], start
    for w in text.split():
        out.append({"word": w, "start": t, "end": t + 0.3, "prob": prob})
        t += 0.4
    return out


def test_perfect_performance():
    heard = _words("petrol station coffee gone cold by the bridge your hair tie still looped on the gear stick "
                   "exit fourteen I know every turn I keep driving on exit fourteen I know every turn I keep driving on")
    c = lyrics.compare(WRITTEN, heard)
    assert c["heard_ratio"] == 1.0
    assert [s["section"] for s in c["sections"]] == ["Verse", "Chorus", "Chorus"]
    assert c["mismatches"] == []


def test_slurred_second_chorus_is_located():
    heard = _words("petrol station coffee gone cold by the bridge your hair tie still looped on the gear stick "
                   "exit fourteen I know every turn I keep driving on") + \
            _words("ex it for tin a know very tern I keep driving on", start=20.0, prob=0.3)
    c = lyrics.compare(WRITTEN, heard)
    assert c["heard_ratio"] < 0.9
    second = c["sections"][-1]
    assert second["section"] == "Chorus" and second["ok"] < second["lines"]
    assert any(m["time"] >= 20 for m in c["mismatches"])
    assert c["mumbled_words"] >= 10


def test_backing_vocals_not_required():
    c = lyrics.compare("[Outro]\nkeep driving on (keep driving)\n", _words("keep driving on"))
    assert c["heard_ratio"] == 1.0


def test_style_descriptors_skip_tempo_and_key():
    assert style_descriptors("soft rock, Rhodes, 92 BPM, A major, tape hiss") == ["soft rock", "Rhodes", "tape hiss"]
