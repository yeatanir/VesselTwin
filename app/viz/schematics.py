"""Schematics drawn from the live parameter dict (plotly shapes). One function per vessel -> plotly Figure.
Axial lengths are to scale; where a vessel is very slender the transverse axis is exaggerated and the figure says so."""
import numpy as np
import plotly.graph_objects as go
import matplotlib

from app.viz.template import BLUE, NAVY, ACCENT, SKY, apply_template
LINE, FILL, HOT, ACC, GAS = NAVY, "rgba(31,95,191,0.08)", ACCENT, BLUE, "#2E86DE"  # blue and white; orange only for heat/source/marker


FILLS = {ACC: "rgba(31,95,191,0.35)", HOT: "rgba(242,140,40,0.35)"}


def _cmap_hex(v, lo, hi, name="cividis"):
    return matplotlib.colors.to_hex(matplotlib.colormaps[name]((v - lo) / (hi - lo + 1e-9)))


def _base(xr, yr, height=300):
    f = go.Figure()
    f.update_layout(height=height, margin=dict(l=8, r=8, t=8, b=8), showlegend=False,
                    xaxis=dict(visible=False, range=xr, scaleanchor="y", constrain="domain"), yaxis=dict(visible=False, range=yr))
    return apply_template(f)


def _rect(f, x0, x1, y0, y1, fill=FILL, line=LINE, w=1.5, dash=None, tip=None):
    """tip = hover text (component name, temperature, dimensions with units); drawn as an invisible hoverable polygon over the shape."""
    f.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor=fill, line=dict(color=line, width=w, dash=dash))
    if tip:
        _hov(f, [x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], tip)


def _hov(f, xs, ys, tip):
    f.add_trace(go.Scatter(x=list(xs), y=list(ys), mode="lines", fill="toself", fillcolor="rgba(31,95,191,0.01)", line=dict(width=0), hoveron="fills", text=tip,
                           hovertemplate="%{text}<extra></extra>", showlegend=False))


def _txt(f, x, y, s, size=12, color=None, anchor="center", yanchor="middle"):
    f.add_annotation(x=x, y=y, text=s, showarrow=False, font=dict(size=size, **({"color": color} if color else {})), xanchor=anchor, yanchor=yanchor)


def _arrow(f, x0, y0, x1, y1, color=GAS, w=2, head=2):
    f.add_annotation(x=x1, y=y1, ax=x0, ay=y0, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=head, arrowwidth=w, arrowcolor=color, text="")


def _mark(f, x, y, label=None, size=18):
    """Bright star marker for the single most important place (growth, front, lamp)."""
    f.add_trace(go.Scatter(x=[x], y=[y], mode="markers", marker=dict(symbol="star", size=size, color="#FFD400", line=dict(color=NAVY, width=1.5)), hovertemplate=(label or "marker") + "<extra></extra>"))
    if label:
        _txt(f, x, y, label, 11, anchor="left", yanchor="bottom")


def _dim(f, x0, x1, y, text, size=11):
    _arrow(f, x0, y, x1, y, LINE, 1, 2); _arrow(f, x1, y, x0, y, LINE, 1, 2)
    _txt(f, 0.5 * (x0 + x1), y, f" {text} ", size, anchor="center", yanchor="bottom")


