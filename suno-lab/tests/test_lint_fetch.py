import json

from lab import fetch, lint, prompt

CLICHE_LYRICS = """[Verse]
Neon lights and echoes of the night
Shadows dance, we ignite the fire within
[Chorus]
We rise above, unbreakable tonight
Burning bright like embers in the wind
[Chorus]
We rise above, unbreakable tonight
Burning bright like embers in the wind
"""

HUMAN_LYRICS = """[Intro: solo Rhodes, 4 bars]
[Verse 1]
Your mum's blue Corolla's still got the dent
from the parking post outside Lidl
I didn't call. Well - I did.
Hung up on the second ring, like a coward, like a kid
[Chorus]
Exit fourteen, I almost took it
[Instrumental Break: harmonica, a bit out of breath]
[Chorus: half-time, just voice and claps]
Exit fourteen - this time I took it
[Outro: band drops out, guitar rings]
[End]
"""


def test_cliche_lyrics_flagged():
    r = lint.lint(CLICHE_LYRICS, "epic emotional pop", "")
    techniques = {f["technique"] for f in r["findings"]}
    assert r["cliche_per_100_words"] > 10
    assert {"concrete-specifics", "vary-the-repeat", "sound-not-adjectives", "designed-ending"} <= techniques


def test_genre_pileup_flagged():
    style = "Art-pop/indie-soul, deep-house sub bass, 8-bit details, 808 trap drums, drum-and-bass fills, riddim growls"
    assert any(f["technique"] == "focused-style" for f in lint.lint("", style, "")["findings"])


def test_human_lyrics_pass():
    style = "soft rock with Afrobeat guitar picking, Rhodes, brushed drums, recorded live in a small room, 92 BPM"
    r = lint.lint(HUMAN_LYRICS, style, "auto-tune")
    assert r["cliches"] == []
    assert not [f for f in r["findings"] if f["severity"] in ("warn", "error")], r["findings"]


def test_prompt_build_and_order_check():
    b = {"vibe": "x", "title": "Exit 14", "genre": "soft rock", "bpm": 92, "key": "A", "mode": "major",
         "sections": [{"tag": "Intro"}, {"tag": "Verse 1"}, {"tag": "Chorus"}, {"tag": "Instrumental Break"},
                      {"tag": "Chorus"}, {"tag": "Outro"}, {"tag": "End"}],
         "lyrics": HUMAN_LYRICS, "exclude": ["auto-tune"]}
    p = prompt.build(b)
    assert "92 BPM, A major" in p["style"]
    assert not any("order" in f["message"] for f in p["lint"]["findings"])
    b["sections"] = b["sections"][::-1]
    assert any("order" in f["message"] for f in prompt.build(b)["lint"]["findings"])


def _page(song_id):
    clip = {"id": song_id, "title": "Test Song", "status": "complete", "model_name": "chirp-x",
            "major_model_version": "v9", "audio_url": "https://studio-api.prod.suno.com/api/forbidden",
            "media_urls": [{"url": f"https://cdn.example/{song_id}.m4a"}],
            "metadata": {"tags": "delta blues, slide guitar", "prompt": "$c5", "duration": 61.0,
                         "make_instrumental": False}}
    lyrics = "[Verse]\nhello é world\n"
    flight = '1:["$","div",null,' + json.dumps({"clip": clip}) + "]\n" + \
             f"c5:T{len(lyrics.encode()):x}," + lyrics + '2:["x"]\n'
    return f'<script>self.__next_f.push([1,{json.dumps(flight)}])</script>'


def test_find_clip_resolves_lyrics():
    sid = "f0f00357-0cd7-4fd5-96e5-d9314439f4e5"
    clip = fetch.find_clip(_page(sid), sid)
    info = fetch.clip_summary(clip, "https://suno.com/song/" + sid)
    assert info["lyrics"] == "[Verse]\nhello é world\n"
    assert info["style"] == "delta blues, slide guitar"
    assert info["audio_candidates"] == [f"https://cdn1.suno.ai/{sid}.mp3"]  # encrypted player stream is never used
    assert info["model_version"] == "v9"


def test_song_id_from_link():
    assert fetch.song_id_from("https://suno.com/song/f0f00357-0cd7-4fd5-96e5-d9314439f4e5?sh=abc") == "f0f00357-0cd7-4fd5-96e5-d9314439f4e5"
    assert fetch.song_id_from("https://suno.com/s/AbCdEf") is None
