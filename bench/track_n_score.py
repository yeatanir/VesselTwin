"""Track N scoring, exactly as pre-registered in docs/prereg/track-n.md.
  python -m bench.track_n_score --score --write     -> bench/track_n/results.json (run ONCE after the pre-registration commit)
  python -m bench.track_n_score --cfd | --momeni | --sens | --diag   (one part, printed)
Reads the stored CFD columns (bench/track_n/cfd_extract.json, made by bench/track_n/extract_cfd.py from stored cases; no solver is run) and the digitised Momeni
figures. Nothing here is tuned; all model constants are ParamDef defaults except the stored case values."""
import argparse, json, math, os
import numpy as np
from core import params as Pm, props
from vessels import cvd_tube as tube
from vessels.cvd_tube import furnace as F, wulff

HERE = os.path.dirname(os.path.abspath(__file__)) + "/track_n"
T_M, T_C, T_U = 25.0, 25.0, 0.15  # pass thresholds: K (bulk), K (centreline), relative (velocity)
R, P_STD, T_STD = props.R, 101325.0, 273.15


# ----------------------------------------------------------------------------------------------------------------- legacy gas on an arbitrary wall (copy of the march formulas)
def legacy_gas(p, x_edges, Tw_fun):
    """Legacy bulk gas temperature (cell exit) on the grid of cell edges x_edges [m], wall Tw_fun(x) [K]: same equations as tube.march (Graetz lag, Nu = p['Nu'],
    k at the cell-mid wall temperature, exact for a wall linear across the cell). Returns (x_exit, T_exit)."""
    car = p["carrier"]
    Nc = P_STD * p["flow_sccm"] * 1e-6 / 60 / (R * T_STD)
    xin, xo = x_edges[:-1], x_edges[1:]
    dx = xo - xin
    Tin, Tout, Tmid = Tw_fun(xin), Tw_fun(xo), Tw_fun(0.5 * (xin + xo))
    ntu = p["Nu"] * np.pi * tube._kcarrier(car, Tmid) * dx / (Nc * props.GAS[car][3] * R)
    sL = (Tout - Tin) / dx * dx / ntu
    out, prev = np.empty(len(xin)), float(Tin[0])
    for i in range(len(xin)):
        prev = out[i] = Tout[i] - sL[i] + (prev - Tin[i] + sL[i]) * math.exp(-ntu[i])
    return xo, out


def rich(dT, Tf, d, u):
    return 9.81 * np.abs(dT) * d / (Tf * u**2)  # Gr/Re^2 (Ri) = g beta dT d / u^2


