"""Diagnostic plots (PNG) that Claude reads to see the song."""

import matplotlib

matplotlib.use("Agg")
import librosa  # noqa: E402
import librosa.display  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .audio import ANALYSIS_SR  # noqa: E402

COLORS = ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#72b7b2", "#b279a2", "#ff9da6", "#9d755d"]


def _shade_sections(ax, sections):
    labels = sorted({s["label"] for s in sections})
    for s in sections:
        c = COLORS[labels.index(s["label"]) % len(COLORS)]
        ax.axvspan(s["start"], s["end"], color=c, alpha=0.18, lw=0)
        ax.text((s["start"] + s["end"]) / 2, 0.97, f"{s['label']}\n{s['role_guess']}",
                transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=7)


def overview(path, y, sections, energy_times, energy_db, novelty_curve, beat_times, title):
    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1.6, 1]})
    S = librosa.feature.melspectrogram(y=y, sr=ANALYSIS_SR, n_mels=96, fmax=11000)
    librosa.display.specshow(librosa.power_to_db(S, ref=np.max), sr=ANALYSIS_SR, x_axis="time",
                             y_axis="mel", fmax=11000, ax=axes[0], cmap="magma")
    axes[0].set_title(f"{title} - mel spectrogram")
    for s in sections:
        axes[0].axvline(s["start"], color="white", lw=0.8, alpha=0.7)

    axes[1].plot(energy_times, energy_db, color="#333", lw=1)
    _shade_sections(axes[1], sections)
    axes[1].set_ylabel("RMS dB")
    axes[1].set_title("energy + detected sections (same letter = repeat)")

    nt = beat_times[:len(novelty_curve)]
    axes[2].plot(nt, novelty_curve, color="#e45756", lw=1)
    axes[2].set_ylabel("novelty")
    axes[2].set_xlabel("time (s)")
    for ax in axes:
        ax.set_xlim(0, len(y) / ANALYSIS_SR)
    fig.tight_layout()
    fig.savefig(path, dpi=80)
    plt.close(fig)


def similarity(path, ssm, beat_times, sections, title):
    fig, ax = plt.subplots(figsize=(7, 6.5))
    end = beat_times[min(len(beat_times) - 1, ssm.shape[0])]
    ax.imshow(ssm, origin="lower", cmap="viridis", extent=[0, end, 0, end], aspect="auto")
    for s in sections:
        ax.axvline(s["start"], color="white", lw=0.6, alpha=0.6)
        ax.axhline(s["start"], color="white", lw=0.6, alpha=0.6)
    ax.set_title(f"{title} - self-similarity (bright diagonals off the middle = repeats)")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("time (s)")
    fig.tight_layout()
    fig.savefig(path, dpi=80)
    plt.close(fig)
