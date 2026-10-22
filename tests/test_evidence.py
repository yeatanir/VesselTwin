import pathlib
import pytest
from streamlit.testing.v1 import AppTest
from app import evidence

APP = str(pathlib.Path(__file__).resolve().parents[1] / "tests" / "ev_app.py")


@pytest.mark.vessel("core")
def test_evidence_renders():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert [t.label for t in at.tabs] [:4] == ["Reasoning trace", "Benchmarks", "Credibility", "Literature"]


@pytest.mark.vessel("core")
def test_benchmark_rows_stay_honest():
    assert {v for *_, v in evidence.BENCH} <= set(evidence.GLYPH)
    sens = next(r for r in evidence.BENCH if r[0].startswith("Sensitivity direction (tube"))
    assert "2/8" in sens[1] and "6/8" in sens[1] and sens[3] == "miss"  # never rewritten as a pass
