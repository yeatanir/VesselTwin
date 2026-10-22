import json, pathlib
import pytest
from streamlit.testing.v1 import AppTest
from app import home, ui_kit
from llm import trace as T

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = str(ROOT / "tests" / "home_app.py")
DASH = str(ROOT / "app" / "dashboard.py")


def _step(at, n):
    while at.session_state["home"]["step"] < n:
        at.button(key="home_next").click().run()


@pytest.mark.vessel("core")
@pytest.mark.parametrize("scn", list(home.SCENARIOS))
def test_all_five_steps(scn):
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception
    at.button(key=f"home_pick_{scn}").click().run()
    at.button(key="home_read_btn").click().run()
    assert not at.exception and "vt-chip" in " ".join(m.value for m in at.markdown)  # chips drawn from the offline extractor
    for i in range(1, 5):
        at.button(key="home_next").click().run()
        assert not at.exception, (scn, i)
        assert at.subheader[0].value == home.COPY[f"title.{i + 1}"]
    assert at.button(key="home_next").disabled
    for _ in range(4):
        at.button(key="home_back").click().run()
    assert at.session_state["home"]["step"] == 0 and not at.exception


@pytest.mark.vessel("core")
def test_word_limits_copy():
    for k, v in home.COPY.items():
        n = home.words(v)
        if k.startswith("title."):
            assert n <= 6, (k, v)
        elif k.startswith("btn.") or k == "badge.honesty":
            assert n <= 8, (k, v)
        elif k == "trust.sentence":
            assert n <= 30, (k, v)  # two lines
        else:
            assert n <= 14 or k.startswith("cap.chips"), (k, v)
    assert home.words(home.COPY["cap.pitch"]) <= 14


@pytest.mark.vessel("core")
@pytest.mark.parametrize("scn,step", [(s, i) for s in home.SCENARIOS for i in (1, 2, 3, 4)])
def test_rendered_captions_within_limit(scn, step):
    at = AppTest.from_file(APP, default_timeout=180).run()
    at.button(key=f"home_pick_{scn}").click().run()
    _step(at, step)
    assert not at.exception
    for c in at.caption:
        assert home.words(c.value) <= 28, c.value  # knobs caption joins two 14-word captions
    assert home.words(at.subheader[0].value) <= 6


@pytest.mark.vessel("core")
def test_trust_step_uses_trace_labels():
    at = AppTest.from_file(APP, default_timeout=180).run()
    _step(at, 4)
    txt = " ".join(m.value for m in at.markdown)
    for lab in T.LABELS:
        assert lab in txt
    n = home.trust_counts()
    assert set(n) == set(T.LABELS)
    assert sum(n.values()) == sum(len(s["claims"]) for q in T.question_ids() for s in T.load(q)["steps"])
    # numbers in the honest sentence are the ones llm.trace states
    assert "2/8" in T.LABEL_RULES["benchmarked"] and "6/8" in T.LABEL_RULES["benchmarked"]
    assert "2/8" in home.COPY["trust.sentence"] and "6/8" in home.COPY["trust.sentence"]


@pytest.mark.vessel("core")
@pytest.mark.parametrize("scn", list(home.SCENARIOS))
def test_setup_label_never_above_evidence(scn):
    s = home.build_story(scn, home.procedure(scn), n_mc=6)
    assert home.setup_label(s) == "hypothesis"  # defaults / synthetic inputs / tier status cap it
    k = s["knobs"][0]
    assert len(s["knobs"]) >= 3 and k["lo"] <= k["effect"] <= k["hi"]


@pytest.mark.vessel("core")
def test_highlight_marks_stated_spans():
    s = home.build_story("cvd_tube", home.procedure("cvd_tube"), n_mc=6)
    h, n = home.highlight(home.procedure("cvd_tube"), s["spec"])
    assert n >= 2 and h.count("vt-chip") == n
    assert "<script" not in h


@pytest.mark.vessel("core")
def test_dashboard_tab_order():
    at = AppTest.from_file(DASH, default_timeout=180).run()
    assert not at.exception
    labels = [t.label for t in at.tabs]
    assert labels[:2] == ["Home", "Advanced"]
    assert {"Results", "Credibility"} <= set(labels[2:])  # existing tabs kept, now under Advanced


@pytest.mark.vessel("core")
def test_ui_kit_status_glyphs_distinct():
    assert len({g for _, g, _ in ui_kit.STATUS.values()}) == 3 and len({g for _, g, _ in ui_kit.CHIP.values()}) == 3


@pytest.mark.vessel("core")
@pytest.mark.parametrize("scn", list(home.SCENARIOS))
def test_snapshot_matches_text(scn):
    d = json.loads((home.SNAP / f"{scn}.json").read_text())
    assert d["key"] == home._skey(scn, home.procedure(scn))  # regenerate with: python -m app.home
