import json, pathlib
import pytest
from llm import trace as T


@pytest.mark.vessel("llm")
def test_trace_schema_and_labels_never_exceed_evidence():
    for qid in ("s01", "s03", "s02"):  # agree, disagree, not modellable (fresh run, offline)
        T.validate(T.run_policy(qid, n_mc=10))
    for f in pathlib.Path(T.TRACES).glob("sens_*.json"):  # every stored trace
        T.validate(json.loads(f.read_text()))
    bad = T.run_policy("s03", n_mc=10)
    bad["steps"][2]["claims"][1]["label"] = "benchmarked"  # shape class upgraded -> must be rejected
    with pytest.raises(AssertionError):
        T.validate(bad)


def test_sign_flip_condition():
    assert T.is_sign_flip([-1, 0, 1]) and T.is_sign_flip([1, 1, -1])
    assert not T.is_sign_flip([1, 1, 1]) and not T.is_sign_flip([0, 1, 1]) and not T.is_sign_flip(None)  # flat vs rising is not a flip


def _flipped_trace(monkeypatch):
    real = T._read

    def fake(p):
        d = real(p)
        if p.endswith("predictions.json"):
            for x in d["predictions"]:
                if x["id"] == "s01":
                    x["proxy_p05_p50_p95"] = [[5 - i, 1 + i, 1 + i] for i in range(5)]  # p05 falls, p95 rises
        return d
    monkeypatch.setattr(T, "_read", fake)
    return T.run_policy("s01", n_mc=10)


def test_sign_flip_banner_fires_when_condition_holds(monkeypatch):
    from streamlit.testing.v1 import AppTest
    tr = _flipped_trace(monkeypatch)
    d = tr["steps"][3]["data"]
    assert d["flip"] and d["signs"][0] * d["signs"][2] < 0
    T.validate(tr)
    assert any("p05 and p95 trends point in opposite" in c["text"] for c in tr["steps"][3]["claims"])
    at = AppTest.from_file(str(pathlib.Path(__file__).parent / "trace_banner_app.py"), default_timeout=60)
    at.session_state["tr"] = tr
    at.run()
    assert not at.exception
    assert any("SIGN FLIP" in m.value for m in at.markdown)


def test_sign_flip_banner_silent_on_stored_data():
    for qid in T.question_ids():
        d = T.load(qid)["steps"][3]["data"]
        assert not d["flip"] or d["signs"][0] * d["signs"][2] < 0


def test_every_excerpt_carries_support_label():
    papers = T._read("bench/sensitivity/papers.json")
    for p in papers:
        for e in T.search_literature(p, papers):
            assert set(e["support"]) == {"verified", "name", "value", "why"}
            if e["support"]["verified"]:
                assert e["support"]["name"] and e["support"]["value"]