# ----------------------------------------------------------------------------------------------------------------- test (a)
def cfd_case(rec):
    p = Pm.validate(wulff.DEFS, rec["values_full"])
    st = rec["stations"]
    L, d = p["L_tube_cm"] / 100, p["tube_id_in"] * 0.0254
    A = math.pi * d**2 / 4
    xw, Tw = np.array(rec["wall_x"]), np.array(rec["wall_T"])
    mids = 0.5 * (xw[1:] + xw[:-1])
    wall = lambda x: Tw[np.searchsorted(mids, np.asarray(x, float))]
    cx = {k: np.array(v) for k, v in rec["cols"].items()}
    stn = {"boat": st["boat_mid"], "substrate": st["substrate_centre"], "release": st["release"]}
    cfd = {s: {"T_mix": float(np.interp(x, cx["x"], cx["T_mix"])), "T_centre": float(np.interp(x, cx["x"], cx["T_centre"])),
               "u_mean": float(np.interp(x, cx["x"], cx["u_mean"])), "T_wall": float(wall(x))} for s, x in stn.items()}
    span = (cx["x"] >= st["boat_mid"]) & (cx["x"] <= st["substrate_centre"])
    Tf = 0.5 * (wall(cx["x"][span]) + cx["T_mix"][span])
    cfd["Ri_span_max"] = float(np.max(rich(wall(cx["x"][span]) - cx["T_mix"][span], Tf, d, cx["u_mean"][span]))) if span.any() else float("nan")
    for s in stn:
        cfd[s]["Ri"] = float(rich(cfd[s]["T_wall"] - cfd[s]["T_mix"], 0.5 * (cfd[s]["T_wall"] + cfd[s]["T_mix"]), d, cfd[s]["u_mean"]))
    nx = int(np.clip(L / 0.002, 300, 1000))
    models = {}
    for name, kw in (("energy_2d_auto", {"gas_model": "energy_2d", "gas_props": "auto"}), ("energy_2d_cfdconst", {"gas_model": "energy_2d", "gas_props": "cfd_const"}),
                     ("graetz_1d", {"gas_model": "graetz_1d", "gas_props": "auto"})):
        q = dict(p) | kw
        if kw["gas_model"] == "energy_2d":
            res = F.energy_2d(q, wall, L, nx, 28)
            x, Tm, Tc, u = res["x"], res["Tm"], res["Tc"], res["u_mean"]
        else:
            x = np.linspace(0, L, nx)
            Tm, _, _ = F.graetz_1d(q, x, wall(x))
            Tc = Tm
            kf, muf, cp, M = F.gas_props(q)
            u = F.mdot_kg_s(q) / (p["pressure_Pa"] * M / (R * Tm) * A)
        Tq = wall(x)
        nums = F.numbers(q, Tq, Tm, u)
        sp = (x >= st["boat_mid"]) & (x <= st["substrate_centre"])
        m = {s: {"T_mix": float(np.interp(xx, x, Tm)), "T_centre": float(np.interp(xx, x, Tc)), "u_mean": float(np.interp(xx, x, u)),
                 "Ri": float(np.interp(xx, x, nums["Ri"]))} for s, xx in stn.items()}
        m["Ri_span_max"] = float(np.max(nums["Ri"][sp])) if sp.any() else float("nan")
        models[name] = m
    mm = tube.march(p)
    Nc = P_STD * p["flow_sccm"] * 1e-6 / 60 / (R * T_STD)
    leg = {}
    for s, xx in stn.items():
        Tg = float(np.interp(xx, mm[0], mm[2]["Tg"]))
        leg[s] = {"T_mix": Tg, "T_centre": Tg, "u_mean": Nc * R * Tg / (p["pressure_Pa"] * A)}
    leg["Ri_span_max"] = float(mm[3]["buoy"]["Ri"])
    models["legacy"] = leg
    return cfd, models


def cfd_eval(store):
    rows, skipped = [], []
    for name, rec in store.items():
        if "error" in rec or rec["settled"]["max_abs_dT_last20pct_K"] >= 2.0:
            skipped.append(name)
            continue
        st = rec["stations"]
        L = rec["values"]["L_tube_cm"] / 100
        if not (0 < st["boat_mid"] < L and 0 < st["substrate_centre"] < L):
            skipped.append(name)
            continue
        cfd, models = cfd_case(rec)
        row = {"case": name, "cfd": cfd, "models": {}}
        for mn, m in models.items():
            e = {}
            for s in ("boat", "substrate", "release"):
                e[s] = {"M1_K": m[s]["T_mix"] - cfd[s]["T_mix"], "M2_K": m[s]["T_centre"] - cfd[s]["T_centre"], "M3_rel": m[s]["u_mean"] / cfd[s]["u_mean"] - 1.0}
            e["Ri_span_max"] = m["Ri_span_max"]
            e["Ri_ratio"] = m["Ri_span_max"] / cfd["Ri_span_max"] if cfd["Ri_span_max"] > 0 else float("nan")
            e["Ri_flag_agree_span"] = bool((m["Ri_span_max"] > 1.0) == (cfd["Ri_span_max"] > 1.0))
            e["Ri_flag_agree_stations"] = bool(all((m[s]["Ri"] > 1.0) == (cfd[s]["Ri"] > 1.0) for s in ("boat", "substrate")) if mn != "legacy" else True)
            e["pass_M1"] = all(abs(e[s]["M1_K"]) <= T_M for s in ("boat", "substrate"))
            e["pass_M2"] = all(abs(e[s]["M2_K"]) <= T_C for s in ("boat", "substrate"))
            e["pass_M3"] = all(abs(e[s]["M3_rel"]) <= T_U for s in ("boat", "substrate"))
            e["pass_M4"] = bool(e["Ri_flag_agree_span"] and (0.5 <= e["Ri_ratio"] <= 2.0 if np.isfinite(e["Ri_ratio"]) else True))
            e["pass_case"] = bool(e["pass_M1"] and e["pass_M2"] and e["pass_M3"])
            row["models"][mn] = e
        rows.append(row)
    summ = {}
    for mn in rows[0]["models"]:
        g = lambda f: np.array([f(r["models"][mn]) for r in rows])
        summ[mn] = {k: {"median_abs": float(np.median(np.abs(g(lambda e: e["substrate"][k])))), "median_abs_boat": float(np.median(np.abs(g(lambda e: e["boat"][k])))),
                        "max_abs": float(max(np.max(np.abs(g(lambda e: e["substrate"][k]))), np.max(np.abs(g(lambda e: e["boat"][k])))))} for k in ("M1_K", "M2_K", "M3_rel")}
        summ[mn] |= {"n_pass_M1": int(g(lambda e: e["pass_M1"]).sum()), "n_pass_M2": int(g(lambda e: e["pass_M2"]).sum()), "n_pass_M3": int(g(lambda e: e["pass_M3"]).sum()),
                     "n_pass_M4": int(g(lambda e: e["pass_M4"]).sum()), "n_pass_case": int(g(lambda e: e["pass_case"]).sum()), "n": len(rows)}
    better = {}
    for mn in rows[0]["models"]:
        if mn == "legacy":
            continue
        better[mn] = {k: [r["case"] for r in rows if max(abs(r["models"]["legacy"][s][k]) for s in ("boat", "substrate")) < max(abs(r["models"][mn][s][k]) for s in ("boat", "substrate"))]
                      for k in ("M1_K", "M2_K", "M3_rel")}
    return {"rows": rows, "summary": summ, "skipped": skipped, "legacy_better_cases": better}


