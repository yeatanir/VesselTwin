"""'Vessel view' dashboard tab: pictures first. Schematic drawn from the live parameters, Tier 1 profiles, stored Tier 2 (OpenFOAM) field maps.

Entry points:
  render(st, vessel, r, tier)                      the dashboard tab (r = dashboard solve result; uses r["values"], r["passport"], r["extras"]).
                                                   Tier 0: schematic only. Tier 1: + model profiles. Tier 2: + stored CFD fields.
  render_vessel_hero(result, vessel, spec, height) compact hero figure for the home page (schematic with temperature / concentration / photon-flux
                                                   field behind it, flow arrows and one bright marker). `spec` is accepted for the caller's
                                                   convenience and not needed; everything is drawn from result["values"].

CFD field maps come ONLY from data/viz_cache/*.npz, regenerated from stored OpenFOAM case directories with
    python scripts/export_fields.py --root <dir with the case dirs>      (see that script's docstring; needs the OpenFOAM v2512 volume)
The tab never runs a solver. If a vessel has no cache file it says so. Figure code lives in app/viz/; this module only lays it out.
Text is kept to a title and a one-line takeaway per panel; tables, status text and sources sit in closed 'Details' expanders.
"""
import json, pathlib
import numpy as np
import streamlit as st_mod  # cache decorators and the hero's own drawing; the tab draws through the `st` argument
from app.viz import schematics, profiles, fields, plotly_figs

ROOT = pathlib.Path(__file__).resolve().parents[1]
TIERS = json.loads((ROOT / "tiers.json").read_text()) if (ROOT / "tiers.json").exists() else {}
UNITS = {"cvd_tube": ("cm", "mm", 100.0, 1000.0), "ampoule": ("cm", "mm", 100.0, 1000.0), "flask": ("mm", "mm", 1000.0, 1000.0)}
BADGE = {"model": ("Model (Tier 1)", "blue"), "cfd": ("CFD (Tier 2)", "green"), "synth": ("Synthetic inputs", "orange"), "input": ("Your inputs", "gray")}
TAKE = {"cvd_tube": "Star = substrate, where growth happens. Colour = furnace wall temperature.",
        "ampoule": "Arrows carry vapour hot to cold; star = growth at the sink.",
        "flask": "Stir bar spins in the liquid; star = highest-shear tip.",
        "sorbent": "Colour = CO2 level in the bed; star = the moving front.",
        "photoreactor": "Light enters through the wall and fades with depth."}


def _key(values):
    return tuple(sorted((k, v) for k, v in values.items()))


def badges(st, *kinds):
    st.markdown(" ".join(f":{BADGE[k][1]}-badge[{BADGE[k][0]}]" for k in kinds))


@st_mod.cache_data(show_spinner=False)
def _sorbent(key):
    return profiles.sorbent_states(dict(key))


@st_mod.cache_data(show_spinner=False)
def _schematic(vessel, key):
    p = dict(key)
    if vessel == "cvd_tube":
        from vessels.cvd_tube import twall
        x = np.linspace(0, p["L_tube_cm"], 300)
        return schematics.tube(p, (x, twall(p, x / 100) - 273.15))
    if vessel == "ampoule":
        T2, T1 = p["T_source_C"], p["T_sink_C"]
        if p["T_profile"] == "two_zone":
            zf = p["zone_frac"]
            fn = lambda s: float(np.interp(s, [0, zf, 1 - zf, 1], [T2, T2, T1, T1]))
        else:
            fn = lambda s: T2 + (T1 - T2) * s
        return schematics.ampoule(p, fn)
    if vessel == "flask":
        from vessels import flask
        m = flask._mix(p)
        return schematics.flask(p, {"T": m["T_flask"], "depth": m["depth"], "d": m["d"]})
    if vessel == "sorbent":
        zc = None
        try:
            z, t, T, c = _sorbent(key)
            k50 = int(np.argmax(c[:, -1] >= 0.5)) if (c[:, -1] >= 0.5).any() else len(t) - 1
            zc = (z, c[max(int(0.75 * k50), 1)])
        except Exception:
            pass
        return schematics.sorbent(p, zc)
    from vessels import photoreactor
    flux = photoreactor.flux_density(p, np.linspace(0, p["path_cm"], 60))
    return schematics.photoreactor(p, float(photoreactor.wall_T(p)), None, flux)


