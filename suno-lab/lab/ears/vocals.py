"""Vocal performance from the isolated vocal stem: pitch precision, vibrato, range, how much is sung."""

import numpy as np

SR = 22050
HOP = 256


def analyze(vocals_44k):
    import librosa

    y = librosa.resample(vocals_44k, orig_sr=44100, target_sr=SR, res_type="soxr_hq")
    f0, voiced, _ = librosa.pyin(y, fmin=70, fmax=1100, sr=SR, hop_length=HOP, frame_length=2048)
    f0 = np.where(voiced, f0, np.nan)
    sung = np.isfinite(f0)
    if sung.sum() < 200:
        return {"sung_ratio": round(float(sung.mean()), 3), "note": "Too little singing detected to judge pitch."}

    midi = librosa.hz_to_midi(f0[sung])
    tuning = float(np.median((midi - np.round(midi)) * 100))  # global tuning offset in cents
    cents = (midi - np.round(midi)) * 100 - tuning
    cents = (cents + 50) % 100 - 50

    # stable frames only (not slides between notes): small local pitch change
    d = np.abs(np.diff(midi, prepend=midi[0])) * 100
    stable = d < 15
    dev = float(np.median(np.abs(cents[stable]))) if stable.sum() > 50 else None

    # vibrato: 4-8 Hz modulation depth on longer sustained notes
    fps = SR / HOP
    depths = []
    run = []
    for v in np.concatenate([np.where(stable, midi, np.nan), [np.nan]]):
        if np.isfinite(v):
            run.append(v)
            continue
        if len(run) > fps * 0.6:
            seg = np.array(run) - np.mean(run)
            spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
            freqs = np.fft.rfftfreq(len(seg), 1 / fps)
            band = (freqs >= 4) & (freqs <= 8)
            if band.any() and spec[band].max() > 1.5 * np.median(spec[1:] + 1e-9):
                depths.append(float(np.std(seg) * 100))
        run = []
    lo, hi = np.percentile(midi, [5, 95])
    return {
        "sung_ratio": round(float(sung.mean()), 3),
        "pitch_offset_cents_median": None if dev is None else round(dev, 1),
        "vibrato_notes": len(depths),
        "vibrato_depth_cents": round(float(np.median(depths)), 1) if depths else None,
        "range": f"{librosa.midi_to_note(lo)}-{librosa.midi_to_note(hi)}",
        "range_semitones": round(float(hi - lo), 1),
    }


def report_lines(v):
    if "note" in v:
        return [v["note"]]
    dev = v["pitch_offset_cents_median"]
    feel = ("snapped to the note grid (auto-tune-like)" if dev is not None and dev < 8
            else "natural pitch drift" if dev is not None and dev > 15 else "fairly tight")
    return [
        f"Sung {v['sung_ratio']:.0%} of the time; range {v['range']} ({v['range_semitones']} semitones).",
        f"Median distance from exact pitch on held notes: {dev} cents -> {feel}.",
        f"Vibrato on {v['vibrato_notes']} held notes" + (f", depth ~{v['vibrato_depth_cents']} cents." if v["vibrato_depth_cents"] else "."),
    ]
