import numpy as np, pytest
from core import params as P
from schemas.closure import Closure
from vessels.cvd_tube import wulff as w

V = P.defaults(w.DEFS)


def shape(r): return w.geometry(r, V)


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("analytic_limit")
def test_wulff_limits_and_monotone():
    cls, s, lr = shape(1.0)
    assert str(cls) == "hexagon" and s == pytest.approx(0) and lr == pytest.approx(1)  # regular hexagon
    assert str(shape(1e-3)[0]) == "triangle_Mo" and str(shape(1e3)[0]) == "triangle_S"
    assert str(shape(0.7)[0]) == "truncated_triangle"
    ss = shape(np.logspace(-2, 2, 50))[1]
    assert np.all(np.diff(ss) <= 1e-12) and ss[0] == 1 and ss[-1] == -1  # s falls as v_Mo/v_S (S-richness) grows
    # edge lengths from the apothems agree with a direct hexagon: L_Mo/L_S = (2-r)/(2r-1)
    assert shape(0.75)[2] == pytest.approx((2 - 0.75) / (1.5 - 1))


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("known_answer")
def test_detailed_balance_and_trend():
    T = 1000.0
    # at p_feed == p_eq the net edge velocity is the floor (forward = reverse); above it, positive
    peq = V["P_eq_ref_Pa"] * np.exp(V["gamma_edge_S.gamma_eV"] / (w.KB * T))
    assert w.rates(V, peq, 1e9, T)[1] == pytest.approx(1e-12)
    assert w.rates(V, 2 * peq, 1e9, T)[1] > 1e-6
    # direction (Wang/Govind Rajan): Mo-rich -> Mo triangle, S-rich -> hexagon/S side
    mo, so = w.shape_at(V, (10.0, 1.0), T), w.shape_at(V, (0.1, 100.0), T)
    assert mo["shape_index"] > so["shape_index"] and mo["shape"] == "triangle_Mo"


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("known_answer")
def test_closure_override_changes_shape():
    base = w.shape_at(V, (5.0, 50.0), 1000.0)
    c = Closure(name="k_attach_Mo", law="arrhenius", params={"Ea_eV": 0.9}, method="test", source="test", synthetic=True)
    v2 = w.apply_wulff_closures(V, [c])
    assert v2["k_attach_Mo.Ea_eV"] == 0.9
    assert w.shape_at(v2, (5.0, 50.0), 1000.0)["r_vMo_vS"] < base["r_vMo_vS"]


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("known_answer")
def test_shape_map_responds_to_sulfur_boat_and_knobs():
    m = w.shape_map(V, n=20, n_mc=10)
    assert set(m["shape"]) >= {"triangle_Mo", "triangle_S"} and np.isfinite(m["boundary_cm_from_boat"])
    assert len(m["p05"]) == len(m["p95"]) == 20
    hot = w.shape_map(V | {"T_boat_S_C": 220.0}, n=20, n_mc=2)
    assert hot["boundary_cm_from_boat"] != m["boundary_cm_from_boat"]
    k = w.knob_sensitivity(V)
    assert {r["knob"] for r in k} == set(w.KNOBS) and abs(k[0]["shift_cm"]) >= abs(k[-1]["shift_cm"])


@pytest.mark.vessel("cvd_tube")
def test_knob_sensitivity_never_reports_edge_jumps():
    from vessels.cvd_tube import wulff
    from core import params as P
    ks = wulff.knob_sensitivity(P.defaults(wulff.DEFS))
    assert all(r["valid"] for r in ks) and abs(ks[0]["cm_per_unit"]) < 0.5  # an edge jump gave a spurious -1.17 cm per C
    hot = wulff.knob_sensitivity(P.defaults(wulff.DEFS) | {"T_boat_Mo_C": 600.0})
    assert any(not r["valid"] for r in hot)  # Mo-poor everywhere (no triangle_Mo zone): boundary left the map, flagged not ranked