# ----------------------------------------------------------------------------------------------------------------- test (b)
def _cross(x, T, thr, rising):
    i = np.where((T[:-1] < thr) & (T[1:] >= thr))[0] if rising else np.where((T[:-1] >= thr) & (T[1:] < thr))[0]
    i = i[0] if rising else i[-1]
    return float(x[i] + (thr - T[i]) / (T[i + 1] - T[i]) * (x[i + 1] - x[i]))


def momeni():
    d = json.load(open(f"{HERE}/momeni_digitized.json"))
    s2 = np.array(d["S2"]["points_x_in_T_C"], float)
    x2, T2 = s2[:, 0] * 2.54, s2[:, 1]
    x7, T7 = np.array(d["S7"]["x_cm"], float), np.array(d["S7"]["T_K"], float)
    h2, h7 = 0.5 * (T2.max() + T2.min()), 0.5 * (T7.max() + T7.min())
    mid2, mid7 = _cross(x2, T2, h2, False), _cross(x7, T7, h7, False)  # falling edges (the S2 profile starts at 550 C: its rising edge is cut off)
    shift = mid7 - mid2
    tab = [[x2[0] + shift - 15.0, 25.0]] + [[a + shift, b] for a, b in zip(x2, T2)] + [[x2[-1] + shift + 15.0, 25.0]]  # outside the digitised range the wall ramps to 25 C over 15 cm
    vals = {"tube_id_in": 40.0 / 25.4, "flow_sccm": 100.0, "pressure_Pa": 710 * 133.322, "L_tube_cm": 120.0, "T_ends_C": 25.0, "wall_profile_table": tab,
            "S_heat_belt": "off"}  # the digitised profile is the whole wall: no extra sulfur belt
    out = {"alignment_shift_cm": shift, "mid_S2_cm": mid2, "mid_S7_cm": mid7, "table_cm_C": tab}
    reg = x7[T7 > 800.0]
    for label, kw in (("energy_2d_coupling_off", {"gas_model": "energy_2d", "quartz_coupling": "off"}), ("energy_2d_coupling_on", {"gas_model": "energy_2d", "quartz_coupling": "on"}),
                      ("graetz_1d_coupling_off", {"gas_model": "graetz_1d", "quartz_coupling": "off"})):
        pr = F.profile(vals | kw, n=121, n_mc=0)
        x = np.array(pr["x_cm"])
        for key in ("T_gas_mean_K", "T_gas_centre_K"):
            T = np.interp(x7, x, pr[key])
            out[f"{label}:{key}"] = {"peak_K": float(T.max()), "peak_minus_S7_K": float(T.max() - T7.max()), "rms_heated_region_K": float(np.sqrt(np.mean((T[T7 > 800] - T7[T7 > 800]) ** 2))),
                                    "pass_peak": bool(abs(T.max() - T7.max()) <= 50.0), "pass_rms": bool(np.sqrt(np.mean((T[T7 > 800] - T7[T7 > 800]) ** 2)) <= 50.0)}
        out[f"{label}:wall_peak_K"] = float(np.max(pr["T_wall_K"]))
        out[f"{label}:T_quartz_peak_K"] = float(np.max(pr["T_quartz_K"]))
        out[f"{label}:Re_at_peak"] = float(pr["Re"][int(np.argmax(pr["T_gas_mean_K"]))])
    # legacy Graetz lag on the same wall
    p = Pm.validate(wulff.DEFS, {k: v for k, v in vals.items() if k not in ("wall_profile_table", "S_heat_belt")})
    xt, Tt = F.parse_table(tab)
    xe = np.linspace(0, 1.2, 601)
    xo, Tl = legacy_gas(p, xe, lambda x: np.interp(x, xt, Tt))
    T = np.interp(x7, xo * 100, Tl)
    out["legacy_graetz"] = {"peak_K": float(T.max()), "peak_minus_S7_K": float(T.max() - T7.max()), "rms_heated_region_K": float(np.sqrt(np.mean((T[T7 > 800] - T7[T7 > 800]) ** 2))),
                            "pass_peak": bool(abs(T.max() - T7.max()) <= 50.0), "pass_rms": bool(np.sqrt(np.mean((T[T7 > 800] - T7[T7 > 800]) ** 2)) <= 50.0)}
    out["S7_peak_K"], out["S2_wall_peak_K"] = float(T7.max()), float(T2.max() + 273.15)
    out["wall_table_minus_S7_peak_K"] = out["S2_wall_peak_K"] - out["S7_peak_K"]
    return out


