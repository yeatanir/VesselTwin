"""Tier 2 OpenFOAM case writer + parser. No OpenFOAM needed: case text is checked for consistency with the params, the parser runs on
tests/fixtures/tier2_* (FAKE, format-correct, tagged in-file). The solver test skips unless buoyantPimpleFoam/blockMesh are on PATH."""
import math, os, re, shutil, subprocess, pathlib
import pytest
from tier2.openfoam import write_case, read_results, _segments
from core import params as P
import vessels.cvd_tube as tube, vessels.ampoule as amp

FX = pathlib.Path(__file__).parent / "fixtures"
txt = lambda d, f: (d / f).read_text()


def num(d, f, key):
    return float(re.search(rf"{key}\s+(?:uniform\s+)?(\S+?);", txt(d, f)).group(1))


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("case_consistency")
def test_tube_case_follows_params(tmp_path):
    p = P.defaults(tube.DEFS)
    a = write_case("cvd_tube", {}, tmp_path / "a")
    for f in ("system/controlDict", "system/fvSchemes", "system/fvSolution", "system/blockMeshDict", "constant/thermophysicalProperties",
              "0/T", "0/U", "0/p_rgh", "0/Y_MoO3", "0/Y_S2", "constant/g"):
        assert (a / f).is_file(), f
    bm = txt(a, "system/blockMeshDict")
    for x in (p["x_S_boat_cm"], p["x_MoO3_cm"], p["x_MoO3_cm"] + p["x_substrate_cm"], p["L_tube_cm"]):
        assert f"({x / 100:.8g} 0 0)" in bm  # boat / substrate / outlet stations present
    # wall T list is the furnace profile: peak equals the plateau temperature, ends equal ambient
    Tw = [float(x) for x in re.search(r"wall\s*\{[^}]*?fixedValue;\s*value nonuniform List<scalar> \d+\(\n(.*?)\n\)", txt(a, "0/T"), re.S).group(1).split()]
    assert max(Tw) == pytest.approx(p["T_furnace_C"] + 273.15, abs=1.0) and Tw[0] == pytest.approx(p["T_ends_C"] + 273.15, abs=1.0)
    assert num(a, "0/Y_MoO3", "refValue") > 0 and "refValue uniform" in txt(a, "0/Y_MoO3")  # boat saturation
    b = write_case("cvd_tube", {"T_boat_Mo_C": 760.0, "T_furnace_C": 800.0}, tmp_path / "b")
    assert txt(a, "0/Y_MoO3") != txt(b, "0/Y_MoO3") and txt(a, "0/T") != txt(b, "0/T")  # editing a param changes the case
    c = write_case("cvd_tube", {"x_substrate_cm": 20.0, "cells_per_cm": 2.0}, tmp_path / "c")
    assert txt(a, "system/blockMeshDict") != txt(c, "system/blockMeshDict")
    mdot = [num(a, "0/U", "massFlowRate constant"), num(write_case("cvd_tube", {"flow_sccm": 200.0}, tmp_path / "d"), "0/U", "massFlowRate constant")]
    assert mdot[1] == pytest.approx(2 * mdot[0])


@pytest.mark.vessel("cvd_tube")
def test_tube_rejects_overlapping_strips():
    with pytest.raises(ValueError):
        _segments(P.validate(tube.DEFS, {"x_substrate_cm": 0.0, "substrate_length_cm": 5.0, "boat_area_MoO3_cm2": 50.0, "x_MoO3_cm": 99.0}))
    with pytest.raises(ValueError):
        write_case("cvd_tube", {"tube_id_in": 9.0}, "/nonexistent")  # out of ParamDef bounds


