"""Model vs published CALF-20 / 13X data (sorbent_data.json 'benchmarks'). Nothing here is tuned: every parameter is a published
value or the ParamDef default; errors are reported as they come. `python -m vessels.sorbent.benchmark` prints the table."""
import json, pathlib
import numpy as np
from core import params as P
from vessels import sorbent as sb

B = sb.DATA["benchmarks"]
PRE = pathlib.Path(__file__).resolve().parents[2] / "presets"


def _p(preset, **kw): return P.defaults(sb.DEFS) | {k: v for k, v in json.loads((PRE / f"{preset}.json").read_text()).items() if k != "_meta"} | kw


def loading(p, comp, T):
    """Equilibrium CO2 loading for gas composition dict {'CO2': y, ...} at p['P_kPa'] with the model isotherm."""
    pk, cT = sb._pk(p), p["P_kPa"] * 1e3 / (sb.R * T)
    return float(sb._eq(pk, {k: np.array([v * cT]) for k, v in comp.items()}, T)["CO2"][0])


def isotherm_errors():
    out = {}
    p = _p("sorbent__CALF20_CO2", P_kPa=97.0)
    out["CALF20 CO2/N2 (A2.1)"] = [(y, q, loading(p, {"CO2": y, "N2": 1 - y}, 273.15 + T)) for (y, q), T in zip(B["CALF20_loading_CO2N2"]["points"], B["CALF20_loading_CO2N2"]["T_each_C"])]
    out["CALF20 CO2/He (A2.1)"] = [(y, q, loading(p, {"CO2": y}, 273.15 + T)) for y, q, T in B["CALF20_loading_CO2_He"]["points"]]
    pw = _p("sorbent__CALF20_CO2", P_kPa=97.0)
    out["CALF20 H2O (3.2)"] = [(rh, q, float(sb._eq(sb._pk(pw), {"H2O": np.array([rh * sb.psat(273.15 + T) / (sb.R * (273.15 + T))])}, 273.15 + T)["H2O"][0])) for rh, q, T in B["CALF20_loading_H2O"]["points"]]
    p13 = _p("sorbent__13X_CO2", P_kPa=101.325)
    out["13X Z10-02ND CO2 (4.3)"] = [(pc, q, loading(p13, {"CO2": pc * 1e5 / (sb.R * (273.15 + T))}, 273.15 + T) if False else float(sb._eq(sb._pk(p13), {"CO2": np.array([pc * 1e5 / (sb.R * (273.15 + T))])}, 273.15 + T)["CO2"][0])) for pc, q, T in B["13X_Z1002ND_loading_CO2"]["points"]]
    out["13X Z10-02ND H2O (4.3)"] = [(rh, q, float(sb._eq(sb._pk(p13), {"H2O": np.array([rh * sb.psat(273.15 + T) / (sb.R * (273.15 + T))])}, 273.15 + T)["H2O"][0])) for rh, q, T in B["13X_Z1002ND_loading_H2O"]["points"]]
    return {k: [(x, qe, qm, (qm - qe) / qe) for x, qe, qm in v] for k, v in out.items()}


def _bt(p, tbar_target, n_cells):
    s, t, co, Y, Tpk = sb.simulate(p | {"n_cells": n_cells}, n_t=400)
    tb = t * (s["us"] / p["bed.epsilon"]) / s["L"]  # t_bar = t v / L, v interstitial feed velocity
    return sb._first(tb, co, 0.5), float(Y[:, int(0.8 * s["n"]), s["ix"]["T"]].max())  # thermocouple at z = 0.8 L (WIL17; ~1.8 cm from outlet in NGU21)