# ----------------------------------------------------------------------------------------------------------------- not scored
def sens():
    base = {}
    out = {}
    def run(**kw):
        pr = F.profile(base | kw, n=121, n_mc=0)
        b, s = pr["stations"]["boat_MoO3"], pr["stations"]["substrate"]
        return {"T_boat_minus_quartz_K": b["T_body_K"] - b["T_quartz_K"], "T_sub_minus_quartz_K": s["T_body_K"] - s["T_quartz_K"], "tau_boat_s": b["tau_body_s"], "boat_lag_K": b["body_lag_K"],
                "tau_sub_s": s["tau_body_s"], "sub_lag_K": s["body_lag_K"], "T_quartz_minus_wall_max_K": pr["scalars"]["T_quartz_minus_wall_max_K"]}
    out["default"] = run()
    for k, vs in (("quartz_emis_LW", [0.5, 0.7, 0.85, 0.95]), ("quartz_cutoff_um", [3.0, 4.0, 5.0]), ("boat_nir_abs", [0.05, 0.5, 0.95]), ("quartz_nir_transmit", [0.8, 0.9, 1.0]),
                  ("boat_emis", [0.3, 0.7, 0.95]), ("body_Nu", [1.0, 2.0, 5.0])):
        out[k] = {str(v): run(**{k: v}) for v in vs}
    return out


