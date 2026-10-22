"""Tier 2 stirred flask in OpenFOAM v2512 (stock simpleFoam + pimpleFoam, MRF frozen rotor). Entry points for the lead to wire in:
write_case_flask(values, outdir), read_results_flask(outdir, values) -> Passport, BUILD_FLASK (the template), tier2/run_flask.sh <case>.

Model (ponytail, all deliberate):
 - Geometry: vertical CYLINDER of the same liquid volume AND depth as the round-bottom flask's liquid (r = sqrt(Vl/(pi h))), flat
   floor, flat slip free surface (no vortex, no gravity). No spherical bottom, no curvature: wall/bar clearance differs from a real flask.
 - Stir bar: a square-section cuboid (length bar_mm, width = height = 0.3 bar_mm) lifted one height off the floor, a real no-slip wall
   patch `bar`, inside an MRF cell zone `rotor` (cylinder r = L/2 + h/2, one half-height margin above/below). Frozen rotor: ONE bar angle
   (bar along x), steady flow. Sliding/moving-mesh bar is out of scope. The unsteady wake and the bar's sweep through the fluid are not
   represented, so frozen-rotor tracer mixing is slower than reality (a blob never meets the rotating bar) and in LAMINAR runs the
   tracer never mixes across closed streamlines (theta95 -> not reached): treat the tracer theta95 as an upper bound.
 - Turbulence: kEpsilon (wall functions) when Re = N d^2/nu >= Re_lam, else laminar. Dissipation = kEpsilon epsilon + resolved
   nu(G:G + G:G^T) from grad(U); bar power also from the torque on the `bar` patch (cross-check).
 - Tracer pulse: pimpleFoam restarted from the steady field with PIMPLE solveFlow no and the `scalarTransport` function object,
   DEff = nu/Sc + nut/Sct. theta95 = first time max|s - mean|/mean < 5 % over all cells.
 - Micromixing t = C_micro sqrt(nu/eps): mean eps over the liquid, and eps volume-averaged in the feed blob (top surface, r/2, y>0)."""
import json, math, pathlib, re
import numpy as np
from core.params import ParamDef as P, validate
from core.registry import load_all
from schemas.passport import Dist, Passport

T2_FLASK_DEFS = [
    P("cells_per_cm", "Target cell size 1/x", "1/cm", 6.0, 2, 30, group="mesh"),
    P("n_iter", "simpleFoam iterations (fixed, no residual stop)", "", 1500, 100, 20000, group="model"),
    P("t_end_s", "Tracer run length (0 = 15 x Tier 1 theta95, 10-300 s)", "s", 0.0, 0, 1e5, group="model"),
    P("model", "Flow model", "", "auto", choices=["auto", "laminar", "kEpsilon"], group="model"),
    P("Re_lam", "Re below which 'auto' runs laminar", "", 1000.0, 10, 1e5, source="synthetic", group="model"),
    P("maxCo", "Courant limit of the tracer run (pimpleFoam re-solves the converged flow; unstable above ~4)", "", 2.0, 0.5, 50, group="model"),
    P("Sct", "Turbulent Schmidt number for the tracer", "", 0.7, 0.1, 2, source="synthetic", group="model"),
    P("Sc", "Molecular Schmidt number of the tracer", "", 1000.0, 1, 1e5, group="model"),
]
BAR_ASPECT = 0.3  # bar width = height = 0.3 L (25 mm x 8 mm class bar, square section)


def _hdr(cls, obj): return f"FoamFile\n{{\n    version 2.0;\n    format ascii;\n    class {cls};\n    object {obj};\n}}\n\n"
def _vec(v): return "(" + " ".join(f"{x:.8g}" for x in v) + ")"


def _fld(name, cls, dims, internal, patches):
    b = "".join(f"    {k}\n    {{\n" + "".join(f"        {a} {c};\n" for a, c in v.items()) + "    }\n" for k, v in patches.items())
    return _hdr(cls, name) + f"dimensions {dims};\n\ninternalField {internal};\n\nboundaryField\n{{\n{b}}}\n"


def _geom(p, t):
    """All lengths in m. Raises ValueError when the bar zone does not fit the equal-volume cylinder."""
    from vessels.flask import _mix
    m = _mix(p)
    L, dx = p["bar_mm"] / 1e3, 1e-2 / t["cells_per_cm"]
    r, H = math.sqrt(m["Vl"] / (math.pi * m["depth"])), m["depth"]
    hb = BAR_ASPECT * L
    g = dict(L=L, a=L / 2, b=hb / 2, hb=hb, mg=hb / 2, r=r, H=H, dx=dx, m=m)
    g["rz"], g["z"] = L / 2 + g["mg"], [0, hb / 2, hb, 2 * hb, 2.5 * hb, H]
    if g["rz"] + 2 * dx > r or g["z"][4] + 2 * dx > H:
        raise ValueError(f"bar zone (r {g['rz']*1e3:.1f}, top {g['z'][4]*1e3:.1f} mm) does not fit the {r*1e3:.1f} x {H*1e3:.1f} mm "
                         "equal-volume cylinder: smaller bar or more fill")
    return g


