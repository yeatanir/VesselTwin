import numpy as np, pytest
from core import api, params as P
from core.dimensionless import Regime
import vessels.photoreactor as pr
from vessels.photoreactor import H, C_LIGHT, NA


def D(**kw): return P.defaults(pr.DEFS) | kw


FAST_MIX = dict(stir_rpm=3000.0, mix_revs=5.0)  # mixing cap far above the photon rate
THIN = dict(c0_M=1e-6, eps_A=100.0, eps_P=0.0, path_cm=0.05, **FAST_MIX)


@pytest.mark.vessel("photoreactor")
@pytest.mark.check("analytic_limit")
def test_inverse_square_point_source():
    f = lambda d: pr.photons_in(D(lamp_geom="point", dist_cm=d))
    assert f(5) / f(10) == pytest.approx(4.0, rel=1e-12)  # same wall, same area
    p = D(lamp_geom="point", dist_cm=7.0, P_rad_W=3.0)
    assert pr.irradiance(p) == pytest.approx(3.0 / (4 * np.pi * 49.0))
    # line source: -> point source for L << d, -> P/(2 pi d L) for L >> d
    assert pr.irradiance(D(lamp_geom="line", lamp_len_cm=0.1, dist_cm=50.0)) == pytest.approx(pr.irradiance(D(lamp_geom="point", dist_cm=50.0)), rel=1e-4)
    assert pr.irradiance(D(lamp_geom="line", lamp_len_cm=200.0, dist_cm=0.5, P_rad_W=1.0)) == pytest.approx(1.0 / (2 * np.pi * 0.5 * 200.0), rel=1e-4)


@pytest.mark.vessel("photoreactor")
@pytest.mark.check("analytic_limit")
def test_optically_thin_rate_linear_in_power_and_concentration():
    r = lambda **kw: pr.solve(D(**(THIN | kw)))["rate_M_s"]
    assert r(P_rad_W=2.0) / r(P_rad_W=1.0) == pytest.approx(2.0, rel=1e-3)
    assert r(P_rad_W=1.0, c0_M=2e-6) / r(P_rad_W=1.0) == pytest.approx(2.0, rel=1e-3)  # thin: rate ~ eps c l
    s = pr.solve(D(**THIN))
    assert s["fraction_absorbed"] < 1e-3 and s["light_limited"] == 1.0
    assert pr.tier0(D(**THIN))[0] is Regime.reaction_limited


@pytest.mark.vessel("photoreactor")
@pytest.mark.check("analytic_limit")
def test_beer_lambert_absorbed_fraction_and_quantum_yield():
    p = D(**FAST_MIX, eps_P=0.0, c0_M=1e-3, eps_A=1000.0, path_cm=2.0, phi=0.37, f_heat=0.0, h_cool=500.0)
    s = pr.solve(p)
    A = 1000.0 * 1e-3 * 2.0
    assert s["fraction_absorbed"] == pytest.approx(1 - 10 ** (-A), rel=2e-3)  # weak heating drift only
    N_in = s["photon_flux_in_umol_s"]
    assert s["photon_flux_absorbed_umol_s"] == pytest.approx(N_in * (1 - 10 ** (-A)), rel=2e-3)
    V = p["A_irr_cm2"] * p["path_cm"] / 1000
    assert s["rate_photon_limit_M_s"] * V * 1e6 == pytest.approx(0.37 * s["photon_flux_absorbed_umol_s"], rel=1e-9)
    e_mol = H * C_LIGHT / (365e-9) * NA  # photon count: irradiance * area * wall T / E_photon
    assert N_in * 1e-6 == pytest.approx(pr.irradiance(p) * 10.0 * pr.wall_T(p) / e_mol)


@pytest.mark.vessel("photoreactor")
@pytest.mark.check("known_answer")
def test_regime_flips_with_stirring_and_thickness():
    thick = D(c0_M=0.05, eps_A=5000.0, path_cm=1.0, P_rad_W=20.0)
    slow, fast = pr.solve(thick | dict(stir_rpm=5.0)), pr.solve(thick | dict(stir_rpm=3000.0, mix_revs=5.0))
    assert slow["mass_limited"] == 1.0 and fast["Da_mix"] < slow["Da_mix"] / 100
    assert pr.tier0(thick | dict(stir_rpm=5.0))[0] is Regime.transport_limited
    # thin limit: Da = t_mix / t_reaction exactly
    p = D(**THIN)
    n = pr.tier0(p)[2]
    assert n["Da_mix"] == pytest.approx(n["t_mix_s"] / n["t_reaction_s"], rel=1e-9)
    # inner filter: an absorbing product slows conversion
    q = D(c0_M=1e-3, eps_A=1000.0, path_cm=1.0, **FAST_MIX, t_irr_s=300.0)
    assert pr.solve(q | dict(eps_P=5000.0))["conversion_t_irr"] < pr.solve(q | dict(eps_P=0.0))["conversion_t_irr"]
    # thicker wall / more distance lower the photon flux
    assert pr.photons_in(D(wall_mat="soda_lime", lambda_nm=300, wall_mm=5)) < pr.photons_in(D(wall_mat="soda_lime", lambda_nm=300, wall_mm=1))