def tube(p, Tx=None):
    """Tube furnace. Tx = (x_cm array, T_C array) wall-temperature input profile for the strip."""
    L, ID = p["L_tube_cm"], p["tube_id_in"] * 2.54
    k = max(1.0, L / (10 * ID))  # transverse exaggeration so the tube is visible
    h = ID / 2 * k
    xc, Lh, rp = p["x_furnace_center_cm"], p["L_hot_cm"], p["ramp_cm"]
    f = _base([-0.14 * L, 1.02 * L], [-3.3 * h, 3.0 * h], 300)
    _rect(f, xc - Lh / 2, xc + Lh / 2, -1.5 * h, 1.5 * h, "rgba(242,140,40,0.14)", HOT, 1.2, "dot", tip=f"furnace heated zone<br>{p['T_furnace_C']:g} C, length {Lh:g} cm, ramps {rp:g} cm")
    if Tx is not None:  # temperature heatmap fills the tube (input wall profile)
        f.add_trace(go.Heatmap(x=Tx[0], y=[-0.5 * h, 0.5 * h], z=[Tx[1], Tx[1]], colorscale="Cividis", opacity=0.75, zsmooth="best", hovertemplate=f"tube furnace, L = {L:g} cm, ID = {ID * 10:.1f} mm<br>x %{{x:.1f}} cm<br>wall T (input) %{{z:.0f}} C<extra></extra>",
                               colorbar=dict(title=dict(text="wall T [C]", side="top"), orientation="h", thickness=8, len=0.4, x=0.5, y=-0.02, yanchor="top", xanchor="center")))
    _rect(f, 0, L, -h, h, "rgba(0,0,0,0)", tip=None if Tx is not None else f"tube, L = {L:g} cm, ID = {ID * 10:.1f} mm")
    for xa in np.linspace(0.12 * L, 0.88 * L, 6):
        _arrow(f, xa - 0.02 * L, 0.8 * h, xa + 0.02 * L, 0.8 * h, GAS, 2)
    _txt(f, xc, 1.5 * h, f"furnace {p['T_furnace_C']:g} C", 11, HOT, yanchor="bottom")
    # boats and substrate: square footprints from the boat areas (assumption), height drawn schematically
    for key, x, area, col, name in (("S", p["x_S_boat_cm"], p["boat_area_S_cm2"], ACC, f"S boat {p['T_boat_S_C']:g} C"),
                                     ("Mo", p["x_MoO3_cm"], p["boat_area_MoO3_cm2"], HOT, f"MoO3 boat {p['T_boat_Mo_C']:g} C")):
        w = np.sqrt(area)
        _rect(f, x - w / 2, x + w / 2, -h, -0.4 * h, FILLS[col], col, 2, tip=f"{name}<br>x = {x:g} cm, footprint {w:.1f} x {w:.1f} cm (area {area:g} cm2, drawn square)")
        _txt(f, x, 0.15 * h, name, 11, anchor="center", yanchor="bottom")
    xs = p["x_MoO3_cm"] + p["x_substrate_cm"]
    _rect(f, xs, xs + p["substrate_length_cm"], -h, -0.8 * h, "rgba(31,95,191,0.45)", GAS, 2, tip=f"substrate<br>x = {xs:g} cm, length {p['substrate_length_cm']:g} cm")
    _arrow(f, -0.13 * L, 0, -0.01 * L, 0)
    _txt(f, -0.07 * L, 0.5 * h, f"{p['flow_sccm']:g} sccm {p['carrier']}", 11, GAS, yanchor="bottom")
    _mark(f, xs + p['substrate_length_cm'] / 2, -0.55 * h, 'growth')
    f.update_layout(title=dict(text=None))
    _dim(f, 0, L, -2.2 * h, f"tube L = {L:g} cm, ID = {ID * 10:.1f} mm")
    _txt(f, 0.5 * L, -3.0 * h, f"length to scale, width x{k:.1f}", 10)
    return f


