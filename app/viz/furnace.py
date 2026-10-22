"""Figures and text helpers for the 'Furnace and flow' tab (Track O). Pure functions, no Streamlit.

Everything is drawn from the dict returned by vessels.cvd_tube.furnace.profile (schema "cvd_tube.furnace.profile/1"); the x axis is the position in cm
from the TUBE CENTRE (profile x is measured from the inlet, so x_c = x - L_tube/2). Four figures share the same x range and margins so they line up:
schematic, temperatures, velocity and Reynolds number, regime strips. Temperatures are shown in C; one colourmap (cividis, colour-blind safe) and one
colour range are used for every temperature colour so a colour means the same temperature everywhere.
"""
import re
import numpy as np
import plotly.graph_objects as go
import matplotlib

CMAP = "cividis"
GREY, SKY, VERM, ORANGE, BLUE, GREEN, PINK = "#7a7a7a", "#56B4E9", "#D55E00", "#E69F00", "#0072B2", "#009E73", "#CC79A7"  # Okabe-Ito, readable on light and dark
MARGIN = dict(l=72, r=60, t=24, b=34)  # identical for all four figures so their x axes line up
K0 = 273.15


def _hex(T_C, lo, hi):
    return matplotlib.colors.to_hex(matplotlib.colormaps[CMAP](float(np.clip((T_C - lo) / (hi - lo + 1e-9), 0, 1))))


def _a(p, k):
    return np.asarray(p[k], float) if p.get(k) is not None and len(p[k]) else None


# ----------------------------------------------------------------------------------------------------------------- pasted measured profile
def parse_profile_text(text, L_tube_cm):
    """'x_cm, T_C' lines (x from the tube centre; separators comma, semicolon, tab or space; '#' starts a comment).
    Returns (table_string for furnace.TABLE_KEY or '', [error messages]). x is converted to cm from the inlet (x + L/2)."""
    pts, errs = [], []
    for i, raw in enumerate(str(text or "").splitlines(), 1):
        s = raw.split("#")[0].strip()
        if not s:
            continue
        parts = [q for q in re.split(r"[,;\t ]+", s) if q]
        try:
            if len(parts) != 2:
                raise ValueError("need exactly two numbers")
            x, T = float(parts[0]), float(parts[1])
            if not (np.isfinite(x) and np.isfinite(T)):
                raise ValueError("not finite")
            if abs(x) > L_tube_cm / 2 + 1e-9:
                raise ValueError(f"x = {x:g} cm is outside the tube (+-{L_tube_cm / 2:g} cm from the centre)")
            if not -50 <= T <= 1500:
                raise ValueError(f"T = {T:g} C outside -50..1500 C")
            pts.append((x + L_tube_cm / 2, T))
        except ValueError as e:
            errs.append(f"line {i} ('{raw.strip()[:30]}'): {e}")
    if not errs and pts:
        if len(pts) < 2:
            errs.append("need at least 2 points")
        elif len({round(x, 6) for x, _ in pts}) != len(pts):
            errs.append("two lines have the same x")
    if errs or not pts:
        return "", errs
    return ";".join(f"{x:.6g}:{T:.6g}" for x, T in sorted(pts)), []


# ----------------------------------------------------------------------------------------------------------------- takeaways (computed from the data)
def _fx(p, L):
    return np.asarray(p["x_cm"], float) - L / 2


def takeaways(p, L):
    """Three one-line sentences, each computed from the profile arrays (never hard-coded numbers)."""
    x = _fx(p, L)
    Tq, Tg = _a(p, "T_quartz_K"), _a(p, "T_gas_centre_K")
    if Tq is None:
        Tq = _a(p, "T_wall_K")
    sub = p["stations"]["substrate"]
    hot = np.nonzero(Tq >= Tq[0] + 100)[0]
    if Tg is None or not len(hot):
        a = "The wall never gets 100 K above the inlet temperature, so there is no heated section."
    else:
        i0 = hot[0]
        ok = np.nonzero(np.abs(Tg[i0:] - Tq[i0:]) <= 10)[0]
        a = (f"Gas centreline is within 10 K of the wall from x = {x[i0 + ok[0]]:+.0f} cm; the substrate sits at {sub['T_body_K'] - K0:.0f} C."
             if len(ok) else f"Gas centreline never gets within 10 K of the wall; the substrate sits at {sub['T_body_K'] - K0:.0f} C.")
    u, Re = np.asarray(p["u_mean_m_s"], float) * 100, np.asarray(p["Re"], float)
    b = (f"Gas speeds up from {u[0]:.1f} to {u.max():.1f} cm/s as it heats; Re peaks at {Re.max():.1f} ({'laminar' if Re.max() < 2300 else 'not laminar'}).")
    sc = p["scalars"]
    c = (f"Between boat and substrate buoyancy {'matters' if sc['buoyancy_matters_boat_to_substrate'] else 'is small'} (Ri up to {sc['Ri_max_boat_to_substrate']:.3g}); "
         f"gas is carried by {sc['carried_by']} (Pe {sc['Pe_transport_boat_to_substrate']:.3g}).")
    return {"temperature": a, "flow": b, "regime": c}


