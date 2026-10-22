"""Tier 2 OpenFOAM case writer + result reader for cvd_tube and ampoule (openfoam.com v2512, stock solver only).

Approach: stock `buoyantPimpleFoam` (laminar, compressible, perfect gas, heRhoThermo) for flow + T, with each trace species as a
passive scalar (`scalarTransport` function object, dilute: no feedback on rho/mu). Reasons: no custom compile (the user's
graphiteOxidationFoam derives from scalarTransportFoam and is an on-demand build, not needed here), buoyancy and furnace T
profile come free, and Tier 1 is already dilute-species so the same assumption is being refined, not changed. Chemistry is
absent in Tier 1, so no reactingFoam. Species field = mass fraction (tube) or mole-fraction-like p/P (ampoule).
  cvd_tube: axisymmetric 5-degree wedge (gravity ignored), wall T = vessels.cvd_tube.twall, boats = mixed (Hertz-Knudsen in
            series with gas-side transfer, same law as Tier 1), substrate = absorbing wall strip, cold wall = saturation sink.
  ampoule : buoyantBoussinesqPimpleFoam (own solver, not buoyantPimpleFoam); axisymmetric wedge at |tilt|=90, else half square duct of the
            cylinder's area (see _amp); linear wall T; end faces = Hertz-Knudsen mixed BC about equilibrium p; closed volume; the
            transport rate is the gradient at the sink face (all flux leaves there).
ponytail: D, mu, Cp constant at one T; tube gravity off (axisymmetric); wall re-evaporation only where wall psat < boat psat;
ampoule off-vertical is a square duct not a cylinder; molar mass of AIn not needed (s ~ mole fraction); S as S2.
Untested against a real solver on this machine: see tier2/run.sh."""
import json, math, pathlib
import numpy as np
from core import props
from core.params import ParamDef as P, validate
from core.registry import load_all
from schemas.passport import Dist, Passport

R, G, P_STD, T_STD, IN = props.R, 9.81, 101325.0, 273.15, 0.0254
WEDGE = 5.0  # deg
# ponytail: only genuine Tier 2 knobs; geometry and operation all stay in the vessel ParamDefs
T2_DEFS = [
    P("cells_per_cm", "Axial cells per cm", "1/cm", 4.0, 0.5, 40, group="mesh"),
    P("n_cross", "Cells across radius (tube) / height (ampoule)", "", 10, 4, 100, group="mesh"),
    P("src_refine", "Tube: axial cell density on boats/substrate relative to the rest", "", 1.0, 1, 16, group="mesh"),
    P("wall_grading", "Tube: last/first radial cell size ratio (<1 clusters cells at the wall)", "", 1.0, 0.05, 1, group="mesh"),
    P("max_co", "Tube: maximum Courant number", "", 0.5, 0.1, 5, group="mesh"),
    P("t_end_s", "Physical end time (pseudo-steady)", "s", 600.0, 1, 1e5, group="model"),
    P("species_buoyancy", "Weight of the composition term in the buoyancy (0 = thermal Boussinesq only)", "", 1.0, 0, 1, group="model"),
    P("alpha_ends", "Ampoule end-face Hertz-Knudsen accommodation", "", 1.0, 1e-4, 1.0, source="synthetic", group="model"),
]


def _hdr(cls, obj): return f"FoamFile\n{{\n    version 2.0;\n    format ascii;\n    class {cls};\n    object {obj};\n}}\n\n"
def _vec(v): return "(" + " ".join(f"{x:.8g}" for x in v) + ")"
def _nu(a): return f"nonuniform List<scalar> {len(a)}(\n" + "\n".join(f"{x:.8g}" for x in a) + "\n)"
def _uni(x): return f"uniform {x:.8g}"


def _field(name, cls, dims, internal, patches):
    b = "".join(f"    {k}\n    {{\n" + "".join(f"        {a} {c};\n" for a, c in v.items()) + "    }\n" for k, v in patches.items())
    return _hdr(cls, name) + f"dimensions {dims};\n\ninternalField {internal};\n\nboundaryField\n{{\n{b}}}\n"


def _thermo(gas, T, Pt):
    return _hdr("dictionary", "thermophysicalProperties") + (
        "thermoType\n{\n    type heRhoThermo;\n    mixture pureMixture;\n    transport const;\n    thermo hConst;\n"
        "    equationOfState perfectGas;\n    specie specie;\n    energy sensibleEnthalpy;\n}\n\n"
        f"mixture\n{{\n    specie {{ molWeight {props.mass(gas):.8g}; }}\n    thermodynamics {{ Cp {props.cp_mass(gas):.8g}; Hf 0; }}\n"
        f"    transport {{ mu {props.viscosity(gas, T):.8g}; Pr {props.prandtl(gas, T):.8g}; }}\n}}\n")