def ampoule(p, Tfun):
    """Sealed ampoule to scale, rotated by the tilt (+ = source end lower). Tfun(s in 0..1) -> wall T [C], source -> sink."""
    L, D, th = p["L_cm"], p["D_mm"] / 10, np.radians(p["tilt_deg"])
    ax, nrm = np.array([np.cos(th), np.sin(th)]), np.array([-np.sin(th), np.cos(th)])
    ctr = np.zeros(2)
    f = _base([-0.62 * L, 0.62 * L], [-0.5 * L * max(abs(np.sin(th)), 0.2) - 0.25 * L, 0.5 * L * max(abs(np.sin(th)), 0.2) + 0.25 * L], 330)
    T1, T2 = p["T_sink_C"], p["T_source_C"]
    lo, hi = min(T1, T2), max(T1, T2)
    n = 40
    for i in range(n):  # wall colour = input wall temperature, source end first
        s0, s1 = i / n, (i + 1) / n
        a, b = ctr + (s0 - .5) * L * ax, ctr + (s1 - .5) * L * ax
        poly = np.array([a + nrm * D / 2, b + nrm * D / 2, b - nrm * D / 2, a - nrm * D / 2, a + nrm * D / 2])
        col = _cmap_hex(Tfun(0.5 * (s0 + s1)), lo, hi)
        f.add_trace(go.Scatter(x=poly[:, 0], y=poly[:, 1], fill="toself", mode="lines", line=dict(width=0, color=col), fillcolor=col, hoverinfo="skip"))
    out = np.array([ctr - .5 * L * ax + nrm * D / 2, ctr + .5 * L * ax + nrm * D / 2, ctr + .5 * L * ax - nrm * D / 2, ctr - .5 * L * ax - nrm * D / 2, ctr - .5 * L * ax + nrm * D / 2])
    f.add_trace(go.Scatter(x=out[:, 0], y=out[:, 1], mode="lines", line=dict(color=LINE, width=2), fill="toself", fillcolor="rgba(31,95,191,0.01)", hoveron="fills", text=f"sealed ampoule<br>{L:g} cm x {p['D_mm']:g} mm, tilt {p['tilt_deg']:g} deg<br>source {p['T_source_C']:g} C, sink {p['T_sink_C']:g} C", hovertemplate="%{text}<extra></extra>"))
    src, snk = ctr - .5 * L * ax, ctr + .5 * L * ax
    vol = np.pi * (D / 2) ** 2 * L  # cm3
    mg = p["agent_mg_per_cm3"] * vol
    # source charge: true solid volume = mass / crystal density (proxy), usually a sliver -> drawn at minimum visible size
    frac = mg / (p["crystal_density_gcm3"] * 1000) / vol
    sl = max(frac * L, 0.04 * L)
    a, b = src + 0.0 * ax, src + sl * ax
    poly = np.array([a + nrm * D / 2, b + nrm * D / 2, b - nrm * D / 2, a - nrm * D / 2, a + nrm * D / 2])
    f.add_trace(go.Scatter(x=poly[:, 0], y=poly[:, 1], fill="toself", mode="lines", line=dict(color=HOT, width=1.5), fillcolor="rgba(242,140,40,0.6)", hoveron="fills", text=f"agent charge {mg:.0f} mg ({p['agent_mg_per_cm3']:g} mg/cm3), drawn at minimum visible size", hovertemplate="%{text}<extra></extra>"))
    for sfr in (0.3, 0.5, 0.7):  # vapour transport arrows, source -> sink
        a0 = ctr + (sfr - 0.5 - 0.06) * L * ax; a1 = ctr + (sfr - 0.5 + 0.06) * L * ax
        _arrow(f, a0[0], a0[1], a1[0], a1[1], GAS, 2)
    _mark(f, *(snk - 0.02 * L * ax), "growth")
    off = nrm * (D / 2 + 0.07 * L)
    _txt(f, *(src + off - 0.05 * ax * L), f"SOURCE {p['T_source_C']:g} C", 12, HOT, anchor="center")
    _txt(f, *(snk + off + 0.05 * ax * L), f"SINK {p['T_sink_C']:g} C", 12, ACC, anchor="center")
    _txt(f, *(ctr - nrm * (D / 2 + 0.12 * L)), f"{L:g} cm x {p['D_mm']:g} mm, tilt {p['tilt_deg']:g} deg", 12)
    _txt(f, *(ctr + nrm * (D / 2 + 0.12 * L)), f"{p['gas']} {p['agent_mg_per_cm3']:g} mg/cm3 ({mg:.0f} mg)", 11)
    g0 = np.array([-0.58 * L, f.layout.yaxis.range[1] * 0.9])
    _arrow(f, g0[0], g0[1], g0[0], g0[1] - 0.2 * L, LINE, 2); _txt(f, g0[0] + 0.02 * L, g0[1] - 0.1 * L, "g", 12, anchor="left")
    return f