def temp_range_C(p):
    ks = [k for k in ("T_wall_K", "T_quartz_K", "T_gas_centre_K", "T_boat_K", "T_substrate_K") if _a(p, k) is not None]
    allv = np.concatenate([_a(p, k) for k in ks]) - K0
    return float(allv.min()), float(allv.max())


# ----------------------------------------------------------------------------------------------------------------- figures
def _layout(f, h, xr, xtitle=None, ytitle=None, legend=False):
    f.update_layout(height=h, margin=MARGIN, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=legend, hovermode="x unified" if legend else "closest",
                    legend=dict(orientation="h", traceorder="normal", y=1.02, yanchor="bottom", x=0, font=dict(size=11)))
    f.update_yaxes(automargin=False)
    f.update_xaxes(range=xr, fixedrange=True, title=xtitle, showgrid=True, gridcolor="rgba(128,128,128,0.2)", zeroline=False)
    if ytitle:
        f.update_yaxes(title=ytitle, fixedrange=True, gridcolor="rgba(128,128,128,0.2)", zeroline=False)
    return f


def schematic(p, v, L, tmin, tmax):
    """To-scale (axial) tube: bore coloured by furnace wall T, quartz wall, heated zone, boats, substrate, gas arrow, growth marker."""
    x = _fx(p, L)
    Tw = _a(p, "T_wall_K") - K0
    ID = v["tube_id_in"] * 25.4
    r, t = ID / 2, v["quartz_wall_mm"]
    Ro = r + t
    xr = [-L / 2, L / 2]
    f = go.Figure()
    f.add_trace(go.Heatmap(x=x, y=[-r, r], z=[Tw, Tw], zmin=tmin, zmax=tmax, colorscale=CMAP, zsmooth="best",
                           hovertemplate="x %{x:.1f} cm<br>furnace wall %{z:.0f} C<extra></extra>",
                           colorbar=dict(title=dict(text="temperature [C]", side="right"), thickness=8, len=0.9, x=1.0, xpad=4)))
    for s in (1, -1):  # quartz wall (true thickness on the exaggerated transverse scale)
        f.add_shape(type="rect", x0=xr[0], x1=xr[1], y0=s * r, y1=s * Ro, fillcolor="rgba(150,150,150,0.35)", line=dict(color=GREY, width=1))
    xc = v["x_furnace_center_cm"] - L / 2
    hz = Ro + 0.45 * ID
    f.add_shape(type="rect", x0=xc - v["L_hot_cm"] / 2, x1=xc + v["L_hot_cm"] / 2, y0=-hz, y1=hz, fillcolor="rgba(213,94,0,0.10)", line=dict(color=VERM, width=1.5, dash="dot"))
    nz = int(v["furnace_zones"])
    for k in range(1, nz):
        xe = xc - v["L_hot_cm"] / 2 + v["L_hot_cm"] * k / nz
        f.add_shape(type="line", x0=xe, x1=xe, y0=-hz, y1=hz, line=dict(color=VERM, width=1, dash="dot"))
    f.add_annotation(x=xc, y=-hz, text=f"heated zone, {v['L_hot_cm']:.0f} cm", showarrow=False, font=dict(size=10, color=VERM), yanchor="top")
    for key, lab, w in (("boat_MoO3", "MoO3", max(1.5, float(v["boat_area_MoO3_cm2"]) ** 0.5)), ("boat_S", "S", max(1.5, float(v["boat_area_S_cm2"]) ** 0.5)),
                        ("substrate", "sub", float(v["substrate_length_cm"]))):
        s = p["stations"][key]
        xb, Tb = s["x_cm"] - L / 2, s["T_body_K"] - K0
        hgt = 0.18 * ID if key != "substrate" else 0.07 * ID
        y0 = -r if key != "substrate" else -r + 0.20 * ID
        f.add_shape(type="rect", x0=xb - w / 2, x1=xb + w / 2, y0=y0, y1=y0 + hgt, fillcolor=_hex(Tb, tmin, tmax), line=dict(color="#111", width=1.5))
        f.add_annotation(x=xb, y=y0 + hgt, text=lab, showarrow=False, font=dict(size=10, color="#111"), bgcolor="rgba(255,255,255,0.8)", yanchor="bottom", yshift=2)
        f.add_trace(go.Scatter(x=[xb], y=[y0 + hgt / 2], mode="markers", marker=dict(size=14, opacity=0), hovertemplate=f"{lab}<br>x %{{x:.1f}} cm<br>{Tb:.0f} C<extra></extra>", showlegend=False))
    xs = p["stations"]["substrate"]["x_cm"] - L / 2
    f.add_trace(go.Scatter(x=[xs], y=[0.55 * r], mode="markers", marker=dict(symbol="star", size=16, color="#FFD400", line=dict(color="#111", width=1.2)),
                           hovertemplate="growth is computed here (substrate centre)<extra></extra>", showlegend=False))
    ya = Ro + 0.7 * ID
    f.add_annotation(x=xr[0] + 0.14 * L, y=ya, ax=xr[0] + 0.02 * L, ay=ya, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=2, arrowwidth=3, arrowcolor=GREEN, text="")
    f.add_annotation(x=xr[0] + 0.15 * L, y=ya, text=f"gas {v['carrier']} {v['flow_sccm']:.0f} sccm", showarrow=False, font=dict(size=10, color=GREEN), xanchor="left")
    _layout(f, 230, xr)
    f.update_yaxes(visible=False, range=[-hz - 0.35 * ID, Ro + 1.1 * ID], fixedrange=True)
    f.update_xaxes(showgrid=False)
    return f