def _fv(species, pref=None):
    sp = "".join(f"    div(phi,{s}) Gauss limitedLinear 1;\n" for s in species)  # TVD: upwind's numerical D ~ molecular D here
    sch = (_hdr("dictionary", "fvSchemes") + "ddtSchemes { default Euler; }\ngradSchemes { default Gauss linear; }\n"
           "divSchemes\n{\n    default none;\n    div(phi,U) Gauss linearUpwind grad(U);\n    div(phi,h) Gauss upwind;\n"
           "    div(phi,e) Gauss upwind;\n    div(phi,K) Gauss linear;\n    div(phi,Ekp) Gauss linear;\n"
           "    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;\n" + sp + "}\n"
           "laplacianSchemes { default Gauss linear corrected; }\ninterpolationSchemes { default linear; }\n"
           "snGradSchemes { default corrected; }\n")
    ref = f"    pRefCell 0;\n    pRefValue {pref:.8g};\n" if pref else ""
    sol = (_hdr("dictionary", "fvSolution") + 'solvers\n{\n    "rho.*" { solver diagonal; }\n'
           '    "p_rgh.*" { solver GAMG; smoother GaussSeidel; tolerance 1e-6; relTol 0.01; maxIter 100; }\n'
           '    "(U|h|e|Y_.*).*" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0.1; }\n}\n\n'
           "PIMPLE\n{\n    momentumPredictor no;  // yes gives a spurious radial vortex train on graded meshes (checked)\n    nOuterCorrectors 1;\n    nCorrectors 2;\n    nNonOrthogonalCorrectors 0;\n"
           + ref + "}\n")
    return sch, sol


def _control(t, tend, funcs, dtmax):
    return _hdr("dictionary", "controlDict") + (
        f"application buoyantPimpleFoam;\nstartFrom startTime;\nstartTime 0;\nstopAt endTime;\nendTime {tend:.8g};\ndeltaT 1e-4;\n"
        f"writeControl adjustableRunTime;\nwriteInterval {tend:.8g};\nadjustTimeStep yes;\nmaxCo 0.5;\nmaxDeltaT {dtmax:.8g};\n"
        "writeFormat ascii;\nwritePrecision 8;\ntimeFormat general;\ntimePrecision 6;\nrunTimeModifiable true;\n\n"
        "functions\n{\n" + funcs + "}\n")


def _stf(field, D):
    return (f"    {field}_transport\n    {{\n        type scalarTransport;\n        libs (solverFunctionObjects);\n"
            f"        field {field};\n        D {D:.8g};\n        schemesField {field};\n        resetOnStartUp false;\n"
            "        nCorr 1;\n    }\n")


def _probes(fields, pts):
    return ("    probes\n    {\n        type probes;\n        libs (sampling);\n        fields (" + " ".join(fields) + ");\n"
            "        probeLocations (" + " ".join(_vec(x) for x in pts) + ");\n        writeControl timeStep;\n        writeInterval 20;\n    }\n")


def _segments(p):
    """x-ordered axial segments (kind, x0, x1) in m; boats/substrate are wall strips. Overlap or leaving the tube -> ValueError."""
    L, D = p["L_tube_cm"] / 100, IN * p["tube_id_in"]
    xm = (p["x_MoO3_cm"]) / 100
    ev = sorted([("boatS", p["x_S_boat_cm"] / 100, p["boat_area_S_cm2"] * 1e-4 / (math.pi * D)),  # boat area spread round the wall
                 ("boatMo", xm, p["boat_area_MoO3_cm2"] * 1e-4 / (math.pi * D)),
                 ("substrate", xm + p["x_substrate_cm"] / 100, max(p["substrate_length_cm"] / 100, 1e-3))], key=lambda e: e[1])
    segs, x = [], 0.0
    for k, x0, ln in ev:
        if x0 < x - 1e-9 or x0 + ln > L + 1e-9:
            raise ValueError(f"{k} strip [{x0:.4f},{x0 + ln:.4f}] m overlaps its neighbour or leaves the tube (L={L} m)")
        if x0 > x + 1e-9: segs.append(("tube", x, x0))
        segs.append((k, x0, x0 + ln)); x = x0 + ln
    if x < L - 1e-9: segs.append(("tube", x, L))
    return segs


def _tube_geo(p, t):
    """Mesh geometry shared by the case writer and the reader: segments, axial cells, radial vertices (graded to the wall),
    cell-area fractions, exact wall-normal distance dn of the wall-cell centroid (trapezoidal wedge cell), probe stations."""
    Rr, nc = IN * p["tube_id_in"] / 2, t["n_cross"]
    segs = _segments(p)
    # ponytail: refined = boats, substrate and the stretch between boat and substrate (where the wall sink switches on: its onset must be resolved)
    xe = max(x1 for k, _, x1 in segs if k == "boatMo")
    ns = [max(2, round((x1 - x0) * 100 * t["cells_per_cm"] * (t["src_refine"] if k != "tube" or abs(x0 - xe) < 1e-9 else 1))) for k, x0, x1 in segs]
    ns = [n + (k == "substrate" and n % 2 == 0) for (k, _, _), n in zip(segs, ns)]  # odd: the substrate-centre probe station sits at a cell centre, not on a face
    c = Rr * math.cos(math.radians(WEDGE / 2))
    q = t["wall_grading"] ** (1 / (nc - 1))  # cell j width = w0 q^j (blockMesh ratio = last/first)
    w = (c / nc if abs(q - 1) < 1e-9 else c * (q - 1) / (q**nc - 1)) * q ** np.arange(nc)
    ye = np.r_[0.0, np.cumsum(w)]
    dn = w[-1] * (2 * ye[-2] + c) / (3 * (ye[-2] + c))  # centroid of the wall cell (width grows with y) to the wall face
    xb = {k: (x0, x1) for k, x0, x1 in segs if k != "tube"}
    xr = min(xb["boatMo"][1] + 0.03, 0.5 * (xb["boatMo"][1] + xb["substrate"][0]))  # release station
    return dict(Rr=Rr, nc=nc, segs=segs, ns=ns, c=c, ye=ye, ym=(ye[1:] + ye[:-1]) / 2, af=(ye[1:]**2 - ye[:-1]**2) / c**2, dn=dn,
                xr=xr, xs=0.5 * sum(xb["substrate"]), s=Rr * math.sin(math.radians(WEDGE / 2)))


