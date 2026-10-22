import pathlib, copy
import numpy as np
import pytest
from streamlit.testing.v1 import AppTest
from app.viz import furnace as fz

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = str(ROOT / "app" / "dashboard.py")
pytestmark = [pytest.mark.vessel("cvd_tube"), pytest.mark.check("furnace_view")]
GOOD = "-40, 25\n-15, 300\n-5, 700\n5, 700\n15, 300\n40, 25"


def _run(tier=1, vessel="cvd_tube", model=None, table=None):
    at = AppTest.from_file(APP, default_timeout=240).run()
    at.selectbox(key="vessel").set_value(vessel).run()  # the default vessel depends on registry order
    at.selectbox(key="tier").set_value(tier).run()
    if model or table is not None:
        if model:
            at.radio(key="fv_model").set_value(model)
        if table is not None:
            at.text_area(key="fv_table").set_value(table)
        next(b for b in at.button if b.label == "Update").click().run()
    return at


@pytest.mark.parametrize("tier", [0, 1, 2])
@pytest.mark.parametrize("model", ["furnace", "legacy"])
def test_tab_renders(tier, model):
    at = _run(tier, model=model)
    assert not at.exception
    assert any(t.label == "Furnace and flow" for t in at.tabs)
    assert not [e for e in at.error if "could not run" in e.value]


def test_valid_pasted_profile():
    at = _run(1, table=GOOD)
    assert not at.exception and not at.error


def test_invalid_pasted_profile_shows_error():
    at = _run(1, table="-40, 25\nbanana\n0, 9999\n5")
    assert not at.exception
    assert any("Pasted profile not used" in e.value and "line 2" in e.value and "line 3" in e.value for e in at.error)


def test_other_vessel_message():
    at = _run(1, vessel="flask")
    assert not at.exception and any("only for the tube furnace" in i.value for i in at.info)


def test_parse_profile():
    t, e = fz.parse_profile_text(GOOD, 100)
    assert not e and t.startswith("10:25;35:300")
    assert fz.parse_profile_text("1,2", 100)[1] and fz.parse_profile_text("", 100) == ("", [])
    assert fz.parse_profile_text("0,100\n0,200", 100)[1]


def _prof(Tg_lag=0.0, Tsub=800.0):
    x = np.linspace(0, 100, 101)
    Tw = 300 + 500 * np.exp(-((x - 50) / 15) ** 2)
    Tg = Tw - Tg_lag * np.exp(-x / 10)
    z = [0.0] * 101
    st = {k: {"x_cm": 50.0, "T_body_K": Tsub} for k in ("boat_MoO3", "boat_S", "substrate")}
    return {"x_cm": x.tolist(), "T_wall_K": Tw.tolist(), "T_quartz_K": Tw.tolist(), "T_gas_centre_K": Tg.tolist(), "u_mean_m_s": (0.01 + 0 * x).tolist(),
            "Re": (2 + 0 * x).tolist(), "stations": st,
            "scalars": {"buoyancy_matters_boat_to_substrate": True, "Ri_max_boat_to_substrate": 12.5, "carried_by": "convection", "Pe_transport_boat_to_substrate": 25.0}}


def test_takeaways_come_from_data():
    a = fz.takeaways(_prof(), 100)
    assert "from x = -" in a["temperature"] or "from x = +" in a["temperature"]
    assert "800 C" not in a["temperature"] and f"{800 - 273.15:.0f} C" in a["temperature"]
    assert "1.0 to 1.0 cm/s" in a["flow"] and "Re peaks at 2.0" in a["flow"]
    assert "Ri up to 12.5" in a["regime"] and "convection" in a["regime"]
    p = _prof(Tsub=900.0); p["u_mean_m_s"][-1] = 0.05; p["scalars"]["Ri_max_boat_to_substrate"] = 0.3; p["scalars"]["buoyancy_matters_boat_to_substrate"] = False
    b = fz.takeaways(p, 100)
    assert f"{900 - 273.15:.0f} C" in b["temperature"] and "5.0 cm/s" in b["flow"] and "buoyancy is small" in b["regime"] and "0.3" in b["regime"]
    c = fz.takeaways(_prof(Tg_lag=300.0), 100)  # a gas that lags the wall reaches it later
    assert c["temperature"] != a["temperature"]