def flask(p, geo):
    """Round-bottom flask (spherical, as the Tier 1 model assumes) with liquid, stir bar and rotation. geo from vessels.flask._mix: T (m), depth h (m), d bar (m)."""
    T, h, d = geo["T"] * 1e3, geo["depth"] * 1e3, geo["d"] * 1e3  # mm
    R = T / 2
    f = _base([-1.1 * R, 1.1 * R], [-1.15 * R, 1.35 * R], 380)
    th = np.linspace(0, 2 * np.pi, 200)
    f.add_trace(go.Scatter(x=R * np.cos(th), y=R * np.sin(th), mode="lines", line=dict(color=LINE, width=2), hoverinfo="skip"))
    yl = -R + h
    # liquid polygon: lower arc below the free surface + chord
    phi = np.arcsin(np.clip(yl / R, -1, 1))
    arc = np.linspace(np.pi - phi, 2 * np.pi + phi, 120)
    lx, ly = np.r_[R * np.cos(arc), R * np.cos(arc[0])], np.r_[R * np.sin(arc), R * np.sin(arc[0])]
    f.add_trace(go.Scatter(x=lx, y=ly, fill="toself", mode="lines", line=dict(color=ACC, width=1), fillcolor="rgba(31,95,191,0.22)", hoveron="fills", text=f"{p['volume_mL']:g} mL {p['solvent']}, depth {h:.0f} mm, {p['fill_frac'] * 100:.0f} % full", hovertemplate="%{text}<extra></extra>"))
    _rect(f, -d / 2, d / 2, -R + 0.01 * R, -R + 0.01 * R + 0.12 * d, "rgba(242,140,40,0.7)", HOT, 1.5, tip=f"stir bar {p['bar_mm']:g} mm, {p['stir_rpm']:g} rpm")
    _arrow(f, -d, -0.62 * R, d, -0.62 * R, HOT, 2); _txt(f, 0, -0.55 * R, f"{p['stir_rpm']:g} rpm", 12, HOT, yanchor="bottom")
    _txt(f, 0, 1.3 * R, f"{p['volume_mL']:g} mL {p['solvent']}, {p['fill_frac'] * 100:.0f} % full", 12)
    _dim(f, -R, R, 1.08 * R, f"{T:.0f} mm")
    _mark(f, d / 2, -R + 0.07 * R, None, 16)
    _txt(f, 0, -R - 0.03 * R, f"stir bar {p['bar_mm']:g} mm", 11, HOT, yanchor="top")
    return f


def sorbent(p, zc=None):
    """zc = (z_cm, y/y_feed) at one time: bed coloured by CO2 concentration, bright marker at the 50 % front."""
    L, D = p["bed_length_cm"], p["bed_id_cm"]
    k = max(1.0, L / (8 * D))
    h = D / 2 * k
    f = _base([-0.2 * L, 1.2 * L], [-3 * h, 3 * h], 260)
    if zc is not None:
        f.add_trace(go.Heatmap(x=zc[0], y=[-0.5 * h, 0.5 * h], z=[zc[1], zc[1]], zmin=0, zmax=1, colorscale="Blues", opacity=0.8, zsmooth="best", hovertemplate=f"sorbent bed, L = {L:g} cm, ID = {D * 10:g} mm, {p['T_K']:g} K<br>z %{{x:.1f}} cm<br>CO2 / feed %{{z:.2f}} [-]<extra></extra>",
                               colorbar=dict(title=dict(text="CO2 / feed [-]", side="top"), orientation="h", thickness=8, len=0.4, x=0.5, y=-0.02, yanchor="top", xanchor="center")))
        cz = np.asarray(zc[1]); k50 = int(np.argmax(cz < 0.5)) if (cz < 0.5).any() else None
        if k50:
            _mark(f, zc[0][k50], 0, "front")
    _rect(f, 0, L, -h, h, "rgba(0,0,0,0)" if zc is not None else FILL, tip=None if zc is not None else f"sorbent bed, L = {L:g} cm, ID = {D * 10:g} mm, {p['T_K']:g} K")
    rng = np.random.default_rng(1)
    n = 260
    f.add_trace(go.Scatter(x=rng.uniform(0.01 * L, 0.99 * L, n), y=rng.uniform(-0.9 * h, 0.9 * h, n), mode="markers", marker=dict(size=4, color="rgba(160,160,160,0.7)"), hoverinfo="skip"))
    _arrow(f, -0.18 * L, 0, -0.01 * L, 0); _arrow(f, 1.01 * L, 0, 1.18 * L, 0)
    _txt(f, -0.1 * L, 0.5 * h, f"{p['flow_sccm']:g} sccm", 11, GAS, yanchor="bottom")
    _txt(f, -0.1 * L, -0.5 * h, f"CO2 {p['y_feed'] * 100:g} %, {p['carrier']}", 11, GAS, yanchor="top")
    _txt(f, 1.1 * L, 0.5 * h, "outlet", 11, GAS, yanchor="bottom")
    _dim(f, 0, L, -1.6 * h, f"bed L = {L:g} cm, ID = {D * 10:g} mm")
    _txt(f, 0.5 * L, 1.7 * h, f"{p['T_K']:g} K, {p['P_kPa']:g} kPa", 11, yanchor="bottom")
    _txt(f, 0.5 * L, -2.8 * h, f"length to scale, width x{k:.1f}" if k > 1 else "to scale", 10)
    return f