@pytest.mark.vessel("photoreactor")
@pytest.mark.check("known_answer")
def test_ferrioxalate_preset_matches_sourced_numbers():
    """Beilstein JOC 2013, 9, 217 SI: 6 mM ferrioxalate, 1 cm, Phi = 1.24 at 313 nm, >99% absorbed. IUPAC 2004: Phi 1.25-0.9 over 250-500 nm.
    The lamp is not from the paper, so only Phi*absorbed-photons bookkeeping and the >99% absorption claim are checked, not an absolute flux."""
    out = api.solve("photoreactor", preset="photoreactor__ferrioxalate_313nm_cuvette", n_mc=10)
    v, d = out["values"], out["passport"]["derived"]
    assert (v["phi"], v["lambda_nm"], v["c0_M"], v["path_cm"]) == (1.24, 313, 0.006, 1.0)
    assert 0.9 <= v["phi"] <= 1.25
    assert d["fraction_absorbed"]["p50"] > 0.99
    # for any eps >= 333 M-1cm-1 (A >= 2 at 6 mM, 1 cm) the fraction absorbed is >= 99%, as the SI states
    assert pr.solve(D(**v) | dict(eps_A=333.0, eps_P=0.0))["fraction_absorbed"] >= 0.99 - 1e-3
    # Fe2+ made = Phi * photons absorbed; read through the phenanthroline step (eps510 = 11100 M-1cm-1, 0.2 mL aliquot to 10 mL, 1 cm)
    s = pr.solve(D(**v) | FAST_MIX | dict(f_heat=0.0, t_irr_s=1.0))
    n_fe = s["rate_photon_limit_M_s"] * 1.0 * 3e-3  # mol in 3 mL after 1 s (initial rate)
    A510 = 11100 * (n_fe * (0.2 / 3.0) / 0.01)
    assert A510 == pytest.approx(1.24 * s["photon_flux_absorbed_umol_s"] * 1e-6 * (0.2 / 3.0) / 0.01 * 11100, rel=1e-6)
    assert out["passport"]["synthetic"]  # lamp / eps defaults still placeholders


@pytest.mark.vessel("photoreactor")
def test_extras_sensitivity_and_passport_keys():
    out = api.solve("photoreactor", n_mc=20)
    ex = out["extras"]
    assert set(ex["sensitivity"]) == {"dist_cm", "wall_mm", "P_rad_W", "c0_M"} and ex["most_important_per_sigma"] in ex["sensitivity"]
    assert -2.05 < ex["sensitivity"]["dist_cm"]["elasticity"] < -0.5  # point lamp: -2 if photon-limited, shallower where the mixing cap bites
    dr = out["passport"]["derived"]
    for k in ("photon_flux_absorbed_umol_s", "fraction_absorbed", "conversion_t_irr", "rate_M_s", "light_limited", "Da_mix"):
        assert k in dr
    with pytest.raises(ValueError):
        api.solve("photoreactor", {"dist_cm": 0.0}, n_mc=2)


# ---- Track E: comparison with published actinometry (pre-registered, docs/prereg/track-e.md) ----
import json, pathlib
from bench.photoreactor import score as sc

SETUPS = sc.load()["setups"]


def _score(name):
    return sc.score(name, SETUPS[name], n_mc=50)


@pytest.mark.vessel("photoreactor")
@pytest.mark.check("known_answer")
def test_saenz_collimated_cuvette_slope_within_preregistered_factor():
    """Saenz 2024 Table 2: a_QPB = 0.00161 %/(umol m-2). Pre-registered pass: 1/1.25 <= predicted/measured <= 1.25 (measured ratio 0.88)."""
    r = _score("saenz_qpb_cuvette")
    assert 1 / 1.25 <= r["ratio"] <= 1.25
    assert r["wall_T"] == pytest.approx(0.947, abs=0.005)  # paper's own T = 0.947 at normal incidence
    assert r["Da_mix"] < 1e-2  # photon-limited (Da = r_photon / r_mix), the unstated stirring does not matter