def diag():
    cases = {"default": {}, "flow50": {"flow_sccm": 50.0}, "flow200": {"flow_sccm": 200.0}, "furn700": {"T_furnace_C": 700.0}, "furn850": {"T_furnace_C": 850.0},
             "sub6": {"x_substrate_cm": 6.0}, "sub20": {"x_substrate_cm": 20.0}, "boat650": {"T_boat_Mo_C": 650.0}, "boat750": {"T_boat_Mo_C": 750.0}}
    keys = ["MoO3_supply_mol_s", "flux_MoO3_mol_m2_s", "supersaturation_MoO3", "supersaturation_MoO3_gasT", "T_K", "T_gas_K", "species.MoO3_g.p_Pa", "MoO3_to_substrate_frac", "Ri_buoyancy"]
    out = {}
    for n, c in cases.items():
        row = {}
        for label, extra in (("legacy", {}), ("furnace_boat_computed", {"thermal_model": "furnace"}), ("furnace_boat_input", {"thermal_model": "furnace", "boat_temperature": "input"})):
            s = tube.solve(Pm.validate(wulff.DEFS, c | extra))
            row[label] = {k: s[k] for k in keys}
        row["ratio_furnace_computed_over_legacy"] = {k: (row["furnace_boat_computed"][k] / row["legacy"][k] if row["legacy"][k] else float("nan")) for k in keys}
        row["ratio_furnace_input_over_legacy"] = {k: (row["furnace_boat_input"][k] / row["legacy"][k] if row["legacy"][k] else float("nan")) for k in keys}
        out[n] = row
    return out


def posthoc():
    """POST-HOC (not pre-registered, run after seeing the diagnostic): the diagnostic's ramp definitions differ (legacy tanh scale ramp/3 has a 10-90 % distance of
    2 atanh(0.8) ramp/3 = 0.732 ramp; the furnace erf takes ramp_cm as the 10-90 % distance). Matched shape: furnace ramp_cm = 0.732 x legacy ramp_cm."""
    k = 2 * math.atanh(0.8) / 3
    cases = {"default": {}, "flow50": {"flow_sccm": 50.0}, "flow200": {"flow_sccm": 200.0}, "furn700": {"T_furnace_C": 700.0}, "furn850": {"T_furnace_C": 850.0},
             "sub6": {"x_substrate_cm": 6.0}, "sub20": {"x_substrate_cm": 20.0}}
    keys = ["MoO3_supply_mol_s", "flux_MoO3_mol_m2_s", "supersaturation_MoO3", "T_K", "T_gas_K", "MoO3_to_substrate_frac"]
    out = {"ramp_scale_factor": k}
    for n, c in cases.items():
        row = {}
        for label, extra in (("legacy", {}), ("furnace_matched_ramp_boat_input", {"thermal_model": "furnace", "boat_temperature": "input", "ramp_cm": 12.0 * k}),
                             ("furnace_matched_ramp_boat_computed", {"thermal_model": "furnace", "ramp_cm": 12.0 * k})):
            sol = tube.solve(Pm.validate(wulff.DEFS, c | extra))
            row[label] = {q: sol[q] for q in keys}
        row["ratio_input_over_legacy"] = {q: (row["furnace_matched_ramp_boat_input"][q] / row["legacy"][q] if row["legacy"][q] else float("nan")) for q in keys}
        row["ratio_computed_over_legacy"] = {q: (row["furnace_matched_ramp_boat_computed"][q] / row["legacy"][q] if row["legacy"][q] else float("nan")) for q in keys}
        out[n] = row
    return out


def clean(o):
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (np.floating, np.integer, np.bool_)): return o.item()
    return o


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for k in ("score", "write", "cfd", "momeni", "sens", "diag", "posthoc"):
        ap.add_argument("--" + k, action="store_true")
    a = ap.parse_args()
    res = {}
    if a.score or a.cfd:
        res["cfd"] = cfd_eval(json.load(open(f"{HERE}/cfd_extract.json")))
    if a.score or a.momeni:
        res["momeni"] = momeni()
    if a.score or a.sens:
        res["sensitivity"] = sens()
    if a.score or a.diag:
        res["diagnostic"] = diag()
    if a.posthoc:
        ph = clean(posthoc())
        if a.write:
            json.dump(ph, open(f"{HERE}/posthoc.json", "w"), indent=1)
            print("wrote", f"{HERE}/posthoc.json")
        else:
            print(json.dumps(ph, indent=1)[:4000])
    res = clean(res)
    if a.write and res:
        json.dump(res, open(f"{HERE}/results.json", "w"), indent=1)
        print("wrote", f"{HERE}/results.json")
    elif res:
        print(json.dumps({k: (v["summary"] if k == "cfd" else v) for k, v in res.items()}, indent=1)[:6000])
