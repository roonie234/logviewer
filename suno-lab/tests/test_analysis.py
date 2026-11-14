import soundfile as sf
import pytest

from lab.analyze import analyze_clip
from tests import synth


def _write(tmp_path, name, y):
    p = tmp_path / f"{name}.wav"
    sf.write(p, y, synth.SR)
    return p


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("songs")
    out = {}
    for name, kw in {
        "dynamic_exact": dict(dynamic=True, exact_repeat=True),
        "flat_exact": dict(dynamic=False, exact_repeat=True),
        "dynamic_varied": dict(dynamic=True, exact_repeat=False),
    }.items():
        out[name] = analyze_clip(_write(tmp, name, synth.song(**kw)), plots_dir=tmp / "plots", label=name)
    return out


def test_tempo(results):
    bpm = results["dynamic_exact"]["basics"]["bpm"]
    assert any(abs(bpm - synth.BPM * r) / (synth.BPM * r) < 0.05 for r in (1, 2, 0.5)), bpm


def test_key(results):
    b = results["dynamic_exact"]["basics"]
    assert (b["key"], b["mode"]) in {("C", "major"), ("A", "minor")}, b


def test_form_abab(results):
    secs = results["dynamic_exact"]["structure"]["sections"]
    assert 3 <= len(secs) <= 6, secs
    labels = [s["label"] for s in secs]
    # the verse comes back: the label at 32 s matches the label at 0 s
    at = lambda t: next(s["label"] for s in secs if s["start"] <= t < s["end"])
    assert at(2) == at(34), labels
    assert at(18) == at(50), labels
    assert at(2) != at(18), labels


def test_flat_dynamics_ranks(results):
    flat = results["flat_exact"]["humanness"]["signals"]["flat_dynamics"]["score"]
    dyn = results["dynamic_exact"]["humanness"]["signals"]["flat_dynamics"]["score"]
    assert flat > dyn, (flat, dyn)


def test_copy_paste_ranks(results):
    exact = results["dynamic_exact"]["humanness"]["signals"]["copy_paste_repetition"]
    varied = results["dynamic_varied"]["humanness"]["signals"]["copy_paste_repetition"]
    assert exact["value"] > (varied["value"] or 0), (exact, varied)


def test_humanness_overall(results):
    assert results["dynamic_varied"]["humanness"]["score"] > results["flat_exact"]["humanness"]["score"]

