"""Track M scoring, exactly as pre-registered in docs/prereg/track-m.md.
  python -m bench.track_m_score --flux            -> bench/track_m/flux_vs_distance.json (M3, default conditions, no benchmark data)
  python -m bench.track_m_score --score --write   -> bench/track_m/results.json (M4; run ONCE after the pre-registration commit)
Imports bench.track_a_score, bench.track_i_score.tables and bench.track_l_score (edits none of them). Nothing here is tuned to a benchmark item."""
import argparse, json, os
import numpy as np
from bench import track_a_score as A, track_i_score as I, track_l_score as L
from core import params as P, uq
from vessels.cvd_tube import growth, reactive as R, thermo, wulff

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = f"{HERE}/track_m"
NMC, NPTS, TOL, THR = A.NMC, A.NPTS, A.TOL, 0.8  # 100 draws, 5 sweep points, 0.05 ln units, P threshold
SIG = {"T_substrate_offset_K": 30.0}  # M2: substrate temperature unstated by every paper -> wide scoped sigma (K)
COMBOS = [(s, w) for s in R.SUB_MODELS for w in R.WALL_MODELS]  # 8 structural cells, equal weight
N_SHAPE = 8  # structural samples per cell for the s11 shape item
DIST = [0.5, 1, 2, 3, 4, 6, 8, 10, 12, 15, 20]  # cm, substrate leading edge downstream of the MoO3 boat
STICK = [1e-4, 1e-2, 1.0]
WALLV = [("condensation", {}), ("reflecting", {}), ("reactive", {})] + [(f"sticking_{s:g}", {"wall_sticking": s}) for s in STICK]


def struct(sub, wall, rs):
    """Structural constants for one ensemble member: uniform over the stated synthetic ranges (always draws 4 numbers so streams are cell-independent)."""
    u, r = rs.uniform(size=4), R.RANGES
    lerp = lambda k, x: r[k][0] + x * (r[k][1] - r[k][0])
    return {"substrate_uptake_model": sub, "wall_uptake_model": wall, "rxn_log10_k0_m_s": lerp("rxn_log10_k0_m_s", u[0]),
            "rxn_Ea_eV": lerp("rxn_Ea_eV", u[1]), "rxn_n_S": lerp("rxn_n_S", u[2]), "wall_sticking": 10 ** lerp("wall_log10_sticking", u[3])}


def ens_call(pu, pd, pt, pnm):
    if pnm >= 0.9: return "non_monotonic"
    if pu >= THR: return "increase"
    if pd >= THR: return "decrease"
    if pt >= THR: return "no_change"
    return "unresolved"


def ens_item(sid, rule, extra=None, sig=SIG):
    """Structural ensemble for a sweep item: cells x existing parameter MC x i in {1,2,3} x E_eff corners (where Track L uses them)."""
    st, par, lo, hi, base, obs, label, cls = A.ITEMS[sid]
    ov, tied = L.spec(sid) if rule == "L" else ({}, {})
    base = base | ov | (extra or {})
    xs = np.linspace(lo, hi, NPTS)
    corners = A.ECORN if (par == "T_furnace_C" or "T_furnace_C" in tied) else (0.0,)
    v0 = P.validate(wulff.DEFS, base)
    rng, rs = np.random.default_rng(0), np.random.default_rng(1)
    with R.with_structural_sigma(wulff.DEFS, sig), thermo.with_liq_sigma(extra or {}):
        draws = [v0] + [uq.sample(wulff.DEFS, v0, rng) for _ in range(NMC - 1)]
    rows, by = [], {}
    zero = {}
    for sub, wall in COMBOS:
        D, NM, zf = [], [], True
        for dv in draws:
            c = struct(sub, wall, rs)
            try:
                sts = [growth.state(P.validate(wulff.DEFS, dv | c | {par: float(x)} | {k: float(x) for k, src in tied.items() if src == par})) for x in xs]
            except (ValueError, FloatingPointError):
                continue
            zf &= all(s["F"] <= 0 for s in sts)
            for i in A.IS:
                for e in corners:
                    y = np.array([growth.observables(s, i, e)[obs] for s in sts])
                    D.append(y[-1] - y[0]); NM.append(A._reversal(y))
        D, NM = np.array(D), np.array(NM)
        rows.append((D, NM)); zero[f"{sub}/{wall}"] = bool(zf)
        by[f"{sub}/{wall}"] = {"P_up": float(np.mean(D > TOL)), "P_down": float(np.mean(D < -TOL)), "P_tie": float(np.mean(abs(D) <= TOL)), "P_nonmono": float(np.mean(NM)),
                               "n": len(D), "call": ens_call(np.mean(D > TOL), np.mean(D < -TOL), np.mean(abs(D) <= TOL), np.mean(NM))}
    D, NM = np.concatenate([r[0] for r in rows]), np.concatenate([r[1] for r in rows])
    pu, pd, pt, pnm = float(np.mean(D > TOL)), float(np.mean(D < -TOL)), float(np.mean(abs(D) <= TOL)), float(np.mean(NM))
    sub_r = {s: [ens_call(by[f"{s}/{w}"]["P_up"], by[f"{s}/{w}"]["P_down"], by[f"{s}/{w}"]["P_tie"], by[f"{s}/{w}"]["P_nonmono"]) for _, w in COMBOS if _ == s] for s in R.SUB_MODELS}
    ds = {c["call"] for c in by.values()}
    return {"id": sid, "rule": rule, "param": par, "sweep": [lo, hi], "observable": obs, "label": label, "class": cls, "n_members": int(len(D)),
            "P_up": pu, "P_down": pd, "P_tie": pt, "P_literal_high_gt_low": float(np.mean(D > 0)), "P_nonmono": pnm, "ens_call": ens_call(pu, pd, pt, pnm),
            "by_cell": by, "sign_flip_across_cells": bool({"increase", "decrease"} <= ds), "cells_disagree": len(ds) > 1, "zero_flux_cells": zero}


