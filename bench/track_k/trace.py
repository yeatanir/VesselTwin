"""Track K read-only trace: boat release -> substrate flux (no model change). python -m bench.track_k.trace"""
import numpy as np
from core import api
from vessels.cvd_tube import march, psat_MoO3, IN, R, P_STD, T_STD
import vessels.cvd_tube as V


def trace(**kw):
    p = api.defaults("cvd_tube"); p.update(kw)
    x, T, o, m = march(p)
    xc, xs0 = m["xcen"], (p["x_MoO3_cm"] + p["x_substrate_cm"]) / 100
    ic = int(np.searchsorted(x, xc)); iM = int(np.argmin(abs(x - p["x_MoO3_cm"] / 100)))
    Twe = m["Twe"]; ps = psat_MoO3(p, Twe)
    nol = int(p["MoO3.n_oligomer"]); Pt = p["pressure_Pa"]
    return dict(NM_in=m["NM_in"], NM_out=m["NM_out"], frac_sub=m["dep"]["Msub"] / m["NM_in"], pM_sub=o["pM"][ic], psat_wall_sub=float(ps[ic]),
                ss_sub=o["ss"][ic], flux=o["flux"][ic], Tw_sub=Twe[ic], Tw_boat=Twe[iM], psat_wall_boat=float(ps[iM]), pM_boat=o["pM"][iM],
                NM_sub=o["NM"][ic], Nsat_sub=float(ps[ic] * o["Nt"][ic] / Pt), dep_up=o["dM"][iM:ic].sum(), ic=ic, iM=iM, o=o, x=x, ps=ps, p=p, m=m)


if __name__ == "__main__":
    for lab, kws in [("boat T", [dict(T_boat_Mo_C=t) for t in (800, 825, 850)]), ("flow", [dict(flow_sccm=f) for f in (50, 100, 200)]),
                     ("boat T 700 (default)", [dict()])]:
        for kw in kws:
            r = trace(**kw)
            print(lab, kw, {k: (f"{v:.4g}" if isinstance(v, float) else v) for k, v in r.items() if k not in ("o", "x", "ps", "p", "m")})


L = {"MoO3.psat_model": "smolik_liquid_cc"}


def ntu_cum(r):
    """Cumulative wall NTU boat -> substrate centre, backed out of the marched uptake per cell: -ln((N_out-Nsat)/(N_in-Nsat))."""
    o, iM, ic = r["o"], r["iM"], r["ic"]
    Pt, tot = r["p"]["pressure_Pa"], 0.0
    for i in range(iM, ic + 1):
        Nin = o["NM"][i] + o["dM"][i]
        Nsat = r["ps"][i] * o["Nt"][i] / Pt
        if Nin > Nsat and o["NM"][i] > Nsat:
            tot += -np.log((o["NM"][i] - Nsat) / (Nin - Nsat))
    return tot


def elasticity(**kw):
    a, b = trace(T_boat_Mo_C=800, **L, **kw), trace(T_boat_Mo_C=850, **L, **kw)
    return np.log(b["flux"] / a["flux"]) / np.log(b["NM_in"] / a["NM_in"]), ntu_cum(a), a["flux"], b["flux"]


if __name__ == "__main__":
    print("\nelasticity e = dlnF/dlnNM_in (boat 800->850, liquid law), NTU boat->substrate centre")
    for xs in (0.5, 1, 2, 4, 8, 12):
        e, n, fa, fb = elasticity(x_substrate_cm=xs); print(f"x_sub={xs:5} cm  NTU={n:8.2f}  e={e:7.3f}  F800={fa:.4g} F850={fb:.4g}")
    for f in (50, 100, 200):
        e, n, fa, fb = elasticity(flow_sccm=f); print(f"flow={f:4}        NTU={n:8.2f}  e={e:7.3f}  F800={fa:.4g} F850={fb:.4g}")
