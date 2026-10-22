"""'Furnace and flow' dashboard tab (Track O): a picture of the MoS2 tube furnace on the Track N furnace physics (vessels.cvd_tube.furnace.profile).

Entry point: render(st, vessel, r, tier). Only the tube vessel is supported; other vessels get a one-line message.
Layout: to-scale schematic, then temperatures, velocity and Reynolds number, and regime strips, all on one x axis (cm from the tube centre), each with a
one-line takeaway computed from the data. A small form (single Update button) edits the furnace; badges and a closed Details expander say what is not validated.
Figure code is in app/viz/furnace.py. The tab never runs a solver other than the reduced-order furnace model (about 1 s).
"""
import json, pathlib
import numpy as np
import streamlit as st_mod
from app.viz import furnace as fz

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "bench" / "track_n" / "results.json"
CFG = {"displayModeBar": False}
N_MC = 12  # ponytail: few Monte Carlo draws keep an update near 1 s; the p05-p95 bands are rougher than the 30-draw default


def credibility():
    """Badge numbers read from bench/track_n/results.json (written by the Track N scoring run); None if the file is missing."""
    try:
        d = json.loads(RESULTS.read_text())
        s = d["cfd"]["summary"]["energy_2d_auto"]
        return {"n_pass": s["n_pass_case"], "n": s["n"], "momeni_K": d["momeni"]["energy_2d_coupling_on:T_gas_mean_K"]["peak_minus_S7_K"]}
    except Exception:
        return None


def badges(st):
    c = credibility()
    out = [":blue-badge[model (Tier 1)]", ":orange-badge[not validated against measured temperatures]"]
    if c:
        out += [f":orange-badge[CFD agreement: {c['n_pass']} of {c['n']} stored cases (same-physics CFD, not independent)]",
                f":red-badge[did not reproduce Momeni 2018 simulation ({c['momeni_K']:+.0f} K)]"]
    else:
        out.append(":gray-badge[Track N scores not found (bench/track_n/results.json)]")
    st.markdown(" ".join(out))


@st_mod.cache_data(show_spinner=False)
def _compute(key, tab, want_legacy):
    from vessels.cvd_tube import furnace, profile as legacy_profile
    v = dict(key)
    if tab:
        v[furnace.TABLE_KEY] = tab
    prof = furnace.profile(v, n=200, n_mc=N_MC)
    leg = None
    if want_legacy:
        lv = {k: x for k, x in v.items() if k != furnace.TABLE_KEY}
        lv["thermal_model"] = "legacy"
        leg = legacy_profile(lv)
    return prof, leg


def _as_legacy(p, leg, v):
    """Temperatures of the legacy model on the furnace x grid; u, Re and regime flags still come from the furnace calculation (legacy has none)."""
    q = dict(p)
    x = np.asarray(p["x_cm"], float)
    Tw = np.interp(x, leg["x_cm"], leg["T_C"]) + fz.K0
    Tg = np.interp(x, leg["x_cm"], leg["T_gas_C"]) + fz.K0
    q.update(T_wall_K=Tw.tolist(), T_quartz_K=Tw.tolist(), T_gas_centre_K=Tg.tolist(), T_gas_mean_K=Tg.tolist(), T_boat_K=[], T_substrate_K=[], p05={}, p95={})
    st = {k: dict(s) for k, s in p["stations"].items()}
    st["boat_MoO3"]["T_body_K"] = v["T_boat_Mo_C"] + fz.K0
    st["substrate"]["T_body_K"] = float(np.interp(st["substrate"]["x_cm"], x, Tw)) + v["T_substrate_offset_K"]
    q["stations"] = st
    return q


