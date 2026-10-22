"""Tier 2 flask (OpenFOAM MRF): case text is checked against the parameters, the parser runs on a FAKE fixture (tests/fixtures/tier2_flask),
solver tests skip unless OpenFOAM is on PATH. The integration test ran manually (see its docstring)."""
import math, os, re, shutil, subprocess, pathlib
import numpy as np
import pytest
from tier2.flask import write_case_flask, read_results_flask, analyse, _geom, _split
from vessels.flask import _mix, solve
from vessels.flask.solvents import props

FX = pathlib.Path(__file__).parent / "fixtures" / "tier2_flask"
txt = lambda d, f: (d / f).read_text()


def num(d, f, key): return float(re.search(rf"{key}\s+(\S+?);", txt(d, f)).group(1))


@pytest.mark.vessel("flask")
@pytest.mark.check("case_consistency")
def test_flask_case_follows_params(tmp_path):
    a = write_case_flask({"stir_rpm": 400.0, "bar_mm": 25.0}, tmp_path / "a")
    for f in ("system/blockMeshDict", "system/controlDict.simple", "system/controlDict.pimple", "system/fvSolution", "system/setFieldsDict",
              "constant/MRFProperties", "constant/transportProperties", "constant/turbulenceProperties", "0/U", "0/p", "0/s", "0/k", "0/epsilon"):
        assert (a / f).is_file(), f
    assert num(a, "constant/MRFProperties", "omega") == pytest.approx(2 * math.pi * 400 / 60)  # rpm -> rad/s
    pr = props("water", 25.0)
    assert num(a, "constant/transportProperties", "nu") == pytest.approx(pr["mu"] / pr["rho"], rel=1e-6)  # solvent -> nu
    b = write_case_flask({"stir_rpm": 400.0, "bar_mm": 25.0, "solvent": "ethylene_glycol"}, tmp_path / "b")
    assert num(b, "constant/transportProperties", "nu") > 10 * num(a, "constant/transportProperties", "nu")
    assert "simulationType laminar" in txt(b, "constant/turbulenceProperties") and "kEpsilon" in txt(a, "constant/turbulenceProperties")  # Re switch
    assert not (b / "0/k").exists()
    # bar length -> zone size: the rotor cellZone radius is L/2 + h/2 and the bar patch spans +-L/2 in x
    _, p, t = _split({"bar_mm": 25.0})
    g = _geom(p, t)
    assert g["rz"] == pytest.approx(0.5 * 0.025 + 0.5 * 0.3 * 0.025)
    bm = txt(a, "system/blockMeshDict")
    assert f"({0.0125:.8g} " in bm and f"({g['rz']:.8g} " in bm and "rotor" in bm and "symmetryPlane" in bm
    c = write_case_flask({"bar_mm": 15.0}, tmp_path / "c")
    assert txt(c, "system/blockMeshDict") != bm and f"({0.0075:.8g} " in txt(c, "system/blockMeshDict")
    d = write_case_flask({"cells_per_cm": 12.0}, tmp_path / "d")
    assert txt(d, "system/blockMeshDict") != bm  # finer counts
    with pytest.raises(ValueError):
        write_case_flask({"bar_mm": 60.0, "volume_mL": 50.0}, tmp_path / "e")  # zone does not fit the equal-volume cylinder


