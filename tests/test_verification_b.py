"""Track B: analytic / known-answer checks for tier2/verification (Tier 0 replacements, GCI)."""
import math, pytest
from core import params as P
import vessels.ampoule as amp
import vessels.cvd_tube as tube
from tier2.verification import tier0 as t0


@pytest.mark.vessel("ampoule")
@pytest.mark.check("analytic_limit")
@pytest.mark.parametrize("tilt", [-90, -30, 0, 30, 90])
def test_f_variant_duct_reproduces_shipped(tilt):
    p = P.validate(amp.DEFS, {"tilt_deg": float(tilt), "D_mm": 25.0, "T_source_C": 880.0})
    assert t0.f_variant(p, "duct") == pytest.approx(float(amp._core(p)["f"]), rel=1e-9)
    assert t0.f_variant(p, "none") >= t0.f_variant(p, "duct") - 1e-12  # stratification only damps


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("analytic_limit")
def test_tube_da_eff_limits():
    p = P.validate(tube.DEFS, {})
    d0 = t0.tube_da_eff(p)
    assert t0.tube_da_eff(p, Sh=2 * p["Sh"]) == pytest.approx(2 * d0, rel=1e-9)  # linear in k_m
    hot = P.validate(tube.DEFS, {"T_boat_Mo_C": 600.0})
    assert t0.tube_da_eff(hot) <= t0.tube_da_eff(P.validate(tube.DEFS, {"T_boat_Mo_C": 800.0}))  # colder boat -> smaller driving force
    # a flat wall colder than nothing: tiny flow -> huge Da
    assert t0.tube_da_eff(P.validate(tube.DEFS, {"flow_sccm": 30.0})) > t0.tube_da_eff(P.validate(tube.DEFS, {"flow_sccm": 1500.0}))


@pytest.mark.check("known_answer")
def test_gci_nasa_worked_example():
    """NASA Glenn WIND tutorial worked example (Roache GCI): p = 1.786170, GCI12 = 0.103083 %."""
    g = __import__("tier2.verification.gci", fromlist=["gci"]).gci(0.97050, 0.96854, 0.96178, 2.0)
    assert g["p_obs"] == pytest.approx(1.786170, abs=2e-6) and g["gci_fine"] * 100 == pytest.approx(0.103083, abs=2e-6) and g["Fs"] == 1.25 and not g["flags"]


@pytest.mark.check("analytic_limit")
def test_gci_exact_second_order_and_flags():
    from tier2.verification.gci import gci
    f = lambda h: 1.0 + 0.3 * h**2  # exact order 2, r = 2
    g = gci(f(1), f(2), f(4), 2.0)
    assert g["p_obs"] == pytest.approx(2.0) and g["f_richardson"] == pytest.approx(1.0)
    assert gci(1.0, 1.1, 1.05, 2.0)["Fs"] == 3.0  # oscillatory
    assert gci(1.0, 1.0001, 1.2, 2.0)["Fs"] == 3.0  # p far above 2 formal orders