@pytest.mark.vessel("photoreactor")
@pytest.mark.check("known_answer")
def test_saenz_integrating_sphere_cuvette_slope_within_preregistered_factor():
    """Saenz 2024 Table 2: a_IS = 0.0078 %/(umol m-2). Pre-registered pass: factor 1.5 (measured ratio 0.69; no lensing in the model)."""
    r = _score("saenz_is_cuvette")
    assert 1 / 1.5 <= r["ratio"] <= 1.5
    assert r["ratio"] < 1.0  # model misses the paper's unexplained eta = 1.21 excess, so it must under-predict


@pytest.mark.vessel("photoreactor")
@pytest.mark.check("analytic_limit")
def test_diffuse_illumination_limits_and_measured_irradiance_mode():
    from scipy.integrate import quad
    # diffuse wall T = cosine-weighted integral of the same Fresnel/Snell chain (independent adaptive quadrature)
    p = D(illum="diffuse", n_wall=1.56, n_liq=1.33, wall_mm=1.25, wall_mat="quartz", lambda_nm=800.0)
    al = 0.01  # alpha floor 1/cm
    def T(mu):
        s_ = np.sqrt(1 - mu * mu); cw = np.sqrt(1 - (s_ / 1.56) ** 2); cl = np.sqrt(1 - (s_ / 1.33) ** 2)
        return (1 - pr._fresnel(1, mu, 1.56, cw)) * (1 - pr._fresnel(1.56, cw, 1.33, cl)) * np.exp(-al * 0.125 / cw)
    assert pr.wall_T(p) == pytest.approx(quad(lambda m: 2 * m * T(m), 0, 1)[0], rel=1e-6)
    # thin limit: absorbed fraction = A ln10 <1/cos(theta_liq)>, flux-weighted over the refracted cone (independent quadrature)
    A = 1e-6
    cl = lambda m: np.sqrt(1 - (np.sqrt(1 - m * m) / 1.33) ** 2)
    ref = quad(lambda m: 2 * m * T(m) / cl(m), 0, 1)[0] / quad(lambda m: 2 * m * T(m), 0, 1)[0]
    assert pr._fabs(p, A) / (A * np.log(10)) == pytest.approx(ref, rel=1e-4)
    assert 1.1 < ref < 2.0  # refraction into the liquid narrows the cone; 2 is the no-refraction limit
    assert pr._fabs(D(illum="collimated"), 5.0) == pytest.approx(1 - 1e-5)
    # normal-incidence Fresnel equals the collimated formula
    assert pr._fresnel(1.0, 1.0, 1.56, 1.0) == pytest.approx(((1.56 - 1) / 2.56) ** 2)
    # measured irradiance bypasses lamp power and distance; photon count = E A T / E_photon
    m = D(lamp_geom="measured", E_meas_mW_cm2=0.52, A_irr_cm2=3.375)
    assert pr.irradiance(m) == pytest.approx(0.52e-3)
    assert pr.irradiance(m | dict(P_rad_W=99.0, dist_cm=50.0)) == pytest.approx(0.52e-3)
    # V_total changes n0 but not the absorbed photon flux
    s1, s2 = pr.solve(D(**FAST_MIX)), pr.solve(D(**FAST_MIX, V_total_cm3=40.0))
    assert s1["photon_flux_absorbed_umol_s"] == pytest.approx(s2["photon_flux_absorbed_umol_s"])
    assert s2["rate_photon_limit_M_s"] < s1["rate_photon_limit_M_s"]


@pytest.mark.vessel("photoreactor")
def test_extras_photon_flux_vs_depth_band():
    ex = api.solve("photoreactor", n_mc=5)["extras"]
    b = ex["photon_flux_vs_depth"]
    assert len(b["x"]) == len(b["p05"]) == len(b["p50"]) == len(b["p95"]) and b["x_unit"] == "cm" and b["y_unit"] == "umol s-1 cm-2"
    assert all(lo <= m <= hi for lo, m, hi in zip(b["p05"], b["p50"], b["p95"]))
    assert b["p50"][-1] < b["p50"][0]  # Beer-Lambert decay with depth
    assert any("UNSOURCED" in n for n in ex["notes"]) and any("upper bound" in n.lower() for n in ex["notes"])