def shape_item_ens(sid, rule):
    """s11: members = cells x N_SHAPE structural samples; each member compares the predicted shape class at the sweep ends (bench.shape_score.predict)."""
    from bench import shape_score as S
    st, par, lo, hi, base, obs, label, cls = A.ITEMS[sid]
    ov = L.spec(sid)[0] if rule == "L" else {}
    d0 = A.api_defaults() | ov
    rs, res = np.random.default_rng(1), {}
    allm = []
    for sub, wall in COMBOS:
        ms = []
        for _ in range(N_SHAPE):
            c = struct(sub, wall, rs)
            labs, ab = [], []
            for x in (lo, hi):
                with wulff.with_sigma({}):
                    p = S.predict(d0 | c | {par: float(x)})
                labs.append(p["label"]); ab.append(p["abstain"] is not None)
            ms.append("unknown" if any(ab) else ("class_change" if labs[0] != labs[1] else "no_change"))
        allm += ms
        res[f"{sub}/{wall}"] = {k: ms.count(k) / len(ms) for k in ("class_change", "no_change", "unknown")}
    f = {k: allm.count(k) / len(allm) for k in ("class_change", "no_change", "unknown")}
    call = "class_change" if f["class_change"] >= THR else "no_change" if f["no_change"] >= THR else "unresolved"
    return {"id": sid, "rule": rule, "param": par, "sweep": [lo, hi], "observable": "shape", "label": label, "class": cls, "n_members": len(allm), "fractions": f,
            "ens_call": call, "by_cell": res, "sign_flip_across_cells": False, "cells_disagree": len({max(v, key=v.get) for v in res.values()}) > 1, "zero_flux_cells": {}}


def single(rule):
    """Existing single-model rule (Track A/L method, default psat) for the same input rule: rule A = Track L 'before', rule L = Track L 'after'."""
    rows = L.run({}, rule == "L")
    return rows


def with_calls(single_rows, ens):
    out = {}
    for sid, r in single_rows.items():
        e = ens[sid]
        out[sid] = r | {"single_call": r["call"], "ens_call": e["ens_call"], "call": "uncertain" if e["ens_call"] == "unresolved" else e["ens_call"]}
    return out


def score_all():
    res = {}
    for rule in ("A", "L"):
        s = single(rule)
        ens = {sid: (shape_item_ens(sid, rule) if A.ITEMS[sid][5] == "shape" else ens_item(sid, rule)) for sid in A.ITEMS}
        rows_e = with_calls(s, ens)
        res[rule] = {"single": s, "ensemble": ens, "tables_single": I.tables(s), "tables_ensemble": I.tables(rows_e)}
        print("rule", rule)
        for sid in A.ITEMS:
            e = ens[sid]
            print(sid, "label", e["label"], "single", s[sid]["call"], "ens", e["ens_call"], {k: round(e[k], 3) for k in ("P_up", "P_down", "P_tie") if k in e}, "flip" if e["sign_flip_across_cells"] else "", "blind", s[sid]["blind"])
        for t in ("T1_dev_primary_s", "T2_original8", "T4_j1_j3", "T5_all_primary_incl_j"):
            print(t, "single", json.dumps(res[rule]["tables_single"][t]["call"]), "ens", json.dumps(res[rule]["tables_ensemble"][t]["call"]))
    return res


# ---------------------------------------------------------------- M3
def _flux(v, x):
    return growth.state(P.validate(wulff.DEFS, v | {"x_substrate_cm": float(x)}))["F"]