@pytest.mark.vessel("ampoule")
@pytest.mark.check("case_consistency")
@pytest.mark.parametrize("tilt", [0.0, 30.0, -45.0, 90.0])
def test_ampoule_gravity_and_temperatures(tmp_path, tilt):
    a = write_case("ampoule", {"tilt_deg": tilt}, tmp_path)
    gx, gy, gz = map(float, re.search(r"value \((\S+) (\S+) (\S+)\)", txt(a, "constant/g")).groups())
    assert math.hypot(gx, gy) == pytest.approx(9.81) and gz == 0
    assert gx == pytest.approx(-9.81 * math.sin(math.radians(tilt)), abs=1e-6) and gy == pytest.approx(-9.81 * math.cos(math.radians(tilt)), abs=1e-6)
    p = P.defaults(amp.DEFS)
    T = txt(a, "0/T")
    assert f"uniform {p['T_source_C'] + 273.15:.8g}" in T and f"uniform {p['T_sink_C'] + 273.15:.8g}" in T
    c = amp._core(p)
    assert f"uniform {c['p2'] / c['Ptot']:.8g}" in txt(a, "0/Y_AIn")  # source equilibrium p fixed on the end face
    assert "pRefValue" in txt(a, "system/fvSolution")  # closed volume
    assert "ampouleBoussinesqFoam" in txt(a, "system/controlDict") and "TRef" in txt(a, "constant/transportProperties")
    assert num(a, "constant/ampouleProperties", "betaS") > 0  # source end carries the heavier gas, so composition term is non-zero
    assert num(write_case("ampoule", {"tilt_deg": tilt, "species_buoyancy": 0.0}, a / "th"), "constant/ampouleProperties", "betaS") == 0
    assert ("wedge" in txt(a, "system/blockMeshDict")) == (abs(tilt) == 90)  # wedge only when axisymmetric
    ref = float(re.search(r"source\s*\{[^}]*?valueFraction uniform (\S+);", txt(a, "0/Y_AIn")).group(1))
    assert 0.5 < ref < 1  # Hertz-Knudsen fraction: kinetics fast but not infinite


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("parser")
def test_tube_parser_on_fake_fixture():
    pp = read_results(FX / "tier2_tube", "cvd_tube", {})
    assert pp.tier == 2 and pp.source == "openfoam:tier2_tube" and pp.synthetic  # default ParamDefs include synthetic thermo
    p = P.defaults(tube.DEFS)
    pM = 2.0e-4 * p["pressure_Pa"] * 39.948 / 143.95
    assert pp.species["MoO3_g"]["p_Pa"].p50 == pytest.approx(pM, rel=1e-3) and pp.T_K.p50 == pytest.approx(1023.15)
    assert pp.derived["supersaturation_MoO3"].p50 == pytest.approx(pM / float(tube.psat_MoO3(p, 1023.15)))
    assert pp.derived["ratio_Mo_S"].p50 > 0


@pytest.mark.vessel("ampoule")
@pytest.mark.check("parser")
def test_ampoule_parser_on_fake_fixture():
    pp = read_results(FX / "tier2_ampoule", "ampoule", {})
    c = amp._core(P.defaults(amp.DEFS))
    assert pp.tier == 2 and pp.T_K.p50 == pytest.approx(1076.3)
    assert pp.derived["flux_total_mol_m2_s"].p50 == pytest.approx(5.0 * c["D"] * c["Ptot"] / (8.314462618 * c["T"]), rel=1e-6)
    assert pp.derived["convection_enhancement"].p50 == pytest.approx(pp.derived["flux_total_mol_m2_s"].p50 / c["J"])
    assert pp.species["AIn_g"]["p_sink_Pa"].p50 == pytest.approx(0.12 * c["Ptot"])


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("openfoam_run")
@pytest.mark.skipif(not (shutil.which("blockMesh") and shutil.which("buoyantPimpleFoam")), reason="OpenFOAM v2512 not on PATH (run from its shell)")
def test_tube_mesh_builds(tmp_path):
    a = write_case("cvd_tube", {}, tmp_path)
    r = subprocess.run(["blockMesh"], cwd=a, env={**os.environ, "PWD": str(a)}, capture_output=True, text=True)  # OpenFOAM reads $PWD, rejects the spaced project path
    assert r.returncode == 0, r.stdout[-800:]


@pytest.mark.vessel("ampoule")
@pytest.mark.check("openfoam_run")
@pytest.mark.skipif(not (shutil.which("blockMesh") and shutil.which("ampouleBoussinesqFoam")), reason="OpenFOAM v2512 not on PATH (run from its shell)")
def test_ampoule_diffusion_limit_matches_tier1(tmp_path):
    """INTEGRATION (ran manually, `bash tier2/run.sh` ~1 min): small D_mm -> Ra << Ra_crit, so Tier 2 CFD must reproduce Tier 1 Schafer flux."""
    v = {"D_mm": 5.0, "t_end_s": 800.0}
    a = write_case("ampoule", v, tmp_path)
    r = subprocess.run(["bash", str(pathlib.Path(__file__).parents[1] / "tier2" / "run.sh"), str(a)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    pp = read_results(a, "ampoule", v)
    assert pp.derived["convection_enhancement"].p50 == pytest.approx(1.0, rel=0.2)  # J_cfd / J_schafer (diffusion only)