def temperatures(p, v, L, tmin, tmax):
    x = _fx(p, L)
    f = go.Figure()
    spec = [("T_wall_K", "furnace wall", GREY, "dash", 2), ("T_quartz_K", "quartz inner", SKY, "solid", 2), ("T_gas_mean_K", "gas mean", ORANGE, "dot", 2.5),
            ("T_gas_centre_K", "gas centreline", VERM, "solid", 2.5), ("T_boat_K", "boat", BLUE, "solid", 1.5), ("T_substrate_K", "substrate", GREEN, "solid", 1.5)]
    for k, lab, col, dash, w in spec:
        y = _a(p, k)
        if y is None:
            continue
        lo, hi = _a({"a": p["p05"].get(k, [])}, "a"), _a({"a": p["p95"].get(k, [])}, "a")
        if lo is not None and hi is not None and k in ("T_gas_centre_K", "T_boat_K", "T_substrate_K", "T_quartz_K"):  # p05-p95 bands, only where the profile provides them
            f.add_trace(go.Scatter(x=x, y=hi - K0, mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False))
            f.add_trace(go.Scatter(x=x, y=lo - K0, mode="lines", line=dict(width=0), fill="tonexty", fillcolor=_rgba(col, 0.18),
                                   hoverinfo="skip", showlegend=False))
        f.add_trace(go.Scatter(x=x, y=y - K0, mode="lines", name=lab, line=dict(color=col, width=w, dash=dash), hovertemplate="%{y:.0f} C"))
    for key, lab, col in (("boat_MoO3", "MoO3 boat", BLUE), ("substrate", "substrate", GREEN)):
        s = p["stations"][key]
        xb = s["x_cm"] - L / 2
        f.add_vline(x=xb, line=dict(color=col, width=1.5, dash="dot"))
        f.add_trace(go.Scatter(x=[xb], y=[s["T_body_K"] - K0], mode="markers", marker=dict(size=11, color=[s["T_body_K"] - K0], colorscale=CMAP, cmin=tmin, cmax=tmax,
                                                                                         line=dict(color=col, width=2)), showlegend=False,
                               hovertemplate=f"{lab}: %{{y:.0f}} C<extra></extra>"))
    _layout(f, 300, [-L / 2, L / 2], None, "temperature [C]", True)
    return f


def _rgba(hexcol, a):
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{a})"


