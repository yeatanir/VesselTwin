import pathlib
import pytest
from streamlit.testing.v1 import AppTest
from core import api
from app import controls as K
from app import workspace as W

APP = str(pathlib.Path(__file__).resolve().parents[1] / "tests" / "ws_app.py")
VESSELS = list(K.KEY_CONTROLS)


def _out(vessel, ov):
    r = api.solve(vessel, ov, n_mc=K.N_MC.get(vessel, 12), extras=False)
    return [r["passport"]["derived"][k]["p50"] for _, k, _, _ in K.TILES[vessel]] + [r["regime"]]


def test_five_vessels_incl_photoreactor():
    assert VESSELS == ["cvd_tube", "ampoule", "flask", "sorbent", "photoreactor"]


@pytest.mark.parametrize("vessel", VESSELS)
def test_controls_map_to_paramdefs(vessel):
    sch = {d["name"]: d for d in api.schema(vessel)}
    cs = K.KEY_CONTROLS[vessel]
    assert 4 <= len(cs) <= 6
    for c in cs:
        d = sch[c["name"]]  # KeyError = wrong name
        if "select" in c:
            assert d["choices"]
        else:
            assert d["lo"] <= c["lo"] < c["hi"] <= d["hi"], c["name"]
            assert d["lo"] <= d["default"] <= d["hi"]
    for t in K.TILES[vessel]:  # every tile key is a real output
        assert t[1] in api.solve(vessel, n_mc=2, extras=False)["passport"]["derived"]


@pytest.mark.parametrize("vessel", VESSELS)
def test_each_key_control_changes_an_output(vessel):
    sch = {d["name"]: d for d in api.schema(vessel)}
    base = _out(vessel, {})
    for c in K.KEY_CONTROLS[vessel]:
        pts = list(sch[c["name"]]["choices"][:3]) if "select" in c else [c["lo"], c["hi"]]
        outs = [_out(vessel, {c["name"]: x}) for x in pts]
        assert any(o != base for o in outs) and (len(pts) == 3 or outs[0] != outs[1]), f"{vessel}.{c['name']} changes nothing"


@pytest.mark.parametrize("vessel", VESSELS)
def test_presets_valid_and_load(vessel):
    ps = W.presets(vessel)
    assert 2 <= len(ps) <= 6
    sch = {d["name"] for d in api.schema(vessel)}
    for label, p in ps.items():
        assert set(p) <= sch, label
        api.solve(vessel, p, n_mc=2, extras=False)  # solvable


@pytest.mark.parametrize("vessel", VESSELS)
@pytest.mark.parametrize("fid", W.FIDELITY)
def test_page_renders(vessel, fid):
    at = AppTest.from_file(APP, default_timeout=240)
    at.session_state["vt_vessel"] = vessel
    at.run()
    assert not at.exception
    assert at.session_state["wk_vessel"] == vessel  # preselected from session state
    at.get("button_group")[0].set_value(fid).run()  # wk_fid segmented control
    assert not at.exception, (vessel, fid)
    md = " ".join(m.value for m in at.markdown)
    assert 'class="wk-kpi"' in md and "wk-tier on" in md and "Tier 1" in md


def test_widget_changes_results_and_preset_sets_controls():
    at = AppTest.from_file(APP, default_timeout=240)
    at.session_state["vt_vessel"] = "photoreactor"
    at.run()
    tiles = lambda: next(m.value for m in at.markdown if m.value.startswith('<div class="wk-kpis">'))
    t0 = tiles()
    at.slider(key="wk:photoreactor:dist_cm").set_value(15.0).run()
    assert not at.exception and tiles() != t0
    name = "365 nm LED strip, thin flow cell (illustrative)"
    at.get("button_group")[1].set_value(name).run()  # wk_preset pills
    assert not at.exception
    assert at.select_slider(key="wk:photoreactor:P_rad_W").value == 10 and at.slider(key="wk:photoreactor:dist_cm").value == 3
    at.get("button_group")[1].set_value("Defaults").run()
    assert at.slider(key="wk:photoreactor:dist_cm").value == 5


@pytest.mark.parametrize("vessel", VESSELS)
def test_page_loads_like_streamlit_app_loader(vessel):
    """Loader path of streamlit_app.py (module import + render) with vt_vessel set as Home's Open button does, from a foreign cwd."""
    at = AppTest.from_file(str(pathlib.Path(APP).with_name("ws_nav_app.py")), default_timeout=240)
    at.session_state["vt_vessel"] = vessel
    at.run()
    assert not at.exception, at.exception
    assert at.session_state["wk_vessel"] == vessel


def test_picker_click_switches_vessel_and_all_five_render():
    at = AppTest.from_file(APP, default_timeout=240)
    at.run()
    for v in VESSELS:
        at.button(key=f"wk_pick_{v}").click().run()
        assert not at.exception, v
        assert at.session_state["vt_vessel"] == v
        assert any(m.value.startswith('<div class="wk-kpis">') for m in at.markdown), v


def test_reset_dot_restores_preset_value():
    at = AppTest.from_file(APP, default_timeout=240)
    at.session_state["vt_vessel"] = "photoreactor"
    at.run()
    at.slider(key="wk:photoreactor:dist_cm").set_value(15.0).run()
    at.button(key="wk_rs:photoreactor:dist_cm").click().run()
    assert at.slider(key="wk:photoreactor:dist_cm").value == 5
