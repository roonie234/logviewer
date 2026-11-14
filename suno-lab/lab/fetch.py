"""Fetch a Suno song from its public link: audio stream + the exact prompt used.

A public song page (https://suno.com/song/<id>, or a short https://suno.com/s/<code>
share link) embeds the clip record: title, model, style ("tags"), lyrics and the
stream URL the web player uses. We read that, so the user only pastes links.
"""

import json
import re
import subprocess
from pathlib import Path

import httpx

UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) suno-lab/0.1"}


class FetchError(Exception):
    pass


def song_id_from(text):
    m = re.search(UUID, text or "")
    return m.group(0) if m else None


def _flight_data(html):
    """Concatenate the Next.js RSC payload pushed via self.__next_f.push([1, "..."])."""
    parts = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html)
    return "".join(json.loads(f'"{p}"') for p in parts)


def _resolve_text_ref(flight, ref):
    """Resolve an RSC text reference like "$c5" -> the long string chunk `c5:T<hexlen>,<text>`."""
    if not (isinstance(ref, str) and ref.startswith("$") and len(ref) > 1):
        return ref
    m = re.search(r"(?:^|\n|\})%s:T([0-9a-f]+)," % re.escape(ref[1:]), flight)
    if not m:
        return None
    n = int(m.group(1), 16)
    return flight[m.end():].encode("utf-8")[:n].decode("utf-8", "ignore")


def find_clip(html, song_id):
    """Locate the clip dict for `song_id` inside the page payload."""
    flight = _flight_data(html)
    dec = json.JSONDecoder()
    for m in re.finditer(r'"id"\s*:\s*"%s"' % re.escape(song_id), flight):
        for start in range(m.start(), max(0, m.start() - 30000), -1):
            if flight[start] != "{":
                continue
            try:
                obj, _ = dec.raw_decode(flight, start)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("id") == song_id and "metadata" in obj:
                md = obj.get("metadata") or {}
                for key in ("prompt", "tags", "negative_tags", "gpt_description_prompt"):
                    if key in md:
                        md[key] = _resolve_text_ref(flight, md[key])
                return obj
    return None


def _audio_candidates(clip):
    """Plain, directly downloadable audio files only (owner-enabled audio_url, public CDN mp3).
    The web player's encrypted stream (media_urls) is deliberately not used."""
    out = []
    url = clip.get("audio_url")
    if isinstance(url, str) and url.startswith("https://") and "forbidden" not in url:
        out.append(url)
    if clip.get("id"):
        out.append(f"https://cdn1.suno.ai/{clip['id']}.mp3")
    return list(dict.fromkeys(out))


def _decodable(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return r.returncode == 0 and "audio" in r.stdout


def clip_summary(clip, link):
    md = clip.get("metadata") or {}
    return {
        "id": clip.get("id"),
        "link": link,
        "title": clip.get("title"),
        "model_name": clip.get("model_name"),
        "model_version": clip.get("major_model_version"),
        "style": md.get("tags") or "",
        "exclude": md.get("negative_tags") or "",
        "lyrics": md.get("prompt") or "",
        "description_prompt": md.get("gpt_description_prompt") or "",
        "instrumental": bool(md.get("make_instrumental")),
        "type": md.get("type"),
        "duration": md.get("duration"),
        "created_at": clip.get("created_at"),
        "status": clip.get("status"),
        "audio_candidates": _audio_candidates(clip),
    }


def fetch(link, out_dir, label, client=None):
    """Download one song into out_dir as <label>.<ext> + <label>.clip.json."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    own = client is None
    client = client or httpx.Client(headers=UA, timeout=60, follow_redirects=True)
    try:
        page = client.get(link if link.startswith("http") else f"https://suno.com/song/{link}")
        if page.status_code != 200:
            raise FetchError(f"{link}: song page returned HTTP {page.status_code}")
        song_id = song_id_from(link) or song_id_from(str(page.url))
        if not song_id:
            raise FetchError(f"{link}: could not find a song id in the link")
        clip = find_clip(page.text, song_id)
        if clip is None:
            raise FetchError(f"{link}: song data not found on the page (is the song public?)")
        info = clip_summary(clip, link)
        if info["status"] not in (None, "complete"):
            raise FetchError(f"{link}: song is still {info['status']}, try again when it finishes")
        (out_dir / f"{label}.clip.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))

        info["audio_file"] = None
        for url in info["audio_candidates"]:
            ext = Path(url.split("?")[0]).suffix or ".mp3"
            audio_path = out_dir / f"{label}{ext}"
            with client.stream("GET", url) as r:
                if r.status_code != 200:
                    continue
                with open(audio_path, "wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
            if _decodable(audio_path):
                info["audio_file"] = audio_path.name
                break
            audio_path.unlink(missing_ok=True)
        (out_dir / f"{label}.clip.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
        return info
    finally:
        if own:
            client.close()