def velocity(p, v, L):
    x = _fx(p, L)
    f = go.Figure()
    f.add_trace(go.Scatter(x=x, y=np.asarray(p["u_mean_m_s"]) * 100, name="mean velocity", line=dict(color=BLUE, width=2.5), hovertemplate="%{y:.2f} cm/s"))
    f.add_trace(go.Scatter(x=x, y=p["Re"], name="Reynolds number", yaxis="y2", line=dict(color=PINK, width=2.5, dash="dash"), hovertemplate="Re %{y:.2f}"))
    sc = p["scalars"]
    x0 = sc["x_heat_start_cm"] - L / 2
    w = max(sc["L_hydrodynamic_cm"], sc["L_thermal_cm"])
    f.add_vrect(x0=x0, x1=x0 + w, fillcolor="rgba(213,94,0,0.30)", line=dict(color=VERM, width=1), annotation_text=f"entrance {w:.1f} cm", annotation_position="top left",
                annotation_font=dict(size=10, color=VERM))
    for key, col in (("boat_MoO3", BLUE), ("substrate", GREEN)):
        f.add_vline(x=p["stations"][key]["x_cm"] - L / 2, line=dict(color=col, width=1.5, dash="dot"))
    _layout(f, 230, [-L / 2, L / 2], None, "velocity [cm/s]", True)
    f.update_layout(yaxis2=dict(title="Reynolds number [-]", automargin=False, overlaying="y", side="right", fixedrange=True, showgrid=False, rangemode="tozero"))
    f.update_layout(yaxis=dict(rangemode="tozero"))
    return f


def regime(p, v, L):
    """Two thin strips: buoyancy (Ri > Ri_c) and Peclet (axial conduction/diffusion competes with convection). Blue = forced flow/convection, orange = the other."""
    x = _fx(p, L)
    fl = p["flags"]
    f = go.Figure()
    sc = [[0, SKY], [1, VERM]]
    for yy, key, lab in ((1, "buoyancy_matters", "buoyancy"), (0, "axial_conduction_matters", "diffusion")):
        z = np.asarray(fl[key], float)
        f.add_trace(go.Heatmap(x=x, y=[yy], z=[z], zmin=0, zmax=1, colorscale=sc, showscale=False, xgap=0, ygap=3,
                               hovertemplate=("x %{x:.1f} cm: " + ("%{z:.0f} = buoyancy matters (Ri > Ri_c)" if yy else "%{z:.0f} = axial diffusion/conduction matters") + "<extra></extra>")))
    for key, col in (("boat_MoO3", BLUE), ("substrate", GREEN)):
        f.add_vline(x=p["stations"][key]["x_cm"] - L / 2, line=dict(color=col, width=1.5, dash="dot"))
    _layout(f, 130, [-L / 2, L / 2], "position from tube centre [cm]")
    f.update_yaxes(tickvals=[0, 1], ticktext=["Peclet", "buoyancy"], tickfont=dict(size=10), fixedrange=True, range=[-0.6, 1.6], zeroline=False, showgrid=False)
    return f


def overlay(p, leg, v, L):
    """Legacy vs furnace thermal model for the same inputs: wall and gas temperature."""
    f = go.Figure()
    x = _fx(p, L)
    xl = np.asarray(leg["x_cm"], float) - L / 2
    f.add_trace(go.Scatter(x=xl, y=leg["T_C"], name="legacy wall", line=dict(color=GREY, width=2, dash="dash")))
    f.add_trace(go.Scatter(x=x, y=_a(p, "T_wall_K") - K0, name="furnace wall", line=dict(color=GREY, width=2)))
    f.add_trace(go.Scatter(x=xl, y=leg["T_gas_C"], name="legacy gas", line=dict(color=ORANGE, width=2.5, dash="dash")))
    f.add_trace(go.Scatter(x=x, y=_a(p, "T_gas_mean_K") - K0, name="furnace gas mean", line=dict(color=ORANGE, width=2.5)))
    f.add_trace(go.Scatter(x=x, y=_a(p, "T_gas_centre_K") - K0, name="furnace gas centreline", line=dict(color=VERM, width=2)))
    for key, col in (("boat_MoO3", BLUE), ("substrate", GREEN)):
        f.add_vline(x=p["stations"][key]["x_cm"] - L / 2, line=dict(color=col, width=1.5, dash="dot"))
    _layout(f, 280, [-L / 2, L / 2], "position from tube centre [cm]", "temperature [C]", True)
    return f


def overlay_takeaway(p, leg, L):
    x = np.asarray(p["x_cm"], float)
    g_f = _a(p, "T_gas_mean_K") - K0
    g_l = np.interp(x, leg["x_cm"], leg["T_gas_C"])
    w_f, w_l = _a(p, "T_wall_K") - K0, np.interp(x, leg["x_cm"], leg["T_C"])
    xs = p["stations"]["substrate"]["x_cm"]
    d = float(np.interp(xs, x, g_f) - np.interp(xs, x, g_l))
    return (f"At the substrate the furnace model's gas is {abs(d):.0f} K {'hotter' if d > 0 else 'cooler'} than legacy; "
            f"the two wall profiles differ by up to {np.abs(w_f - w_l).max():.0f} K.")