def photoreactor(p, T_wall, geo=None, flux=None):
    """Side view: lamp at dist_cm from the wall (thickness wall_mm), liquid slab path_cm deep, rays. T_wall = wall transmission."""
    d, w, path = p["dist_cm"], p["wall_mm"] / 10, p["path_cm"]
    tot = d + w + path
    H = max(0.9 * tot, 4.0)
    f = _base([-0.15 * tot, 1.25 * tot], [-0.7 * H, 0.7 * H], 340)
    lamp_h = p["lamp_len_cm"] if p["lamp_geom"] == "line" else 0.0
    if p["lamp_geom"] == "line":
        _rect(f, -0.015 * tot, 0.015 * tot, -min(lamp_h, 1.3 * H) / 2, min(lamp_h, 1.3 * H) / 2, "rgba(242,140,40,0.8)", HOT, 1.5, tip=f"lamp, {p['P_rad_W']:g} W radiant, {p['lambda_nm']:g} nm, length {p['lamp_len_cm']:g} cm")
    else:
        f.add_trace(go.Scatter(x=[0], y=[0], mode="markers", marker=dict(size=16, color="#E69F00", line=dict(color=HOT, width=2)), hoverinfo="skip"))
    _rect(f, d, d + w, -0.6 * H, 0.6 * H, "rgba(31,95,191,0.35)", ACC, 1.5, tip=f"vessel wall, {p['wall_mm']:g} mm thick, transmission {T_wall:.2f}")
    if flux is not None:  # photon flux density vs depth (Beer-Lambert) colours the liquid
        zz = np.linspace(d + w, tot, len(flux))
        f.add_trace(go.Heatmap(x=zz, y=[-0.3 * H, 0.3 * H], z=[flux, flux], colorscale="Blues", opacity=0.85, zsmooth="best", hovertemplate=f"liquid slab, path {path:g} cm<br>photon flux %{{z:.3g}} umol/s/cm2<extra></extra>",
                               colorbar=dict(title=dict(text="photon flux [umol/s/cm2]", side="top"), orientation="h", thickness=8, len=0.4, x=0.5, y=-0.02, yanchor="top", xanchor="center")))
    _rect(f, d + w, tot, -0.6 * H, 0.6 * H, "rgba(0,0,0,0)" if flux is not None else "rgba(46,134,222,0.15)", GAS, 1.5, tip=None if flux is not None else f"liquid slab, path {path:g} cm")
    for y in np.linspace(-0.45 * H, 0.45 * H, 7):
        if p["illum"] == "collimated":
            _arrow(f, 0.0, y, d + w + 0.5 * path, y, "#E69F00", 1)
        else:
            _arrow(f, 0.0, 0.0, d, y * 0.9, "#E69F00", 1)
            _arrow(f, d, y * 0.9, d + w + 0.5 * path, y * 0.7, "#E69F00", 1)
    _txt(f, 0, 0.62 * H, f"{p['P_rad_W']:g} W lamp, {p['lambda_nm']:g} nm", 11, anchor="left", yanchor="bottom")
    _txt(f, d + w / 2, -0.62 * H, f"wall {p['wall_mm']:g} mm", 11, ACC, anchor="center", yanchor="top")
    _txt(f, d + w + path / 2, 0.66 * H, f"liquid {path:g} cm", 11, GAS, yanchor="bottom", anchor="left")
    _dim(f, 0, d, -0.52 * H, f"{d:g} cm")
    _dim(f, d + w, tot, -0.52 * H, f"{path:g} cm")
    return f