@pytest.mark.vessel("flask")
@pytest.mark.check("parser")
def test_flask_parser_on_fake_fixture():
    r = analyse(FX)
    nu, V = 1e-6, 4e-6
    assert r["eps_mean"] == pytest.approx((0.01 + 0.02 + 0.03 + 0.04) / 4 + nu * 100 / 4)  # epsilon field + resolved nu G:G (shear only in cell 0)
    assert r["eps_feed"] == pytest.approx(0.01 + nu * 100)  # blob holds cell 0 only
    assert r["Np_dissip"] == pytest.approx(r["eps_mean"] * V / (6.6667**3 * 0.025**5))
    assert r["Np_torque"] == pytest.approx(9.0e-8 * 41.9 / (6.6667**3 * 0.025**5))  # last row, total_z
    assert r["theta95"] == pytest.approx(40 + 20 * math.log(0.2 / 0.05) / math.log(0.2 / 0.04))  # log interpolation between max-dev 0.2 and 0.04
    pp = read_results_flask(FX, {})
    assert pp.tier == 2 and pp.vessel == "flask" and pp.source == "openfoam:tier2_flask" and not pp.synthetic
    d = pp.derived
    assert d["t_micro_s"].p50 == pytest.approx(17.3 * math.sqrt(nu / r["eps_mean"]))
    assert d["t_micro_feed_s"].p50 > d["t_micro_s"].p50 and d["eps_ratio_feed"].p50 == pytest.approx(r["eps_feed"] / r["eps_mean"])
    assert d["t_mix95_s"].p50 == pytest.approx(r["theta95"])


needs_foam = pytest.mark.skipif(not (shutil.which("blockMesh") and shutil.which("simpleFoam")), reason="OpenFOAM v2512 not on PATH (run from its shell)")


@pytest.mark.vessel("flask")
@pytest.mark.check("openfoam_run")
@needs_foam
def test_flask_mesh_builds(tmp_path):
    a = write_case_flask({}, tmp_path)
    r = subprocess.run(["blockMesh"], cwd=a, env={**os.environ, "PWD": str(a)}, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-800:]
    c = subprocess.run(["checkMesh"], cwd=a, env={**os.environ, "PWD": str(a)}, capture_output=True, text=True)
    assert "Mesh OK" in c.stdout


@pytest.mark.vessel("flask")
@pytest.mark.check("openfoam_run")
@needs_foam
def test_flask_cfd_vs_tier1_integration(tmp_path):
    """INTEGRATION (ran manually, `bash tier2/run_flask.sh`, minutes): water 400 rpm, 100 mL half full, 25 mm bar. CFD epsilon and
    micromixing time must land within a factor 10 / 3 of the (placeholder) Tier 1; the factor-10 band is wide on purpose, see docs/flask_cfd_scan.json."""
    v = {"stir_rpm": 400.0, "t_end_s": 60.0}
    a = write_case_flask(v, tmp_path)
    r = subprocess.run(["bash", str(pathlib.Path(__file__).parents[1] / "tier2" / "run_flask.sh"), str(a)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    pp = read_results_flask(a, v)
    t1 = solve(_split(v)[1])
    assert 0.1 < pp.derived["epsilon_W_kg"].p50 / t1["epsilon_W_kg"] < 10
    assert 1 / 3 < pp.derived["t_micro_s"].p50 / t1["t_micro_s"] < 3


@pytest.mark.vessel("flask")
@pytest.mark.check("case_consistency")
def test_flask_reachable_through_tier2_openfoam(tmp_path):
    """tier2.openfoam.write_case/read_results dispatch to the flask writer/parser (runs on the fake fixture, no solver needed)."""
    from tier2 import openfoam as of
    a = of.write_case("flask", {"stir_rpm": 400.0}, tmp_path / "f")
    assert (a / "system/blockMeshDict").is_file() and of.RUNNER["flask"] == "run_flask.sh" and (pathlib.Path(of.__file__).parent / of.RUNNER["flask"]).is_file()
    assert num(a, "constant/MRFProperties", "omega") == pytest.approx(2 * math.pi * 400 / 60)
    pp = of.read_results(FX, "flask", {})
    assert pp.tier == 2 and "Np" in pp.derived


@pytest.mark.vessel("flask")
@pytest.mark.check("openfoam_run")
@pytest.mark.skipif(not shutil.which("blockMesh"), reason="OpenFOAM v2512 not on PATH (run from its shell)")
def test_flask_openfoam_mesh_builds_via_tier2(tmp_path):
    from tier2 import openfoam as of
    a = of.write_case("flask", {"cells_per_cm": 3.0}, tmp_path)
    r = subprocess.run(["blockMesh"], cwd=a, env={**os.environ, "PWD": str(a)}, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-800:]