def _tube_species(p):
    """(mass M of the transported unit, saturation law, boat molecule mass, atoms per saturation molecule) per species.
    Transported scalar = mass fraction of Mo-bearing vapour (MoO3-formula-unit basis) / of S atoms, so Y does not depend on speciation."""
    from vessels.cvd_tube import psat_MoO3, psat_S
    nol = int(p["MoO3.n_oligomer"])
    s2 = p["S.speciation"] == "S2" or p["thermo_basis"] == "legacy_synthetic"
    return {"MoO3": (props.mass("MoO3") * 1e-3, lambda T: psat_MoO3(p, T), nol * props.mass("MoO3") * 1e-3, 1),
            "S2": (32.06e-3, lambda T: (2 if s2 else 8) * psat_S(p, T), (64.13 if s2 else 256.52) * 1e-3, 1)}


def _hk(Mmol, ysat, Tb, alpha, D, dn, Pt, Mc):
    """Mixed-BC (refValue, valueFraction) for a boat: Hertz-Knudsen of the vapour MOLECULE (mass Mmol) in series with the gas-side
    film rho D/dn, dn = exact wall-cell centroid distance (so the BC is the Robin law flux = h (ref - Y_wall) at any mesh)."""
    h = alpha / math.sqrt(2 * math.pi * Mmol * R * Tb) * Pt * Mc  # kg/m2/s per unit mass-fraction difference (M cancels)
    return min(ysat, 1.0), h / (h + Pt * Mc / (R * Tb) * D / dn)


