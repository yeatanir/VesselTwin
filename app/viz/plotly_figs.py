"""Public Plotly figure API (Track R). Every function returns a styled plotly Figure (template 'vesseltwin'), no network resources, built from cached data.
  vessel_hero, cfd_field, profiles, knob_bars, furnace_figs, apply_template."""
import functools
import numpy as np
import plotly.graph_objects as go
from app.viz import fields, profiles as _prof, schematics
from app.viz.template import apply_template, BLUE, ACCENT, NAVY, GREY

__all__ = ["vessel_hero", "cfd_field", "profiles", "knob_bars", "furnace_figs", "apply_template"]
UNITS = {"cvd_tube": ("cm", "mm", 100.0, 1000.0), "ampoule": ("cm", "mm", 100.0, 1000.0), "flask": ("mm", "mm", 1000.0, 1000.0)}


def vessel_hero(vessel, result, spec=None, height=380):
    """Interactive vessel figure: stored CFD field behind the vessel when a case exists (nearest to the live inputs), else the to-scale schematic."""
    from app import vessel_view as vv  # lazy: vessel_view imports this package
    vals = result["values"]
    m = vv._hero_case(vessel, vals) if vessel in fields.HERO_FIELD else None
    if m is not None:
        f = go.Figure(vv._cfd_hero(m["name"]))
        f.update_layout(title=dict(text=f"{m['case']}: stored CFD result, not re-run", font=dict(size=12)), margin=dict(l=10, r=10, t=30, b=110))
    else:
        f = go.Figure(vv._schematic(vessel, vv._key(vals)))
    return apply_template(f.update_layout(height=height))


@functools.lru_cache(maxsize=16)
def _lines(name):
    """Streamlines thinned to keep the figure JSON small."""
    d, _ = fields.load(name)
    xs, ys = fields.streamlines(d, 1.0)
    xs, ys = list(xs), list(ys)
    keep_x, keep_y, k = [], [], 0
    for a, b in zip(xs, ys):
        if a is None:
            keep_x.append(None); keep_y.append(None); k = 0
        else:
            if k % 2 == 0:
                keep_x.append(round(a, 6)); keep_y.append(round(b, 6))
            k += 1
    return keep_x, keep_y


