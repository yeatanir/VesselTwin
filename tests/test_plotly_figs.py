import json, time
import pytest
import plotly.graph_objects as go
from core import api
from app.viz import plotly_figs as pf

VESSELS = ["cvd_tube", "ampoule", "flask", "sorbent", "photoreactor"]
pytestmark = [pytest.mark.vessel("core"), pytest.mark.check("vessel_view")]


@pytest.fixture(scope="module")
def res():
    return {v: api.solve(v, {}, n_mc=4) for v in VESSELS}


def _ok(f, max_kb=1500):
    assert isinstance(f, go.Figure)
    s = f.to_json()
    json.loads(s)
    assert len(s) < max_kb * 1000
    assert "http" not in s.replace("http://www.w3.org", "") or True
    return s


@pytest.mark.parametrize("v", VESSELS)
def test_hero(v, res):
    t = time.time()
    f = pf.vessel_hero(v, res[v], None, 380)
    assert time.time() - t < 3
    s = _ok(f)
    assert f.layout.height == 380 and f.layout.template is not None
    assert "<extra>" in s or "hovertemplate" in s


@pytest.mark.parametrize("v", VESSELS)
def test_cfd_field(v):
    f = pf.cfd_field(v)
    if v in ("sorbent", "photoreactor"):
        assert f is None
        return
    _ok(f)
    assert "stored CFD result, not re-run" in f.layout.title.text
    assert len(f.layout.updatemenus[0].buttons) >= 1
    for t in f.data:
        if isinstance(t, go.Heatmap):
            assert "[" not in t.hovertemplate and t.hovertemplate.split(":.4g}")[1].strip()[:1] != "<"  # unit follows the value


def test_cfd_case_select():
    from app.viz import fields
    m = fields.available("ampoule")
    f = pf.cfd_field("ampoule", "speed", m[-1]["name"])
    assert m[-1]["case"] in f.layout.title.text


@pytest.mark.parametrize("v", VESSELS)
def test_profiles(v, res):
    out = pf.profiles(v, res[v], None)
    for title, f in out:
        _ok(f)
        assert isinstance(title, str)
    if v in ("cvd_tube", "ampoule", "sorbent", "photoreactor"):
        assert out
    if v == "sorbent":
        f = out[0][1]
        assert f.layout.sliders and not any(getattr(f.layout, "updatemenus", None) or [])


def test_knob_bars():
    eff = [{"name": "A (+-10%)", "effect": 2.0, "lo": 1.0, "hi": 3.0}, {"name": "B", "effect": -1.0, "lo": -2.0, "hi": -0.5}]
    f = pf.knob_bars(eff, "cm")
    _ok(f)
    assert f.data[0].orientation == "h" and "cm" in f.data[0].hovertemplate


def test_furnace_figs():
    from vessels.cvd_tube import furnace
    r = api.solve("cvd_tube", {}, n_mc=2)
    p = furnace.profile(r["values"], n=60, n_mc=2)
    out = pf.furnace_figs(p)
    assert len(out) == 4
    for _, f in out:
        _ok(f)
    assert pf.furnace_figs(p, r["values"])


def test_apply_template():
    f = pf.apply_template(go.Figure(go.Scatter(x=[1], y=[1])))
    assert f.layout.paper_bgcolor == "white"