def _tube(p, t):
    from vessels.cvd_tube import twall, thermo
    g = _tube_geo(p, t)
    Rr, Pt, car = g["Rr"], p["pressure_Pa"], p["carrier"]
    Mc, Tf, Te = props.mass(car) * 1e-3, p["T_furnace_C"] + 273.15, p["T_ends_C"] + 273.15
    segs, ns, nc, c, s, dn = g["segs"], g["ns"], g["nc"], g["c"], g["s"], g["dn"]
    xc = {k: np.zeros(0) for k in ("tube", "boatS", "boatMo", "substrate")}
    for (k, x0, x1), n in zip(segs, ns): xc[k] = np.r_[xc[k], x0 + (np.arange(n) + .5) * (x1 - x0) / n]
    end = {k: x1 for k, _, x1 in segs if k != "tube"}
    N = len(segs)
    xb = [segs[0][1]] + [sg[2] for sg in segs]  # vertices per station i: 3i axis, 3i+1 outer z<0, 3i+2 outer z>0
    vtx = "".join(f"    ({x:.8g} 0 0)\n    ({x:.8g} {c:.8g} {-s:.8g})\n    ({x:.8g} {c:.8g} {s:.8g})\n" for x in xb)
    blk = "".join(f"    hex ({3*i} {3*i+3} {3*i+4} {3*i+1} {3*i} {3*i+3} {3*i+5} {3*i+2}) ({n} {nc} 1) simpleGrading (1 {t['wall_grading']:.8g} 1)\n"
                  for i, n in enumerate(ns))  # axis vertices repeated: collapsed edge, wedge about x
    def patch(name, typ, kinds, face):
        f = "".join(f"        {face(i)}\n" for i, (k, _, _) in enumerate(segs) if k in kinds)
        return f"    {name}\n    {{\n        type {typ};\n        faces\n        (\n{f}        );\n    }}\n"
    allk = tuple(xc)
    wallf = lambda i: f"({3*i+1} {3*i+2} {3*i+5} {3*i+4})"
    bmd = (_hdr("dictionary", "blockMeshDict") + f"scale 1;\n\nvertices\n(\n{vtx});\n\nblocks\n(\n{blk});\n\nedges ();\n\nboundary\n(\n"
           + "    inlet\n    {\n        type patch;\n        faces ( (0 0 2 1) );\n    }\n"
           + f"    outlet\n    {{\n        type patch;\n        faces ( ({3*N} {3*N+1} {3*N+2} {3*N}) );\n    }}\n"
           + patch("wall", "wall", ("tube",), wallf) + patch("boatS", "wall", ("boatS",), wallf)
           + patch("boatMo", "wall", ("boatMo",), wallf) + patch("substrate", "wall", ("substrate",), wallf)
           + patch("wedgeF", "wedge", allk, lambda i: f"({3*i} {3*i+1} {3*i+4} {3*i+3})")
           + patch("wedgeB", "wedge", allk, lambda i: f"({3*i} {3*i+3} {3*i+5} {3*i+2})") + ");\n\nmergePatchPairs ();\n")
    # fields
    Tw = twall(p, xc["tube"])
    Tsub = twall(p, xc["substrate"]) + p["T_substrate_offset_K"]
    nol = int(p["MoO3.n_oligomer"]); s2 = p["S.speciation"] == "S2" or p["thermo_basis"] == "legacy_synthetic"
    D_ = {"MoO3": thermo.fuller_D(car, "MoO3", Tf, Pt, nol) * p["D_scale"],  # ponytail: one D per species at furnace T (Tier 1: local T^1.75)
          "S2": thermo.fuller_D(car, "S2", Tf, Pt) * p["D_scale"]}  # S atoms diffuse as S2 (Tier 1 wall transfer); S8 at the boat not resolved
    sp_ = {"MoO3": ("Y_MoO3", p["T_boat_Mo_C"] + 273.15, p["alpha_MoO3"], "boatMo"), "S2": ("Y_S2", p["T_boat_S_C"] + 273.15, p["alpha_S"], "boatS")}
    fa = {"inlet": {"type": "fixedValue", "value": "uniform 0"}, "outlet": {"type": "inletOutlet", "inletValue": "uniform 0", "value": "uniform 0"},
          "wedgeF": {"type": "wedge"}, "wedgeB": {"type": "wedge"}}
    Y = {}
    for sname, (fld, Tb, alpha, boat) in sp_.items():
        Mu, sat, Mmol, _ = _tube_species(p)[sname]
        ys = lambda T: np.minimum(sat(T) / Pt * Mu / Mc, 1.0)  # saturation mass fraction
        ref, f = _hk(Mmol, float(ys(Tb)), Tb, alpha, D_[sname], dn, Pt, Mc)
        sink = lambda T, ok: {"type": "mixed", "refValue": _nu(ys(T)), "refGradient": "uniform 0", "valueFraction": _nu(((ys(T) < ref) & ok).astype(float)),
                              "value": "uniform 0"}  # cold wall / substrate can only take up; hot one must not feed (Tier 1 has no re-evaporation)
        pat = {k: {"type": "zeroGradient"} for k in ("boatS", "boatMo")}
        pat[boat] = {"type": "mixed", "refValue": _uni(ref), "refGradient": "uniform 0", "valueFraction": _uni(f), "value": "uniform 0"}
        pat |= {"wall": sink(Tw, xc["tube"] > end[boat]), "substrate": sink(Tsub, np.ones(len(Tsub), bool))}
        Y[fld] = _field(fld, "volScalarField", "[0 0 0 0 0 0 0]", "uniform 0", fa | pat)
    walls = ("wall", "boatS", "boatMo", "substrate")
    mdot = P_STD * p["flow_sccm"] * 1e-6 / 60 / (R * T_STD) * Mc * WEDGE / 360
    wd = {"wedgeF": {"type": "wedge"}, "wedgeB": {"type": "wedge"}}
    Tb_ = {"boatS": p["T_boat_S_C"] + 273.15, "boatMo": p["T_boat_Mo_C"] + 273.15}
    F = {"U": _field("U", "volVectorField", "[0 1 -1 0 0 0 0]", "uniform (0 0 0)",
                     {"inlet": {"type": "flowRateInletVelocity", "massFlowRate": f"constant {mdot:.8g}", "value": "uniform (0 0 0)"},
                      "outlet": {"type": "inletOutlet", "inletValue": "uniform (0 0 0)", "value": "uniform (0 0 0)"}}
                     | {k: {"type": "noSlip"} for k in walls} | wd),
         "T": _field("T", "volScalarField", "[0 0 0 1 0 0 0]", _nu(np.concatenate([np.tile(twall(p, x0 + (np.arange(n) + .5) * (x1 - x0) / n), nc)
                                                                                 for (_, x0, x1), n in zip(segs, ns)])),  # start on the wall profile: no expansion transient
                     {"inlet": {"type": "fixedValue", "value": _uni(Te)}, "outlet": {"type": "inletOutlet", "inletValue": _uni(Te), "value": _uni(Te)},
                      "wall": {"type": "fixedValue", "value": _nu(Tw)}, "substrate": {"type": "fixedValue", "value": _nu(Tsub)}}
                     | {k: {"type": "fixedValue", "value": _uni(v)} for k, v in Tb_.items()} | wd),
         "p": _field("p", "volScalarField", "[1 -1 -2 0 0 0 0]", _uni(Pt),
                     {k: {"type": "calculated", "value": _uni(Pt)} for k in ("inlet", "outlet") + walls} | wd),
         "p_rgh": _field("p_rgh", "volScalarField", "[1 -1 -2 0 0 0 0]", _uni(Pt),
                         {"inlet": {"type": "fixedFluxPressure", "value": _uni(Pt)}, "outlet": {"type": "fixedValue", "value": _uni(Pt)}}
                         | {k: {"type": "fixedFluxPressure", "value": _uni(Pt)} for k in walls} | wd)}
    F = {f"0/{k}": v for k, v in (F | Y).items()}
    # probes sit on the z=0 plane at the cell-centre height ym
    pts = [(x, y, 0) for x in (g["xr"], g["xs"]) for y in g["ym"]]  # radial rows at the release and the substrate-centre stations
    funcs = (_stf("Y_MoO3", D_["MoO3"]) + _stf("Y_S2", D_["S2"]) + _probes(("T", "Y_MoO3", "Y_S2", "U"), pts))
    sch, sol = _fv(("Y_MoO3", "Y_S2"))
    tend = t["t_end_s"]
    ctl = _control(t, tend, funcs, 1.0).replace("maxCo 0.5", f"maxCo {t['max_co']:.8g}")
    F |= {"system/blockMeshDict": bmd, "system/controlDict": ctl, "system/fvSchemes": sch, "system/fvSolution": sol,
          "constant/thermophysicalProperties": _thermo(car, Tf, Pt), "constant/g": _gfile((0, 0, 0)), "constant/pRef": _pref(Pt)}
    return F