def flux_vs_distance(n_mc=100):
    """Substrate Mo flux (mol MoO3 units/m2/s) vs source-to-substrate distance at default conditions, per substrate model x wall variant.
    p05/p50/p95 from the existing parameter MC (default sigmas) plus the scoped sigmas of the reactive constants (k0 1 dex, Ea 0.5 eV, n 0.5) in reactive cells."""
    out = {"distance_cm": DIST, "units": "mol MoO3 units / m2 / s", "defaults": {"k0_log10": 1.0, "Ea_eV": 0.5, "n_S": 1.0}, "curves": {}}
    for sub in R.SUB_MODELS:
        for wname, wex in WALLV:
            wall = wname.split("_")[0]
            cfg = {"substrate_uptake_model": sub, "wall_uptake_model": wall} | wex
            v0 = P.validate(wulff.DEFS, cfg)
            rng = np.random.default_rng(0)
            react = sub == "reactive" or wall == "reactive"
            with R.with_structural_sigma(wulff.DEFS, {k: s for k, s in R.SCOPED_SIGMA.items() if k != "T_substrate_offset_K"} if react else {}):
                draws = [v0] + [uq.sample(wulff.DEFS, v0, rng) for _ in range(n_mc - 1)]
            Y = np.array([[_flux(dv, x) for x in DIST] for dv in draws])
            out["curves"][f"{sub}/{wname}"] = {"nominal": Y[0].tolist(), "p05": np.percentile(Y, 5, axis=0).tolist(), "p50": np.percentile(Y, 50, axis=0).tolist(),
                                              "p95": np.percentile(Y, 95, axis=0).tolist(), "frac_zero": float(np.mean(Y == 0))}
    # responses at nominal: ln-change of the flux over a boat-temperature, flow and (default) sweep, per cell and distance
    resp = {}
    liq = {"MoO3.psat_model": "smolik_liquid_cc"}
    for sub in R.SUB_MODELS:
        for wname, wex in WALLV:
            wall = wname.split("_")[0]
            cfg = {"substrate_uptake_model": sub, "wall_uptake_model": wall} | wex
            r = {}
            for x in (1.0, 4.0, 12.0):
                f = lambda extra: _flux(cfg | extra, x)
                lnr = lambda a, b: float(np.log(max(b, 1e-300)) - np.log(max(a, 1e-300)))
                r[str(x)] = {"dlnF_Tboat_800_850_liquidlaw": lnr(f(liq | {"T_boat_Mo_C": 800.0}), f(liq | {"T_boat_Mo_C": 850.0})),
                             "dlnF_Tboat_700_750_defaultlaw": lnr(f({"T_boat_Mo_C": 700.0}), f({"T_boat_Mo_C": 750.0})),
                             "dlnF_flow_50_200": lnr(f({"flow_sccm": 50.0}), f({"flow_sccm": 200.0})),
                             "F_zero_when_Tsub_equals_Tboat": f({"T_boat_Mo_C": 750.0, "T_furnace_C": 750.0, "x_substrate_cm": 0.0}) <= 0}
            resp[f"{sub}/{wname}"] = r
    out["responses_nominal_by_distance_cm"] = resp
    return out


def posthoc():
    """NOT pre-registered; run after seeing the scored results because every variant gave P_tie = 1 for j1-j3 under rule A (the default smolik_hsc law is clamped above
    1068 K, i.e. boat T > 795 C, Track K). Items with a boat/furnace temperature sweep re-run with (a) the smolik_liquid_cc law, (b) a fixed -50 K substrate offset (j only)."""
    out = {}
    liq = {"MoO3.psat_model": "smolik_liquid_cc"}
    for sid in ("s09", "j1", "j2", "j3"):
        for rule in ("A", "L"):
            for tag, extra in (("liquid_law", liq), ("liquid_law_Tsub_minus50K", liq | {"T_substrate_offset_K": -50.0})):
                if tag.endswith("50K") and not sid.startswith("j"): continue
                e = ens_item(sid, rule, extra, {} if "50K" in tag else SIG)
                out[f"{sid}/{rule}/{tag}"] = {k: e[k] for k in ("label", "P_up", "P_down", "P_tie", "ens_call", "sign_flip_across_cells")} | {"by_cell_calls": {c: v["call"] for c, v in e["by_cell"].items()}}
                print(sid, rule, tag, out[f"{sid}/{rule}/{tag}"]["ens_call"], {k: round(e[k], 3) for k in ("P_up", "P_down", "P_tie")}, out[f"{sid}/{rule}/{tag}"]["by_cell_calls"])
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--flux", action="store_true"); ap.add_argument("--score", action="store_true"); ap.add_argument("--write", action="store_true"); ap.add_argument("--posthoc", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.flux:
        o = flux_vs_distance()
        for k, c in o["curves"].items(): print(k, [f"{x:.2e}" for x in c["nominal"]])
        if a.write: json.dump(o, open(f"{OUT}/flux_vs_distance.json", "w"), indent=1)
    if a.posthoc:
        o = posthoc()
        if a.write: json.dump(o, open(f"{OUT}/posthoc.json", "w"), indent=1, default=float)
    if a.score:
        res = score_all()
        if a.write: json.dump(res, open(f"{OUT}/results.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