def _form(st, v, L, sch):
    """The edit form. Returns the dict of values to override and the pasted text."""
    def bounds(n):
        d = next(d for d in sch if d["name"] == n)
        return float(d["lo"]), float(d["hi"])

    def num(col, label, key, val, name=None, lo=None, hi=None, step=1.0, fmt="%.0f"):
        if name:
            lo, hi = bounds(name)
        return col.number_input(label, lo, hi, float(min(max(val, lo), hi)), step, format=fmt, key=key)
    with st.form("fv_form", border=False):
        a = st.columns(4)
        nz = a[0].selectbox("Heating zones", [1, 2, 3], index=int(v["furnace_zones"]) - 1, key="fv_zones")
        t1 = num(a[1], "Zone 1 setpoint [C]", "fv_T1", v["T_furnace_C"], "T_furnace_C", step=10.0)
        t2 = num(a[2], "Zone 2 setpoint [C]", "fv_T2", v["T_zone2_C"], "T_zone2_C", step=10.0)
        t3 = num(a[3], "Zone 3 setpoint [C]", "fv_T3", v["T_zone3_C"], "T_zone3_C", step=10.0)
        b = st.columns(4)
        lh = num(b[0], "Heated length [cm]", "fv_Lhot", v["L_hot_cm"], "L_hot_cm", step=1.0)
        rp = num(b[1], "Ramp length [cm]", "fv_ramp", v["ramp_cm"], "ramp_cm", step=1.0)
        dx = num(b[2], "Boat from centre [cm]", "fv_dx", v["dx_MoO3_from_centre_cm"] if v["positions_from_centre"] == "on" else v["x_MoO3_cm"] - L / 2,
                 lo=-L / 2, hi=L / 2, step=1.0)
        xs = num(b[3], "Substrate past boat [cm]", "fv_xsub", v["x_substrate_cm"], "x_substrate_cm", step=1.0)
        c = st.columns(4)
        fl = num(c[0], "Carrier flow [sccm]", "fv_flow", v["flow_sccm"], "flow_sccm", step=10.0)
        idm = num(c[1], "Tube inner diameter [mm]", "fv_id", v["tube_id_in"] * 25.4, lo=bounds("tube_id_in")[0] * 25.4, hi=bounds("tube_id_in")[1] * 25.4, step=1.0, fmt="%.1f")
        tm = c[2].radio("Thermal model", ["furnace", "legacy"], index=["furnace", "legacy"].index(v["thermal_model"]), horizontal=True, key="fv_model")
        ov = c[3].checkbox("Compare legacy and furnace", key="fv_overlay")
        with st.expander("Paste a measured wall profile (optional)"):
            txt = st.text_area("One 'x_cm, T_C' per line, x from the tube centre (negative = inlet side); replaces the zone setpoints", key="fv_table", height=100,
                               placeholder="-20, 25\n-10, 600\n0, 750\n10, 600\n20, 25")
        go_ = st.form_submit_button("Update", type="primary")
    over = {"furnace_zones": int(nz), "T_furnace_C": t1, "T_zone2_C": t2, "T_zone3_C": t3, "L_hot_cm": lh, "ramp_cm": rp, "positions_from_centre": "on",
            "dx_MoO3_from_centre_cm": dx, "dx_S_from_centre_cm": v["dx_S_from_centre_cm"] if v["positions_from_centre"] == "on" else v["x_S_boat_cm"] - L / 2,
            "x_substrate_cm": xs, "flow_sccm": fl, "tube_id_in": idm / 25.4, "thermal_model": tm}
    return over, txt, ov


def render(st, vessel, r, tier):
    if vessel != "cvd_tube":
        st.info("Furnace and flow is only for the tube furnace.")
        return
    from core import api
    sch = api.schema("cvd_tube")
    v0 = dict(r["values"])
    L = float(v0["L_tube_cm"])
    over, txt, ov = _form(st, v0, L, sch)
    v = {**v0, **over}
    v["x_MoO3_cm"] = float(min(max(L / 2 + v["dx_MoO3_from_centre_cm"], 0), L))
    v["x_S_boat_cm"] = float(min(max(L / 2 + v["dx_S_from_centre_cm"], 0), L))
    tab, errs = fz.parse_profile_text(txt, L)
    if errs:
        st.error("Pasted profile not used. " + " | ".join(errs[:4]) + (" ..." if len(errs) > 4 else ""))
    key = tuple(sorted((k, x) for k, x in v.items() if not isinstance(x, (list, dict))))
    legacy = v["thermal_model"] == "legacy"
    try:
        prof, leg = _compute(key, tab, legacy or ov)
    except Exception as e:  # out-of-range input or a solver failure: say so, do not crash the dashboard
        st.error(f"Furnace model could not run for these inputs: {e}")
        return
    p = _as_legacy(prof, leg, v) if legacy else prof
    badges(st)
    if legacy and (tab or v["furnace_zones"] > 1):
        st.warning("Legacy model uses one flat zone and ignores zones and pasted profiles; switch to furnace to use them.")
    tmin, tmax = fz.temp_range_C(p)
    tk = fz.takeaways(p, L)
    show = lambda f: st.plotly_chart(f, width="stretch", config=CFG)
    show(fz.schematic(p, v, L, tmin, tmax))
    st.caption("Axial length to scale; diameter and quartz wall exaggerated equally. Colour = furnace wall temperature; boats and substrate = their computed temperature; star = growth.")
    show(fz.temperatures(p, v, L, tmin, tmax))
    st.caption(tk["temperature"])
    show(fz.velocity(p, v, L))
    st.caption(tk["flow"])
    show(fz.regime(p, v, L))
    st.caption("Blue = forced flow, convection. Orange = buoyancy or axial diffusion matters. " + tk["regime"])
    if ov and leg:
        st.markdown("**Legacy vs furnace thermal model, same inputs**")
        show(fz.overlay(prof, leg, v, L))
        st.caption(fz.overlay_takeaway(prof, leg, L))
    with st.expander("Details", expanded=False):
        st.markdown("**Assumptions and sources (from the model)**")
        st.markdown("\n".join(f"- {n}" for n in prof["notes"]))
        syn = sorted(k for k, c in prof["constants"].items() if str(c["source"]).startswith("synthetic"))
        src = sorted(k for k in prof["constants"] if k not in syn)
        st.markdown("**Synthetic constants (no source opened):** " + ", ".join(syn))
        st.markdown("**Constants with a source:** " + "; ".join(f"{k} = {prof['constants'][k]['value']:g} {prof['constants'][k]['unit']}" for k in src))
        st.caption("Results: docs/track_n_results.md and bench/track_n/results.json. The CFD cases impose the wall temperature, have no gravity and no radiation, so they cannot test buoyancy, quartz, boat or substrate temperatures.")