def _gfile(g):
    return _hdr("uniformDimensionedVectorField", "g") + f"dimensions [0 1 -2 0 0 0 0];\nvalue {_vec(g)};\n"


def _pref(Pt): return _hdr("uniformDimensionedScalarField", "pRef") + f"dimensions [1 -1 -2 0 0 0 0];\nvalue {Pt:.8g};\n"


def _amp(p, t):
    """Ampoule case for stock buoyantBoussinesqPimpleFoam (incompressible, T, p_rgh, species as scalarTransport).
    |tilt| = 90: axisymmetric 5-degree wedge (cylinder of D_mm x L_cm, gravity along the axis). Any other tilt breaks axisymmetry,
    so use a half-box (symmetry plane z=0 holds the axis and gravity) of the same cross-section AREA as the cylinder: a square duct
    is not a cylinder, wall drag/convection differ (limitation, ponytail). End faces: Hertz-Knudsen mixed BC about the equilibrium
    fraction (Tier 1 DH/DS via _pC), f = k/(k + D c/dn); Tier 1's Q/K drive max(0, 1-Q/K) is the same law written one-sided; with
    solid on both ends the net exchange is two-way, so the BC is symmetric."""
    from vessels.ampoule import _core
    c = _core(p)
    L, Dm, Pt, Tm = p["L_cm"] / 100, p["D_mm"] / 1000, c["Ptot"], c["T"]
    T2, T1 = p["T_source_C"] + 273.15, p["T_sink_C"] + 273.15
    nx, ny = max(4, round(L * 100 * t["cells_per_cm"])), t["n_cross"]
    th = math.radians(p["tilt_deg"])
    g = (-G * math.sin(th), -G * math.cos(th), 0.0)  # +tilt: source end (x=0) lower, so "down" points toward -x
    wedge = abs(p["tilt_deg"]) == 90
    if wedge:
        Rr = Dm / 2; cc, s = Rr * math.cos(math.radians(WEDGE / 2)), Rr * math.sin(math.radians(WEDGE / 2)); dn = Rr / ny / 2
        vtx = "".join(f"    ({x:.8g} 0 0)\n    ({x:.8g} {cc:.8g} {-s:.8g})\n    ({x:.8g} {cc:.8g} {s:.8g})\n" for x in (0, L))
        blk, nz = f"hex (0 3 4 1 0 3 5 2) ({nx} {ny} 1) simpleGrading (1 1 1)", 1
        faces = {"source": ("patch", "(0 0 2 1)"), "sink": ("patch", "(3 4 5 3)"), "walls": ("wall", "(1 2 5 4)"),
                 "wedgeF": ("wedge", "(0 3 4 1)"), "wedgeB": ("wedge", "(0 3 5 2)")}
        side = {"wedgeF": "wedge", "wedgeB": "wedge"}
    else:
        a = Dm * math.sqrt(math.pi) / 2; zw = a / 2; nz = max(2, ny // 2); dn = a / ny / 2  # equal-area square, half of it
        vtx = "".join(f"    ({x:.8g} {y:.8g} {z:.8g})\n" for z in (0, zw) for x, y in ((0, 0), (L, 0), (L, a), (0, a)))
        blk = f"hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)"
        faces = {"source": ("patch", "(0 4 7 3)"), "sink": ("patch", "(1 2 6 5)"), "walls": ("wall", "(0 1 5 4) (3 7 6 2) (4 5 6 7)"),
                 "sym": ("symmetryPlane", "(0 3 2 1)")}
        side = {"sym": "symmetryPlane"}
    bnd = "".join(f"    {k}\n    {{\n        type {ty};\n        faces ( {f} );\n    }}\n" for k, (ty, f) in faces.items())
    bmd = (_hdr("dictionary", "blockMeshDict") + f"scale 1;\n\nvertices\n(\n{vtx});\n\nblocks\n(\n    {blk}\n);\n\nedges ();\n\nboundary\n(\n{bnd});\n")
    xc = (np.arange(nx) + .5) * L / nx
    tile = lambda f: _nu(np.tile(f, ny * nz))  # blockMesh cells run x fastest; ponytail: initial profiles linear in x
    sh = lambda ref, k: {"type": "mixed", "refValue": _uni(ref), "refGradient": "uniform 0", "valueFraction": _uni(k), "value": _uni(ref)}
    s2, s1 = c["p2"] / Pt, c["p1"] / Pt
    M = props.mass("I2") * 1e-3  # ponytail: molar mass of AIn taken as I2's (kinetic prefactor only)
    cD = c["D"] * Pt / (R * Tm) / dn  # gas-side molar transfer per unit s
    fk = lambda T: (lambda k: k / (k + cD))(t["alpha_ends"] * Pt / math.sqrt(2 * math.pi * M * R * T))
    sd = {k: {"type": ty} for k, ty in side.items()}
    ends = lambda v: {k: v for k in ("source", "sink")}
    prof = lambda a, b: {"type": "fixedProfile", "profile": f"polynomial (({a:.8g} 0) ({(b - a) / L:.8g} 1))", "direction": "(1 0 0)", "origin": "0"}
    F = {"U": _field("U", "volVectorField", "[0 1 -1 0 0 0 0]", "uniform (0 0 0)", {k: {"type": "noSlip"} for k in ("walls", "source", "sink")} | sd),
         "T": _field("T", "volScalarField", "[0 0 0 1 0 0 0]", tile(T2 + (T1 - T2) * xc / L),
                     {"walls": prof(T2, T1), "source": {"type": "fixedValue", "value": _uni(T2)}, "sink": {"type": "fixedValue", "value": _uni(T1)}} | sd),
         "p": _field("p", "volScalarField", "[0 2 -2 0 0 0 0]", "uniform 0", ends({"type": "calculated", "value": "uniform 0"}) | {"walls": {"type": "calculated", "value": "uniform 0"}} | sd),
         "p_rgh": _field("p_rgh", "volScalarField", "[0 2 -2 0 0 0 0]", "uniform 0",
                         {k: {"type": "fixedFluxPressure", "rho": "rhok", "value": "uniform 0"} for k in ("walls", "source", "sink")} | sd),
         "alphat": _field("alphat", "volScalarField", "[0 2 -1 0 0 0 0]", "uniform 0",
                          {k: {"type": "calculated", "value": "uniform 0"} for k in ("walls", "source", "sink")} | sd),
         "Y_AIn": _field("Y_AIn", "volScalarField", "[0 0 0 0 0 0 0]", tile(s2 + (s1 - s2) * xc / L),
                         {"walls": {"type": "zeroGradient"}, "source": sh(s2, fk(T2)), "sink": sh(s1, fk(T1))} | sd)}
    F = {f"0/{k}": v for k, v in F.items()}
    M = np.array([p["agent_M_gmol"], p["M_X_gmol"], p["M_A_gmol"] + p["n_I_per_C"] * p["M_X_gmol"], p["E_M_gmol"], p["M_A_gmol"] + p["n2_I_per_C"] * p["M_X_gmol"]])
    Mbar = lambda ps: (float(np.dot([ps[k] for k in ("B", "X", "C1", "E1", "C2")], M)) + c["pAr"] * props.mass("Ar")) / (sum(ps.values()) + c["pAr"])
    M2, M1 = Mbar(c["s2"]), Mbar(c["s1"])  # mean molar mass at each end (g/mol); ponytail: p_C1 as the only varying fraction, other species follow it
    betaS = -t["species_buoyancy"] * (M2 - M1) / (s2 - s1) / (0.5 * (M1 + M2))  # rho ~ M: rhok = 1 - betaS (Y - Yref)
    rho = 0.5 * (M1 + M2) * 1e-3 * Pt / (R * Tm)  # kg/m3, mixture, as Tier 1 uses for nu
    nu, Pr = props.viscosity(p["gas"], Tm) / rho, props.prandtl(p["gas"], Tm)
    tp = (_hdr("dictionary", "transportProperties") + f"transportModel Newtonian;\nnu {nu:.8g};\nbeta {1 / Tm:.8g};\nTRef {Tm:.8g};\n"
          f"Pr {Pr:.8g};\nPrt 1;\n")  # ponytail: beta = 1/Tm (ideal gas), thermal only; species density effect ignored
    ap = _hdr("dictionary", "ampouleProperties") + f"betaS {betaS:.8g};\nYref {0.5 * (s1 + s2):.8g};\nDy {c['D']:.8g};\n"
    funcs = (_probes(("T", "Y_AIn"), [(0.5 * L / nx, dn, 1e-4 * dn), (L - 0.5 * L / nx, dn, 1e-4 * dn)])
             + "    gradY\n    {\n        type grad;\n        libs (fieldFunctionObjects);\n        field Y_AIn;\n        writeControl none;\n    }\n"
             "    sinkFlux\n    {\n        type surfaceFieldValue;\n        libs (fieldFunctionObjects);\n        log false;\n"
             "        writeFields false;\n        regionType patch;\n        name sink;\n        operation areaNormalAverage;\n"
             "        fields (grad(Y_AIn));\n        writeControl timeStep;\n        writeInterval 20;\n    }\n")
    sch = (_hdr("dictionary", "fvSchemes") + "ddtSchemes { default Euler; }\ngradSchemes { default Gauss linear; }\n"
           "divSchemes\n{\n    default none;\n    div(phi,U) Gauss linearUpwind grad(U);\n    div(phi,T) Gauss limitedLinear 1;\n"
           "    div(phi,Y_AIn) Gauss limitedLinear 1;\n    div((nuEff*dev2(T(grad(U))))) Gauss linear;\n}\n"
           "laplacianSchemes { default Gauss linear corrected; }\ninterpolationSchemes { default linear; }\nsnGradSchemes { default corrected; }\n")
    sol = (_hdr("dictionary", "fvSolution") + "solvers\n{\n    p_rgh { solver PCG; preconditioner DIC; tolerance 1e-10; relTol 0.01; }\n"
           "    p_rghFinal { solver PCG; preconditioner DIC; tolerance 1e-10; relTol 0; }\n"
           '    "(U|T|Y_AIn)" { solver PBiCGStab; preconditioner DILU; tolerance 1e-12; relTol 0.01; }\n'
           '    "(U|T|Y_AIn)Final" { solver PBiCGStab; preconditioner DILU; tolerance 1e-12; relTol 0; }\n}\n\n'
           "PIMPLE\n{\n    momentumPredictor no;\n    nOuterCorrectors 1;\n    nCorrectors 2;\n    nNonOrthogonalCorrectors 0;\n    pRefCell 0;\n    pRefValue 0;\n}\n")
    ctl = _control(t, t["t_end_s"], funcs, t["t_end_s"] / 200).replace("buoyantPimpleFoam", "ampouleBoussinesqFoam")
    F |= {"system/blockMeshDict": bmd, "system/controlDict": ctl, "system/fvSchemes": sch, "system/fvSolution": sol,
          "constant/transportProperties": tp, "constant/ampouleProperties": ap, "constant/g": _gfile(g)}
    return F


BUILD = {"cvd_tube": _tube, "ampoule": _amp}


def _split(vessel, values):
    v = load_all()[vessel]
    t2 = {d.name: values[d.name] for d in T2_DEFS if d.name in values}
    return v, validate(v.defs, {k: x for k, x in values.items() if k not in t2}), validate(T2_DEFS, t2)


RUNNER = {"cvd_tube": "run.sh", "ampoule": "run.sh", "flask": "run_flask.sh"}  # script in tier2/ that runs a case dir of each vessel


def write_case(vessel: str, values: dict, outdir) -> pathlib.Path:
    """Canonical-unit values (same dict as Tier 1; Tier 2 mesh/time knobs T2_DEFS may ride along) -> runnable case dir.
    flask: delegated to tier2.flask.write_case_flask (own knobs T2_FLASK_DEFS, MRF rotating zone); run it with tier2/run_flask.sh."""
    if vessel == "flask":
        from tier2.flask import write_case_flask
        return write_case_flask(values, outdir)
    if vessel not in BUILD: raise ValueError(f"no OpenFOAM template for {vessel!r}; have {sorted(BUILD)}")
    _, p, t = _split(vessel, values)
    out = pathlib.Path(outdir)
    files = BUILD[vessel](p, t) | {"constant/turbulenceProperties": _hdr("dictionary", "turbulenceProperties") + "simulationType laminar;\n",
                                    "tier2_case.json": json.dumps({"vessel": vessel, "values": p, "tier2": t}, indent=1)}
    for rel, txt in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(txt)
    return out


def _last(path):
    """Last data row of an OpenFOAM probes / surfaceFieldValue file (skip '#'), as floats, time column dropped."""
    rows = [ln.split() for ln in pathlib.Path(path).read_text().splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    return [float(x.strip("()")) for x in rows[-1][1:]]


def _find(out, d, name):  # latest time dir of a postProcessing function object
    runs = sorted((out / "postProcessing" / d).iterdir(), key=lambda q: float(q.name))
    return runs[-1] / name


def _rows(path):  # whole probes file as a float array (time + values), '#' lines and parentheses dropped
    return np.array([[float(x.strip("()")) for x in ln.split()] for ln in pathlib.Path(path).read_text().splitlines()
                     if ln.strip() and not ln.lstrip().startswith("#")])


def tube_fields(out, p, t):
    """Flow-weighted (cup-mixing) bulk values at the release and substrate-centre stations from the radial probe rows, per time row.
    Returns dict station -> {T, pM (MoO3-unit Pa), pSatoms (Pa), N_Mo (mol/s, full tube), axis_pM}; station 0 = release, 1 = substrate."""
    g = _tube_geo(p, t)
    nc, Pt, Mc = g["nc"], p["pressure_Pa"], props.mass(p["carrier"]) * 1e-3
    R_ = {f: _rows(_find(out, "probes", f)) for f in ("T", "Y_MoO3", "Y_S2", "U")}
    ux = R_["U"][:, 1::3]
    res = {}
    for k in (0, 1):
        sl = slice(k * nc, (k + 1) * nc)
        T, YM, YS = R_["T"][:, 1:][:, sl], R_["Y_MoO3"][:, 1:][:, sl], R_["Y_S2"][:, 1:][:, sl]
        w = g["af"] * Pt * Mc / (R * T) * ux[:, sl]  # mass flow per unit section area share
        W = w.sum(1)
        bulk = lambda f: (w * f).sum(1) / W
        Am = g["c"] * g["s"] * 360 / WEDGE  # full-tube section area (wedge triangle x 72)
        res[k] = dict(t=R_["T"][:, 0], T=bulk(T), pM=bulk(YM) * Pt * Mc / (props.mass("MoO3") * 1e-3), pSa=bulk(YS) * Pt * Mc / 32.06e-3,
                      N_Mo=(w * YM).sum(1) * Am / (props.mass("MoO3") * 1e-3), axis_pM=YM[:, 0] * Pt * Mc / (props.mass("MoO3") * 1e-3))
    return res


def _read_tube(out, v, p, t, syn, src):
    from vessels.cvd_tube import psat_MoO3, twall, thermo
    Pt, Mc = p["pressure_Pa"], props.mass(p["carrier"]) * 1e-3
    one = lambda x, u="": Dist(p50=float(x), unit=u)
    pr = lambda f: _last(_find(out, "probes", f))
    if len(pr("Y_MoO3")) == 1:  # single-probe layout (old / fake fixture): near-axis point value
        T, ym, ys = pr("T")[0], pr("Y_MoO3")[0], pr("Y_S2")[0]
        pM, pS = ym * Pt * Mc / (props.mass("MoO3") * 1e-3), ys * Pt * Mc / (props.mass("S2") * 1e-3)  # dilute: x = Y Mc/M
        return Passport(vessel="cvd_tube", site=v.site(p), T_K=one(T, "K"),
                        species={"MoO3_g": {"p_Pa": one(pM, "Pa")}, "S2_g": {"p_Pa": one(pS, "Pa")}},
                        derived={"ratio_Mo_S": one(pM / max(pS, 1e-30)), "supersaturation_MoO3": one(pM / float(psat_MoO3(p, T)))},
                        source=src, tier=2, synthetic=syn)
    f = tube_fields(out, p, t)
    rel, sub = f[0], f[1]
    Tg, pM, pSa = sub["T"][-1], sub["pM"][-1], sub["pSa"][-1]
    s2 = p["S.speciation"] == "S2" or p["thermo_basis"] == "legacy_synthetic"
    xS = 1.0 if s2 else float(thermo.s2_fraction(pSa / Pt, Tg, Pt, p["S.dHf_S8_kJ"]))  # S atoms as S2, as Tier 1's post pass
    pS = pSa * xS / 2
    g = _tube_geo(p, t)
    Tw = float(twall(p, np.array([g["xs"]]))[0]) + p["T_substrate_offset_K"]
    late = (sub["t"] <= 0.75 * sub["t"][-1]).nonzero()[0]
    drift = max(abs(sub[k][-1] / sub[k][late[-1]] - 1) for k in ("pM", "pSa")) if len(late) else float("nan")  # change over the last quarter, worse of Mo and S
    return Passport(vessel="cvd_tube", site=v.site(p), T_K=one(Tg, "K"),
                    species={"MoO3_g": {"p_Pa": one(pM, "Pa")}, "S2_g": {"p_Pa": one(pS, "Pa")}},
                    derived={"ratio_Mo_S": one(pM / max(pS, 1e-30)), "supersaturation_MoO3": one(pM / float(psat_MoO3(p, Tg))),
                             "supersaturation_MoO3_wallT": one(pM / float(psat_MoO3(p, Tw))), "T_wall_K": one(Tw, "K"),
                             "MoO3_released_mol_s": one(rel["N_Mo"][-1], "mol/s"), "MoO3_at_substrate_mol_s": one(sub["N_Mo"][-1], "mol/s"),
                             "T_gas_release_K": one(rel["T"][-1], "K"), "p_MoO3_axis_Pa": one(sub["axis_pM"][-1], "Pa"),
                             "S2_fraction_of_S": one(xS), "drift_last_quarter": one(drift)},
                    source=src, tier=2, synthetic=syn)


def read_results(outdir, vessel: str, values: dict) -> Passport:
    """Parse solver output into a Tier 2 Passport. Needs postProcessing/{probes,sinkFlux} as written by write_case."""
    out = pathlib.Path(outdir)
    if vessel == "flask":
        from tier2.flask import read_results_flask
        return read_results_flask(out, values)
    v, p, _ = _split(vessel, values)
    syn = any(d.source == "synthetic" for d in v.defs)  # ponytail: provenance not passed in; any synthetic ParamDef flags the run
    one = lambda x, u="": Dist(p50=float(x), unit=u)
    src = f"openfoam:{out.name}"
    pr = lambda f: _last(_find(out, "probes", f))
    if vessel == "cvd_tube":
        cj = out / "tier2_case.json"
        return _read_tube(out, v, p, json.loads(cj.read_text())["tier2"] if cj.exists() else _split(vessel, values)[2], syn, src)
    from vessels.ampoule import _core
    c = _core(p)
    T0, T1 = pr("T")
    s0, s1 = pr("Y_AIn")
    grad = _last(_find(out, "sinkFlux", "surfaceFieldValue.dat"))[0]  # mean n.grad(s) on sink, n outward (+x)
    J = -c["D"] * c["Ptot"] / (R * c["T"]) * grad  # mol/m2/s leaving through the sink = total transport (closed ampoule)
    return Passport(vessel=vessel, site=v.site(p), T_K=one(T1, "K"),
                    species={"AIn_g": {"p_source_Pa": one(s0 * c["Ptot"], "Pa"), "p_sink_Pa": one(s1 * c["Ptot"], "Pa")}},
                    derived={"flux_total_mol_m2_s": one(J, "mol/m2/s"), "convection_enhancement": one(J / c["J"]),
                             "transport_rate_mmol_h": one(J * c["area"] * 3.6e6)},
                    source=src, tier=2, synthetic=syn)