def calf20_breakthrough(n_cells=60):
    c = B["CALF20_breakthrough_CO2_He"]["column"]
    out = []
    for (y, texp), Tpk_exp in zip(B["CALF20_breakthrough_CO2_He"]["points"], B["CALF20_breakthrough_CO2_He"]["T_peak_C_fig2.6b"]):
        p = _p("sorbent__CALF20_CO2", carrier="He", y_feed=y, bed_length_cm=c["L_m"] * 100, bed_id_cm=c["D_m"] * 100, flow_sccm=50.0,
               T_K=273.15 + c["T_C"], P_kPa=c["P_bar"] * 100, wall_model="lumped", h_in=c["h_in"], h_wall=c["h_out"], Kz=c["Kz"],
               cp_solid=c["cp_solid"], wall_mm=(c["Do_m"] - c["D_m"]) / 2 * 1e3, particle_dp_mm=c["dp_mm"], **{"bed.rho_kg_m3": c["mass_g"] * 1e-3 / (np.pi / 4 * c["D_m"] ** 2 * c["L_m"])})
        tb, Tpk = _bt(p, texp, n_cells)
        out.append(dict(y=y, t_exp=texp, t_model=tb, err=(tb - texp) / texp, Tpeak_exp_C=Tpk_exp, Tpeak_model_C=Tpk - 273.15))
    return out


def x13_breakthrough(n_cells=60, dp_mm=None):
    c = B["13X_Z1002ND_breakthrough_CO2_He"]["column"]
    out = []
    for (y, texp), key in zip(B["13X_Z1002ND_breakthrough_CO2_He"]["points"], ("0.15", "0.5")):
        p = _p("sorbent__13X_CO2", carrier="He", y_feed=y, bed_length_cm=c["L_m"] * 100, bed_id_cm=c["D_m"] * 100, flow_sccm=c["flows_sccm"][key],
               T_K=273.15 + c["T_C"], P_kPa=c["P_bar"] * 100, wall_model="lumped", h_in=c["h_in"], h_wall=c["h_out"], Kz=c["Kz"],
               cp_solid=c["cp_solid"], wall_mm=(c["Do_m"] - c["D_m"]) / 2 * 1e3, particle_dp_mm=dp_mm or c["dp_mm_ASSUMED"],
               **{"bed.rho_kg_m3": c["mass_g"] * 1e-3 / (np.pi / 4 * c["D_m"] ** 2 * c["L_m"])})
        tb, Tpk = _bt(p, texp, n_cells)
        out.append(dict(y=y, t_exp=texp, t_model=tb, err=(tb - texp) / texp, Tpeak_exp_C=B["13X_Z1002ND_breakthrough_CO2_He"]["T_peak_C_fig4.11c_z0.8L"][key], Tpeak_model_C=Tpk - 273.15))
    return out


def competitive_13X():
    p = _p("sorbent__13X_CO2", P_kPa=102.0)
    out = []
    for r in B["13X_Z1002ND_competitive"]["points"]:
        T, cT = 273.15 + r["T_C"], 102e3 / (sb.R * (273.15 + r["T_C"]))
        yw = r["RH"] * sb.psat(T) / 102e3
        q = sb._eq(sb._pk(p), {"CO2": np.array([(1 - yw) * cT]), "H2O": np.array([yw * cT])}, T)
        out.append(dict(RH=r["RH"], qCO2_exp=r["q_CO2"], qCO2_model=float(q["CO2"][0]), qH2O_exp=r["q_H2O"], qH2O_model=float(q["H2O"][0])))
    return out


if __name__ == "__main__":
    for k, v in isotherm_errors().items():
        print(k, "mean |err| = %.1f %%" % (100 * np.mean([abs(e) for *_, e in v])), [round(e, 3) for *_, e in v])
    print("CALF-20 CO2/He breakthrough (t_bar at 50 %):", [{k: round(float(x), 2) for k, x in r.items()} for r in calf20_breakthrough()])
    print("13X Z10-02ND CO2/He breakthrough:", [{k: round(float(x), 2) for k, x in r.items()} for r in x13_breakthrough()])
    print("13X competitive CO2/H2O (EDSL):", competitive_13X())