@st_mod.cache_data(show_spinner=False)
def _tube_figs(key, extras_json):
    return profiles.tube_figs(dict(key), json.loads(extras_json))


@st_mod.cache_data(show_spinner=False)
def _field(name, field, lines, xs, ys, xu, yu, h, equal):
    d, meta = fields.load(name)
    return fields.field_fig(d, meta, field, lines, xs, ys, xu, yu, h, fields.streamlines(d) if lines else None, equal)


CFG = {"displayModeBar": "hover", "scrollZoom": True, "displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"]}  # zoom, pan, double-click resets


def render_vessel_hero(result, vessel, spec=None, height=360):
    """Compact hero figure for the home page: to-scale schematic, field behind it, flow arrows, one marker, tiny status badge."""
    st = st_mod
    try:
        import plotly.graph_objects as go
        m = _hero_case(vessel, result["values"]) if vessel in fields.HERO_FIELD else None
        if m is not None:  # stored CFD field behind the vessel, flow arrows, one marker
            fig = go.Figure(_cfd_hero(m["name"])); fig.update_layout(height=height)
            st.plotly_chart(fig, width="stretch", config=CFG)
            st.caption(":green-badge[CFD (Tier 2), stored, not re-run]" + (" :orange-badge[other inputs]" if fields.differences(m, result["values"], vessel) else ""))
            return
        fig = go.Figure(_schematic(vessel, _key(result["values"])))  # copy: the cached figure is not mutated
        fig.update_layout(height=height)
        st.plotly_chart(fig, width="stretch", config=CFG)
        syn = result.get("passport", {}).get("synthetic", True)
        st.caption(":blue-badge[Model (Tier 1)] " + (":orange-badge[Synthetic inputs]" if syn else ":green-badge[Sourced inputs]"))
    except Exception as e:
        st.caption(f"Hero figure unavailable: {e}")


@st_mod.cache_data(show_spinner=False)
def _cfd_hero(name):
    d, meta = fields.load(name)
    return fields.hero_fig(d, meta, meta["vessel"], fields.streamlines(d, 1.6), 360)


def _hero_case(vessel, v):
    metas = [m for m in fields.available(vessel) if vessel != "flask" or "vertical" in m["name"]]
    return metas[fields.nearest(metas, v, vessel)] if metas else None


def _schematic_section(st, vessel, v):
    st.subheader("Your vessel")
    try:
        st.plotly_chart(_schematic(vessel, _key(v)), width="stretch", config=CFG)
    except Exception as e:
        st.warning(f"Schematic could not be drawn for these parameters: {e}")
    st.caption(TAKE.get(vessel, ""))
    with st.expander("Details", expanded=False):
        badges(st, "input")
        st.write("Redrawn from your current parameters; lengths are to scale. Slender vessels have the width exaggerated (stated in the figure). "
                 "Boat footprints are drawn square from the boat area; the ampoule agent charge is drawn at a minimum visible size.")


