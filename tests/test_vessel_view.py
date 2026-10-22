import json, pathlib
import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = str(ROOT / "app" / "dashboard.py")
VESSELS = ["cvd_tube", "ampoule", "flask", "sorbent", "photoreactor"]
pytestmark = [pytest.mark.vessel("core"), pytest.mark.check("vessel_view")]


def _run(vessel, tier):
    at = AppTest.from_file(APP, default_timeout=180).run()
    at.selectbox(key="vessel").set_value(vessel).run()
    at.selectbox(key="tier").set_value(tier).run()
    return at


@pytest.mark.parametrize("tier", [0, 1, 2])
@pytest.mark.parametrize("vessel", VESSELS)
def test_vessel_view_tab(vessel, tier):
    at = _run(vessel, tier)
    assert not at.exception
    msgs = [e.value for e in at.error] + [w.value for w in at.warning]
    assert not [m for m in msgs if "Vessel view failed" in m or "could not be" in m], msgs
    assert any(t.label == "Vessel view" for t in at.tabs)


def test_cfd_labels_present_at_tier2():
    at = _run("cvd_tube", 2)
    text = " ".join(m.value for m in at.markdown)
    assert "stored CFD result, not re-run" in text and "cells" in text


def test_no_cfd_for_sorbent_says_so():
    at = _run("sorbent", 2)
    assert any("No stored CFD field result" in i.value for i in at.info)


@pytest.mark.parametrize("f", sorted((ROOT / "data" / "viz_cache").glob("*.npz")), ids=lambda f: f.stem)
def test_field_cache_loads(f):
    from app.viz import fields
    d, meta = fields.load(f.stem)
    assert f.stat().st_size < 1_000_000
    nx, ny = len(d["x"]), len(d["y"])
    for k in list(meta["fields"]) + ["u", "v"]:
        a = d[k]
        assert a.shape == (ny, nx), (k, a.shape)
        fin = np.isfinite(a)
        assert fin.mean() > 0.5 and np.isfinite(a[fin]).all()
    assert "stored CFD result" in meta["note"] and meta["n_cells"] > 0 and meta["date_made"]
    assert np.nanmin(d["T"]) > 250 if "T" in d else True


@pytest.mark.parametrize("vessel", VESSELS)
def test_hero_function(vessel, tmp_path):
    from core import api
    from app import vessel_view
    r = api.solve(vessel, {}, n_mc=4)
    app = tmp_path / "hero_app.py"
    app.write_text(f"import sys; sys.path.insert(0, {str(ROOT)!r})\nfrom app.vessel_view import render_vessel_hero\nfrom core import api\n"
                   f"render_vessel_hero(api.solve({vessel!r}, {{}}, n_mc=4), {vessel!r}, None, height=360)\n")
    at = AppTest.from_file(str(app), default_timeout=120).run()
    assert not at.exception and not [c for c in at.caption if "unavailable" in c.value]