def _mesh(g):
    """blockMeshDict: bar cuboid carved out of an O-grid. 12 points per z level (C bar corners, Z zone circle, O wall circle), 5 z layers."""
    a, b, rz, r, z, dx = g["a"], g["b"], g["rz"], g["r"], g["z"], g["dx"]
    th = math.atan2(b, a)
    ang = [-th, th, math.pi - th, math.pi + th]
    mid = [0, math.pi / 2, math.pi, 3 * math.pi / 2]
    pt = [(a, -b), (a, b), (-a, b), (-a, -b)] + [(R * math.cos(q), R * math.sin(q)) for R in (rz, r) for q in ang]
    vtx = "".join(f"    ({x:.8g} {y:.8g} {zz:.8g})\n" for zz in z for x, y in pt)
    ce = lambda L_: max(3, math.ceil(L_ / dx))
    ns, nl = ce(2 * b), ce(2 * a)
    nri, nro = max(2, math.ceil((rz - math.hypot(a, b)) / dx)), max(2, math.ceil((r - rz) / dx))
    nz = [max(2, math.ceil((z[i + 1] - z[i]) / dx)) for i in range(5)]
    tan = [ns, nl, ns, nl]
    blocks, quads = [], []  # quads: (layer, kind, k, vertex ids)
    for i in range(5):
        qs = [("center", 0, [0, 1, 2, 3], (ns, nl))] if i != 2 else []
        qs += [("inner", k, [(k + 1) % 4, k, 4 + k, 4 + (k + 1) % 4], (tan[k], nri)) for k in range(4)]
        qs += [("outer", k, [4 + (k + 1) % 4, 4 + k, 8 + k, 8 + (k + 1) % 4], (tan[k], nro)) for k in range(4)]
        for kind, k, q, (n1, n2) in qs:
            v = [i * 12 + x for x in q] + [(i + 1) * 12 + x for x in q]
            zone = "rotor " if kind != "outer" and i in (1, 2, 3) else ""
            blocks.append(f"    hex ({' '.join(map(str, v))}) {zone}({n1} {n2} {nz[i]}) simpleGrading (1 1 1)\n")
            quads.append((i, kind, k, v))
    edges = "".join(f"    arc {i*12 + 4 + 4*R + k} {i*12 + 4 + 4*R + (k + 1) % 4} ({(rz, r)[R]*math.cos(mid[k]):.8g} {(rz, r)[R]*math.sin(mid[k]):.8g} {z[i]:.8g})\n"
                    for i in range(6) for R in (0, 1) for k in range(4))
    F = lambda v, ids: "(" + " ".join(str(v[j]) for j in ids) + ")"
    zmin, zmax, ymin, ymax = (0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (3, 7, 6, 2)
    pat = {"floor": [F(v, zmin) for i, kd, k, v in quads if i == 0], "top": [F(v, zmax) for i, kd, k, v in quads if i == 4],
           "wall": [F(v, ymax) for i, kd, k, v in quads if kd == "outer"],
           "bar": [F(v, ymin) for i, kd, k, v in quads if i == 2 and kd == "inner"] + [F(v, zmax) for i, kd, k, v in quads if i == 1 and kd == "center"]
                  + [F(v, zmin) for i, kd, k, v in quads if i == 3 and kd == "center"]}
    typ = {"floor": "wall", "top": "symmetryPlane", "wall": "wall", "bar": "wall"}
    bd = "".join(f"    {n}\n    {{\n        type {typ[n]};\n        faces\n        (\n" + "".join(f"            {f}\n" for f in fs) + "        );\n    }\n"
                 for n, fs in pat.items())
    return (_hdr("dictionary", "blockMeshDict") + f"scale 1;\n\nvertices\n(\n{vtx});\n\nblocks\n(\n{''.join(blocks)});\n\nedges\n(\n{edges});\n\n"
            f"boundary\n(\n{bd});\n\nmergePatchPairs ();\n")


def _build(p, t):
    g = _geom(p, t)
    m = g["m"]
    Re = m["Re"]
    model = t["model"] if t["model"] != "auto" else ("kEpsilon" if Re >= t["Re_lam"] else "laminar")
    N, nu, omega = m["N"], m["nu"], 2 * math.pi * m["N"]
    utip = math.pi * N * g["L"]
    k0 = 1.5 * (0.05 * utip) ** 2
    e0 = 0.09 ** 0.75 * k0 ** 1.5 / (0.1 * g["r"])
    tend = t["t_end_s"] or min(max(15 * m["theta95"], 10.0), 300.0)
    feed = (0.0, 0.5 * g["r"], g["H"] - 2 * g["dx"])
    rb = 0.1 * g["r"]
    symm = {"top": {"type": "symmetryPlane"}}
    W = ("floor", "wall", "bar")
    fields = {"U": _fld("U", "volVectorField", "[0 1 -1 0 0 0 0]", "uniform (0 0 0)", {w: {"type": "noSlip"} for w in W} | symm),
              "p": _fld("p", "volScalarField", "[0 2 -2 0 0 0 0]", "uniform 0", {w: {"type": "zeroGradient"} for w in W} | symm),
              "s": _fld("s", "volScalarField", "[0 0 0 0 0 0 0]", "uniform 0", {w: {"type": "zeroGradient"} for w in W} | symm)}
    if model == "kEpsilon":
        fields |= {"k": _fld("k", "volScalarField", "[0 2 -2 0 0 0 0]", f"uniform {k0:.8g}",
                             {w: {"type": "kqRWallFunction", "value": f"uniform {k0:.8g}"} for w in W} | symm),
                   "epsilon": _fld("epsilon", "volScalarField", "[0 2 -3 0 0 0 0]", f"uniform {e0:.8g}",
                                   {w: {"type": "epsilonWallFunction", "value": f"uniform {e0:.8g}"} for w in W} | symm),
                   "nut": _fld("nut", "volScalarField", "[0 2 -1 0 0 0 0]", "uniform 0",
                               {w: {"type": "nutkWallFunction", "value": "uniform 0"} for w in W} | symm)}
    F = {f"0/{k}": v for k, v in fields.items()}
    mrf = (_hdr("dictionary", "MRFProperties") + f"MRF1\n{{\n    cellZone rotor;\n    active yes;\n    nonRotatingPatches ();\n"
           f"    origin (0 0 0);\n    axis (0 0 1);\n    omega {omega:.8g};\n}}\n")
    tp = _hdr("dictionary", "transportProperties") + f"transportModel Newtonian;\nnu {nu:.8g};\n"
    mt = _hdr("dictionary", "turbulenceProperties") + (
        "simulationType RAS;\nRAS\n{\n    RASModel kEpsilon;\n    turbulence on;\n    printCoeffs off;\n}\n" if model == "kEpsilon"
        else "simulationType laminar;\n")
    sch = lambda ddt, extra: (_hdr("dictionary", "fvSchemes") + f"ddtSchemes {{ default {ddt}; }}\ngradSchemes {{ default Gauss linear; }}\n"
                              "divSchemes\n{\n    default none;\n    div(phi,U) bounded Gauss linearUpwind grad(U);\n"
                              "    div(phi,k) bounded Gauss limitedLinear 1;\n    div(phi,epsilon) bounded Gauss limitedLinear 1;\n"
                              "    div(phi,s) Gauss limitedLinear 1;\n    div((nuEff*dev2(T(grad(U))))) Gauss linear;\n}\n"
                              "laplacianSchemes { default Gauss linear corrected; }\ninterpolationSchemes { default linear; }\n"
                              "snGradSchemes { default corrected; }\n" + extra)
    ss = '    "(U|k|epsilon|s)(Final)?" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-9; relTol 0.01; }\n'
    sol = (_hdr("dictionary", "fvSolution") + 'solvers\n{\n    "p(Final)?" { solver GAMG; smoother GaussSeidel; tolerance 1e-9; relTol 0.01; }\n' + ss + "}\n\n"
           "SIMPLE\n{\n    nNonOrthogonalCorrectors 1;\n    pRefCell 0;\n    pRefValue 0;\n}\n\n"
           "PIMPLE\n{\n    solveFlow no;\n    momentumPredictor no;\n    nOuterCorrectors 1;\n    nCorrectors 1;\n    nNonOrthogonalCorrectors 1;\n"
           "    pRefCell 0;\n    pRefValue 0;\n}\n\n"
           "relaxationFactors\n{\n    fields { p 0.3; }\n    equations { U 0.7; k 0.7; epsilon 0.7; }\n}\n")
    ctl = lambda app, t0, t1, dt, extra, fo: (_hdr("dictionary", "controlDict") + f"application {app};\nstartFrom startTime;\nstartTime {t0:.8g};\n"
                                              f"stopAt endTime;\nendTime {t1:.8g};\ndeltaT {dt:.8g};\nwriteFormat ascii;\nwritePrecision 8;\n"
                                              f"timeFormat general;\ntimePrecision 8;\nrunTimeModifiable false;\n" + extra + f"functions\n{{\n{fo}}}\n")
    n = int(t["n_iter"])
    forces = ("    forces\n    {\n        type forces;\n        libs (forces);\n        patches (bar);\n        rho rhoInf;\n        rhoInf 1;\n"
              "        CofR (0 0 0);\n        writeControl timeStep;\n        writeInterval 10;\n    }\n")
    tracer = ("    tracer\n    {\n        type scalarTransport;\n        libs (solverFunctionObjects);\n        field s;\n"
              f"        alphaD {1 / t['Sc']:.8g};\n        alphaDt {1 / t['Sct']:.8g};\n        nCorr 1;\n        resetOnStartUp false;\n    }}\n"
              if model == "kEpsilon" else
              "    tracer\n    {\n        type scalarTransport;\n        libs (solverFunctionObjects);\n        field s;\n"
              f"        D {nu / t['Sc']:.8g};\n        nCorr 1;\n        resetOnStartUp false;\n    }}\n")
    F |= {"system/blockMeshDict": _mesh(g), "constant/MRFProperties": mrf, "constant/transportProperties": tp,
          "constant/turbulenceProperties": mt, "system/fvSolution": sol,
          "system/fvSchemes.simple": sch("steadyState", ""), "system/fvSchemes.pimple": sch("Euler", ""),
          "system/controlDict.simple": ctl("simpleFoam", 0, n, 1, f"writeControl timeStep;\nwriteInterval {n};\npurgeWrite 0;\n", forces),
          "system/controlDict.pimple": ctl("pimpleFoam", n, n + tend, tend / 4000,
                                           f"writeControl adjustableRunTime;\nwriteInterval {tend / 60:.8g};\nadjustTimeStep yes;\nmaxCo {t['maxCo']};\n"
                                           f"maxDeltaT {tend / 300:.8g};\n", tracer),
          "system/setFieldsDict": _hdr("dictionary", "setFieldsDict") + "defaultFieldValues ( volScalarFieldValue s 0 );\nregions\n(\n"
              f"    sphereToCell {{ origin {_vec(feed)}; radius {rb:.8g}; fieldValues ( volScalarFieldValue s 1 ); }}\n);\n"}
    F["system/controlDict"] = F["system/controlDict.simple"]
    F["system/fvSchemes"] = F["system/fvSchemes.simple"]
    meta = {"vessel": "flask", "model": model, "Re": Re, "t_simple": n, "t_end_s": tend, "omega": omega, "nu": nu, "rho": m["rho"], "N": N,
            "d": g["L"], "r_cyl": g["r"], "H": g["H"], "Vl": m["Vl"], "feed": feed, "blob_r": rb, "dx": g["dx"],
            "tier1": {"eps": m["eps"], "theta95": m["theta95"], "t_micro": m["t_micro"], "Np": m["Np"]}}
    F["tier2_case.json"] = json.dumps(meta, indent=1)
    return F


BUILD_FLASK = _build


def _split(values):
    v = load_all()["flask"]
    t2 = {d.name: values[d.name] for d in T2_FLASK_DEFS if d.name in values}
    return v, validate(v.defs, {k: x for k, x in values.items() if k not in t2}), validate(T2_FLASK_DEFS, t2)


def write_case_flask(values: dict, outdir) -> pathlib.Path:
    """Canonical-unit flask values (Tier 2 knobs T2_FLASK_DEFS may ride along) -> case dir; run with `bash tier2/run_flask.sh <dir>`."""
    _, p, t = _split(values)
    out = pathlib.Path(outdir)
    for rel, txt in BUILD_FLASK(p, t).items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(txt)
    return out


def _rd(path, n=None):
    """internalField of an ascii OpenFOAM field -> (N,) or (N, ncomp) array; `uniform` needs n."""
    txt = pathlib.Path(path).read_text()
    m = re.search(r"internalField\s+uniform\s+(.*?);", txt)
    if m:
        v = np.array(m.group(1).strip("() ").split(), float)
        return np.full(n, v[0]) if v.size == 1 else np.tile(v, (n, 1))
    m = re.search(r"internalField\s+nonuniform\s+List<\w+>\s*(\d+)\s*\(\n(.*?)\n\)\s*;", txt, re.S)
    a = np.array(m.group(2).replace("(", " ").replace(")", " ").split(), float).reshape(int(m.group(1)), -1)
    return a[:, 0] if a.shape[1] == 1 else a


def _times(out):
    return sorted(((float(d.name), d) for d in out.iterdir() if d.is_dir() and re.fullmatch(r"[0-9.eE+-]+", d.name)), key=lambda x: x[0])


def analyse(outdir) -> dict:
    """Parse a finished case: eps (mean, feed blob), power, Np, tracer theta95 (nan = not reached within the run)."""
    out = pathlib.Path(outdir)
    c = json.loads((out / "tier2_case.json").read_text())
    d0 = out / f"{c['t_simple']:g}"
    V = _rd(d0 / "V")
    C = _rd(d0 / "C", len(V))
    G = _rd(d0 / "grad(U)", len(V)).reshape(-1, 3, 3)
    eps = c["nu"] * (np.einsum("nij,nij->n", G, G) + np.einsum("nij,nji->n", G, G))  # resolved viscous dissipation
    if (d0 / "epsilon").is_file():
        eps = eps + _rd(d0 / "epsilon", len(V))
    Vt = V.sum()
    inb = np.linalg.norm(C - np.array(c["feed"]), axis=1) < c["blob_r"]
    e_mean, e_feed = float((eps * V).sum() / Vt), float((eps * V)[inb].sum() / V[inb].sum())
    N3d5 = c["N"] ** 3 * c["d"] ** 5
    r = dict(eps_mean=e_mean, eps_feed=e_feed, Np_dissip=e_mean * Vt / N3d5, V_liquid=float(Vt), n_cells=len(V), Re=c["Re"], model=c["model"])
    mom = out / "postProcessing" / "forces" / "0" / "moment.dat"
    if mom.is_file():
        row = [ln for ln in mom.read_text().splitlines() if ln.strip() and not ln.lstrip().startswith("#")][-1]
        Mz = abs(float(row.replace("(", " ").replace(")", " ").split()[3]))  # kinematic (rhoInf 1) total moment about z
        r["Np_torque"] = Mz * c["omega"] / N3d5
    th, hist = float("nan"), []
    ts = [(t, d) for t, d in _times(out) if t > c["t_simple"] and (d / "s").is_file()]  # the tracer writes s every step
    for t, d in ts[:: max(1, len(ts) // 200)]:  # ponytail: <= ~200 samples, theta95 resolution = run length / 200
        s = _rd(d / "s", len(V))
        mu = (s * V).sum() / Vt
        hist.append((t - c["t_simple"], float(np.abs(s - mu).max() / mu)))
    for (t1, e1), (t2, e2) in zip(hist, hist[1:]):
        if e2 < 0.05 <= e1:
            th = t1 + (t2 - t1) * (math.log(e1) - math.log(0.05)) / (math.log(e1) - math.log(e2))  # log-linear in the decay
            break
    else:
        if hist and hist[0][1] < 0.05:
            th = hist[0][0]
    r |= dict(theta95=th, tracer_hist=hist)
    return r


def read_results_flask(outdir, values: dict) -> Passport:
    """Solver output -> Tier 2 Passport (derived: epsilon_W_kg, t_micro_s, t_micro_feed_s, t_mix95_s if reached, Np, eps_ratio_feed)."""
    v, p, _ = _split(values)
    r = analyse(outdir)
    nu = json.loads((pathlib.Path(outdir) / "tier2_case.json").read_text())["nu"]
    one = lambda x, u="": Dist(p50=float(x), unit=u)
    mic = lambda e: p["C_micro"] * math.sqrt(nu / e)
    der = {"epsilon_W_kg": one(r["eps_mean"], "W/kg"), "epsilon_feed_W_kg": one(r["eps_feed"], "W/kg"), "t_micro_s": one(mic(r["eps_mean"]), "s"),
           "t_micro_feed_s": one(mic(r["eps_feed"]), "s"), "eps_ratio_feed": one(r["eps_feed"] / r["eps_mean"]), "Np": one(r["Np_dissip"]),
           "Re": one(r["Re"])}
    if not math.isnan(r["theta95"]): der["t_mix95_s"] = one(r["theta95"], "s")
    used = ("volume_mL", "fill_frac", "bar_mm", "stir_rpm", "solvent", "T_C", "mu_factor", "C_micro")
    syn = any(d.source == "synthetic" for d in v.defs if d.name in used)
    return Passport(vessel="flask", site=v.site(p), T_K=one(p["T_C"] + 273.15, "K"), derived=der, source=f"openfoam:{pathlib.Path(outdir).name}",
                    tier=2, synthetic=syn)