def _profiles_section(st, vessel, r):
    v, ex = r["values"], r.get("extras") or {}
    st.subheader("What the model predicts")
    syn = r["passport"]["synthetic"]
    badges(st, "model", *(["synth"] if syn else []))
    det = []  # (text) lines for the Details expander
    try:
        if vessel == "cvd_tube":
            figs, n = _tube_figs(_key(v), json.dumps(ex, default=float))
            cols = st.columns(2)
            for i, f in enumerate(figs[:2]):
                cols[i].plotly_chart(f, width="stretch", config=CFG)
            if len(figs) > 2:
                with st.expander("Deposition shape vs position (hypothesis)"):
                    st.plotly_chart(figs[2], width="stretch", config=CFG)
            det.append(f"Bands: {n} Monte Carlo draws of the 1D march. Shape index rests on synthetic edge rates: trend only.")
        elif vessel == "ampoule":
            figs = profiles.ampoule_figs(v, r["passport"])
            cols = st.columns(len(figs))
            for c, f in zip(cols, figs):
                c.plotly_chart(f, width="stretch", config=CFG)
            det.append("The Tier 1 ampoule model gives end pressures and a rate, not an interior profile. Interior fields are in the CFD panels.")
        elif vessel == "sorbent":
            st.plotly_chart(plotly_figs.profiles(vessel, r, None)[0][1], width="stretch", config=CFG)  # time slider is inside the figure
            det.append("Slide to move the front down the bed. No uncertainty band is computed for the bed state.")
        elif vessel == "photoreactor" and ex.get("photon_flux_vs_depth"):
            st.plotly_chart(profiles.photon_fig(ex), width="stretch", config=CFG)
            det.append("Only the optical chain is checked against published actinometry; lamp power to irradiance and the mixing cap are not.")
        elif vessel == "flask":
            st.info("Tier 1 flask is well-mixed: no spatial profile. See the CFD panels at Tier 2.")
            rows = [{"quantity": k, "unit": d["unit"], "p05": d["p05"], "p50": d["p50"], "p95": d["p95"]} for k, d in r["passport"]["derived"].items() if d.get("p50") is not None]
            det.append(rows)
        else:
            st.info("No spatial profile from this vessel's Tier 1 model.")
    except Exception as e:
        st.warning(f"Profile could not be computed for these parameters: {e}")
    st.caption("Solid = model output, shaded = p05 to p95, dashed = your input.")
    with st.expander("Details", expanded=False):
        for d in det:
            st.dataframe(d, width="stretch", hide_index=True) if isinstance(d, list) else st.write(d)
        st.write(TIERS.get(vessel, {}).get("status", ""))


def _cfd_section(st, vessel, v):
    st.subheader("Flow and temperature inside (CFD)")
    metas = fields.available(vessel)
    if not metas:
        st.info(f"No stored CFD field result for {vessel}; nothing is drawn rather than a made-up field.")
        return
    labels = [f"{m['case']} ({m['plane'].split(',')[0]})" if vessel == "flask" else m["name"] for m in metas]
    i = st.selectbox("Stored case", range(len(metas)), index=fields.nearest(metas, v, vessel), format_func=lambda j: labels[j], key=f"vv_case_{vessel}")
    m = metas[i]
    ti = TIERS.get(vessel, {})
    badges(st, "cfd", "synth")
    st.markdown(f"`{m['case']}` · {m['n_cells']:,} cells · made {m['date_made']} · **stored CFD result, not re-run** · verification: see Details (highest tier {ti.get('tier', '?')})")
    diff = fields.differences(m, v, vessel)
    if diff:
        st.warning("Stored case used different inputs than yours; not recomputed.")
    if vessel in fields.HERO_FIELD and (hm := _hero_case(vessel, v)) is not None:
        st.plotly_chart(_cfd_hero(hm["name"]), width="stretch", config=CFG)
        st.caption("Colour = field, white arrows = flow, star = where transfer happens.")
    st.plotly_chart(plotly_figs.cfd_field(vessel, case=m["name"]), width="stretch", config=CFG)  # field dropdown inside the figure
    st.caption("Pick the field in the figure menu. Orange lines = flow. Stored result, not re-run.")
    with st.expander("Details", expanded=False):
        st.write("Plane: " + m["plane"])
        st.write("Solver: " + m["solver"] + f", time {m['time_dir']}. Colormaps: cividis (temperature), blues (others).")
        st.write({"cvd_tube": "Radial axis stretched. Species are passive scalars on a laminar buoyant flow.",
                  "ampoule": "Laminar Boussinesq flow; tilted cases are a square duct, not a round tube.",
                  "flask": "Frozen-rotor k-epsilon with wall functions on an equal-volume cylinder; mesh GCI 5-14 %."}.get(vessel, ""))
        if diff:
            st.write("Input differences: " + "; ".join(diff))
        st.write("Tier-2 verification status (tiers.json): " + ti.get("status", "none recorded"))


def render(st, vessel, r, tier):
    v = r["values"]
    try:
        _schematic_section(st, vessel, v)
        if tier >= 1:
            _profiles_section(st, vessel, r)
        else:
            st.caption("Tier 0: picture only. Pick Tier 1 for profiles, Tier 2 for CFD.")
        if tier >= 2:
            _cfd_section(st, vessel, v)
        elif tier == 1:
            st.caption("Pick Tier 2 to see the stored CFD fields.")
    except Exception as e:
        st.error(f"Vessel view failed: {e}")
