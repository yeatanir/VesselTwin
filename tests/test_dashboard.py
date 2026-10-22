import pathlib
import pytest
from streamlit.testing.v1 import AppTest

APP = str(pathlib.Path(__file__).resolve().parents[1] / "app" / "dashboard.py")
VESSELS = ["cvd_tube", "ampoule", "flask", "sorbent", "photoreactor"]


def _run(vessel):
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.selectbox(key="vessel").set_value(vessel).run()
    return at


@pytest.mark.vessel("core")
@pytest.mark.parametrize("vessel", VESSELS)
def test_app_loads(vessel):
    at = _run(vessel)
    assert not at.exception
    assert len(at.tabs) >= 2 and at.metric


@pytest.mark.vessel("core")
def test_edit_changes_result():
    at = _run("cvd_tube")
    snap = lambda: [d.value.to_json() for d in at.dataframe[:2]]
    before = snap()
    w = next(w for w in at.sidebar.number_input if w.key == "cvd_tube:T_boat_S_C")
    w.set_value(w.value + 40).run()
    assert not at.exception
    assert snap() != before


@pytest.mark.vessel("core")
def test_harness_tab_renders():
    at = _run("flask")
    assert any("passed" in m.value for m in at.metric)


@pytest.mark.vessel("core")
def test_three_dropdowns_and_chemistry_set():
    at = _run("sorbent")
    assert [b.key for b in at.selectbox[:3]] == ["vessel", "chem:sorbent", "tier"]
    at.selectbox(key="chem:sorbent").set_value("sorbent__13X_CO2").run()
    assert not at.exception
    import json
    q = json.load(open(pathlib.Path(APP).parents[1] / "presets" / "sorbent__13X_CO2.json"))["isotherm.Q"]
    assert next(w for w in at.sidebar.number_input if w.key == "sorbent:isotherm.Q").value == pytest.approx(q, rel=1e-3)  # preset is sourced now (was 38.0)
    at.selectbox(key="chem:sorbent").set_value("custom").run()


@pytest.mark.vessel("core")
@pytest.mark.parametrize("tier", [0, 1, 2])
def test_tier_dropdown(tier):
    at = _run("flask")
    at.selectbox(key="tier").set_value(tier).run()
    assert not at.exception
    if tier == 2:
        assert any("OpenFOAM v2512" in i.value for i in at.info)


@pytest.mark.vessel("core")
@pytest.mark.parametrize("vessel", VESSELS)
@pytest.mark.parametrize("tier", [0, 2])
def test_every_vessel_every_tier_no_exception(vessel, tier):
    at = _run(vessel)
    at.selectbox(key="tier").set_value(tier).run()
    assert not at.exception


@pytest.mark.vessel("core")
def test_mixed_type_column_is_cast_not_crashed():
    """C5: pyarrow cannot convert [1.0, 'Ar'] in one column; show_df casts mixed object columns to str."""
    import pandas as pd
    from app.common import clean
    here = pathlib.Path(__file__).parent
    at = AppTest.from_file(str(here / "mixed_df_app.py"), default_timeout=60).run()
    assert not at.exception
    assert at.session_state["cleaned"] == ["1.0", "Ar"]
    import pyarrow as pa
    with pytest.raises(pa.ArrowInvalid):
        pa.Table.from_pandas(pd.DataFrame({"value": [1.0, "Ar"]}))  # the raw frame is what used to crash
    pa.Table.from_pandas(clean(pd.DataFrame({"value": [1.0, "Ar", None]})))


@pytest.mark.vessel("core")
@pytest.mark.parametrize("qid", ["s%02d" % i for i in range(1, 15)])
def test_trace_tab_every_question(qid):
    at = AppTest.from_file(str(pathlib.Path(__file__).parent / "trace_tab_app.py"), default_timeout=120)
    at.session_state["qid"] = qid
    at.run()
    assert not at.exception
    assert any("Scripted replay (not model-driven)" in m.value or "Recorded run" in m.value for m in at.markdown)


@pytest.mark.vessel("core")
def test_extras_plots_render_and_photoreactor_has_a_plot():
    from app.common import plots_from_extras, plot_chart
    p = {"title": "t", "x": {"name": "x", "unit": "m", "values": [1, 2, 3]}, "y": {"name": "y", "unit": "s", "values": [1, 4, 9]},
         "band": {"p05": [0, 3, 8], "p95": [2, 5, 10]}}
    assert plots_from_extras({"plots": [p]}) == [p]
    plot_chart(p).to_dict()
    from core import api
    r = api.solve("photoreactor", {}, n_mc=5, seed=0)
    ps = plots_from_extras(r["extras"])
    assert len(ps) == 1 and len(ps[0]["x"]["values"]) == len(ps[0]["y"]["values"]) > 1
    at = _run("photoreactor")
    assert not at.exception
    assert any("Model-declared plots" in s.value for s in at.subheader)


@pytest.mark.vessel("core")
def test_extras_accepts_track_e_photon_flux_format():
    from app.common import plots_from_extras, plot_chart
    e = {"photon_flux_vs_depth": {"x": [0, 1, 2], "x_label": "depth", "x_unit": "cm", "y_label": "flux", "y_unit": "umol s-1 cm-2",
                                  "p05": [1, 0.5, 0.2], "p50": [2, 1, 0.5], "p95": [3, 2, 1]}, "notes": ["n"]}
    (p,) = plots_from_extras(e)
    assert p["band"]["p95"] == [3, 2, 1] and p["y"]["values"] == [2, 1, 0.5]
    plot_chart(p).to_dict()