def cfd_field(vessel, field="T", case=None):
    """Stored OpenFOAM field as an interactive heatmap with streamlines and a field dropdown; None when the vessel has no stored case."""
    metas = fields.available(vessel)
    if not metas:
        return None
    if case is not None:
        sel = [m for m in metas if case in (m["name"], m["case"])]
        m = sel[0] if sel else metas[0]
    else:
        vert = [x for x in metas if vessel != "flask" or "vertical" in x["name"]]
        m = (vert or metas)[0]
    d, meta = fields.load(m["name"])
    st = max(1, len(d["x"]) // 180)  # thin the grid: keeps the figure JSON small, hover still shows local values
    d = {k: (v[::st] if k == "x" else v[:, ::st] if v.ndim == 2 else v) for k, v in d.items()}
    xu, yu, xs, ys = UNITS.get(vessel, ("mm", "mm", 1000.0, 1000.0))
    names = [k for k in meta["fields"]]
    first = field if field in names else names[0]
    f = go.Figure()
    for k in names:
        spec = meta["fields"][k]
        z = d[k].astype(np.float32)
        zp = np.log10(np.maximum(z, 1e-30)) if spec.get("log") else z
        f.add_trace(go.Heatmap(x=d["x"] * xs, y=d["y"] * ys, z=zp, customdata=z if spec.get("log") else None, name=spec["label"], visible=(k == first), zsmooth="best",
                               colorscale=fields.CMAP.get(k, "Blues"),
                               colorbar=dict(title=dict(text=("log10 " if spec.get("log") else "") + f"{spec['label']} [{spec['unit']}]", side="right"), thickness=12, len=0.9),
                               hovertemplate=f"x %{{x:.2f}} {xu}<br>y %{{y:.2f}} {yu}<br>{spec['label']}: %{{" + ("customdata" if spec.get("log") else "z") + f":.4g}} {spec['unit']}<extra></extra>"))
    lx, ly = _lines(m["name"])
    f.add_trace(go.Scatter(x=[None if v is None else v * xs for v in lx], y=[None if v is None else v * ys for v in ly], mode="lines", name="streamlines",
                           line=dict(color=ACCENT, width=0.8), opacity=0.8, hoverinfo="skip"))
    n = len(names)
    f.update_layout(
        height=360, margin=dict(l=10, r=10, t=70, b=10), xaxis_title=f"x [{xu}]", yaxis_title=f"y [{yu}]", showlegend=True,
        title=dict(text=f"{m['case']} - stored CFD result, not re-run<br><sup>{m['n_cells']:,} cells, made {m['date_made']}; plane: {m['plane']}</sup>", font=dict(size=13)),
        legend=dict(orientation="h", y=-0.02, yanchor="top"),
        updatemenus=[dict(type="dropdown", x=0.0, y=1.0, xanchor="left", yanchor="bottom", pad=dict(t=0, b=4), bgcolor="white", bordercolor=BLUE,
                          buttons=[dict(label=meta["fields"][k]["label"], method="update",
                                        args=[{"visible": [j == i for j in range(n)] + [True]}]) for i, k in enumerate(names)])])
    f.update_xaxes(range=[float(d["x"].min() * xs), float(d["x"].max() * xs)], constrain="domain")
    f.update_yaxes(range=[float(d["y"].min() * ys), float(d["y"].max() * ys)], constrain="domain")
    if vessel != "cvd_tube":
        f.update_yaxes(scaleanchor="x", scaleratio=xs / ys)
    return apply_template(f)


def _slider_sorbent(vessel, vals):
    z, t, T, c = _prof._sorbent_cached(tuple(sorted(vals.items())))
    ks = np.unique(np.linspace(0, len(t) - 1, 30).astype(int))
    from plotly.subplots import make_subplots
    f = make_subplots(specs=[[{"secondary_y": True}]])
    for j, k in enumerate(ks):
        vis = j == len(ks) // 3
        f.add_trace(go.Scatter(x=z, y=c[k], name="CO2 / feed (model output)", visible=vis, legendgroup="c", showlegend=vis, line=dict(color=BLUE, width=2.4),
                               hovertemplate="%{y:.3f} [-]<extra>CO2 / feed</extra>"), secondary_y=False)
        f.add_trace(go.Scatter(x=z, y=T[k], name="bed temperature (model output)", visible=vis, legendgroup="T", showlegend=vis, line=dict(color=ACCENT, width=2.4, dash="dash"),
                               hovertemplate="%{y:.1f} K<extra>bed temperature</extra>"), secondary_y=True)
    steps = []
    for j, k in enumerate(ks):
        vis = [False] * (2 * len(ks)); vis[2 * j] = vis[2 * j + 1] = True
        steps.append(dict(method="update", label=f"{t[k]:.0f}", args=[{"visible": vis, "showlegend": [x for x in vis]}]))
    f.update_layout(sliders=[dict(active=len(ks) // 3, steps=steps, currentvalue=dict(prefix="time into run [min]: "), pad=dict(t=30))], height=380, hovermode="x unified",
                    title=dict(text="Bed state vs position (no uncertainty band computed)", font=dict(size=14)), xaxis_title="position along bed z [cm]",
                    legend=dict(orientation="h", y=1.08))
    f.update_yaxes(title_text="y / y_feed [-]", range=[0, 1.05], secondary_y=False)
    f.update_yaxes(title_text="temperature [K]", secondary_y=True, showgrid=False)
    return apply_template(f)


def profiles(vessel, result, spec=None):
    """list of (title, Figure): Tier 1 profiles with p05-p95 bands, unified hover, toggleable legend; sorbent has a time slider (no autoplay)."""
    vals, ex = result["values"], result.get("extras") or {}
    out = []
    if vessel == "cvd_tube":
        figs, _ = _prof.tube_figs(vals, ex)
        out = [(f.layout.title.text, f) for f in figs]
    elif vessel == "ampoule":
        out = [(f.layout.title.text, f) for f in _prof.ampoule_figs(vals, result["passport"])]
    elif vessel == "sorbent":
        out = [("Bed state vs position", _slider_sorbent(vessel, vals))]
    elif vessel == "photoreactor" and ex.get("photon_flux_vs_depth"):
        f = _prof.photon_fig(ex)
        out = [(f.layout.title.text, f)]
    return [(t, apply_template(f)) for t, f in out]


def knob_bars(effects, unit=""):
    """Horizontal effect bars (blue raises, orange lowers) with p05-p95 whiskers. effects = [{name, effect, lo, hi}] from home.knob_effects."""
    rows = list(effects)[::-1]  # largest on top
    u = f" {unit}" if unit else ""
    eff = np.array([r["effect"] for r in rows], float)
    f = go.Figure(go.Bar(
        y=[r["name"] for r in rows], x=eff, orientation="h", marker_color=[BLUE if e >= 0 else ACCENT for e in eff],
        error_x=dict(type="data", symmetric=False, array=[max(r["hi"] - r["effect"], 0) for r in rows], arrayminus=[max(r["effect"] - r["lo"], 0) for r in rows], color=NAVY, thickness=1.6, width=5),
        customdata=[[r["lo"], r["hi"]] for r in rows],
        hovertemplate="%{y}<br>change %{x:.3g}" + u + "<br>p05 to p95: %{customdata[0]:.3g} to %{customdata[1]:.3g}" + u + "<extra></extra>"))
    f.update_layout(height=max(180, 46 * len(rows) + 70), margin=dict(l=10, r=10, t=10, b=10), showlegend=False, xaxis_title="change in result" + (f" [{unit}]" if unit else ""),
                    bargap=0.35, yaxis=dict(automargin=True))
    f.add_vline(x=0, line=dict(color=NAVY, width=1))
    return apply_template(f)


def furnace_figs(p, values=None):
    """Furnace-and-flow figures (Track O) in the new template: [(title, Figure)]. values = the tube's parameter dict (defaults when omitted)."""
    from app.viz import furnace as fz
    if values is None:
        from core import api
        values = api.solve("cvd_tube", {}, n_mc=2, extras=False)["values"]
    L = float(values["L_tube_cm"])
    tmin, tmax = fz.temp_range_C(p)
    figs = [("Furnace and tube schematic", fz.schematic(p, values, L, tmin, tmax)), ("Temperatures", fz.temperatures(p, values, L, tmin, tmax)),
            ("Gas speed and Reynolds number", fz.velocity(p, values, L)), ("Regime strips", fz.regime(p, values, L))]
    return [(t, apply_template(f)) for t, f in figs]
