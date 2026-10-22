"""Tier 1 profiles. Model output = solid line + p05-p95 band (where the model has parameter sigmas); input = dashed line, labelled."""
import numpy as np
import plotly.graph_objects as go

from app.viz.template import BLUE, ACCENT as ORANGE, SKY as GREEN, PINK as PURPLE, apply_template


def _rgba(h, a):
    h = h.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def _style(f, height, title, xlabel, ylabel, logy=False):
    f.update_layout(height=height, margin=dict(l=10, r=10, t=40 if title else 14, b=10), title=dict(text=title, font=dict(size=14)) if title else None,
                    xaxis_title=xlabel, yaxis_title=ylabel, yaxis_type="log" if logy else "linear", legend=dict(orientation="h", y=-0.3, font=dict(size=11)), hovermode="x unified")
    f.update_xaxes(showgrid=True, automargin=True, title_standoff=8)
    f.update_yaxes(showgrid=True, automargin=True, title_standoff=8)
    return apply_template(f)


def line_fig(curves, xlabel, ylabel, height=260, logy=False, vlines=(), title=None):
    """curves: dict(name, x, y, kind 'model'|'input', color, p05?, p95?). Legend text carries the kind, not colour alone."""
    f = go.Figure()
    for c in curves:
        col, model = c.get("color", BLUE), c.get("kind", "model") == "model"
        nm = f"{c['name']} ({'model output' if model else 'input'})"
        if c.get("p05") is not None:
            f.add_trace(go.Scatter(x=np.r_[c["x"], c["x"][::-1]], y=np.r_[c["p95"], np.asarray(c["p05"])[::-1]], fill="toself", mode="lines", line=dict(width=0),
                                   fillcolor=_rgba(col, 0.2), hoverinfo="skip", showlegend=False))
        f.add_trace(go.Scatter(x=c["x"], y=c["y"], name=nm, mode="lines", line=dict(color=col, width=2.2, dash=None if model else "dash"),
                               hovertemplate="%{y:.4g} " + ylabel[ylabel.find("[") + 1:ylabel.rfind("]")] + "<extra>" + nm + "</extra>" if "[" in ylabel else None))
    for x, lab in vlines:
        f.add_vline(x=x, line=dict(color="#7A8699", width=1, dash="dot"), annotation_text=lab, annotation_position="top")
    return _style(f, height, title, xlabel, ylabel, logy)


def tube_bands(values, n=60, seed=0):
    """p05/p50/p95 of the 1D march over the ParamDef sigmas (same sampler as the passport Monte Carlo), on the nominal x grid."""
    from core import uq
    from core.registry import load_all
    from vessels.cvd_tube import march
    defs = load_all()["cvd_tube"].defs
    x0, T0, o0, _ = march(values)
    rng = np.random.default_rng(seed)
    runs = {"Tg": [], "pM": [], "pS": []}
    for i in range(n):
        try:
            x, T, o, _ = march(values if i == 0 else uq.sample(defs, values, rng))
        except Exception:
            continue
        runs["Tg"].append(np.interp(x0, x, o["Tg"] - 273.15))
        runs["pM"].append(np.interp(x0, x, o["pM"])); runs["pS"].append(np.interp(x0, x, o["pS"]))
    q = lambda k: tuple(np.percentile(np.array(runs[k]), [5, 50, 95], axis=0))
    return {"x_cm": x0 * 100, "T_wall_C": T0 - 273.15, "n": len(runs["Tg"]), **{k: q(k) for k in runs}}


def tube_figs(values, extras, n=60):
    b = tube_bands(values, n)
    vl = [(values["x_S_boat_cm"], "S boat"), (values["x_MoO3_cm"], "MoO3 boat"), (values["x_MoO3_cm"] + values["x_substrate_cm"], "substrate")]
    x, fl = b["x_cm"], lambda a: np.maximum(a, 1e-12)
    f1 = line_fig([dict(name="wall T", x=x, y=b["T_wall_C"], kind="input", color=ORANGE),
                   dict(name="gas T", x=x, y=b["Tg"][1], p05=b["Tg"][0], p95=b["Tg"][2], color=BLUE)],
                  "position along tube x [cm]", "temperature [C]", vlines=vl, title="Furnace wall and gas temperature")
    f2 = line_fig([dict(name="MoO3 partial pressure", x=x, y=fl(b["pM"][1]), p05=fl(b["pM"][0]), p95=fl(b["pM"][2]), color=ORANGE),
                   dict(name="S2 partial pressure", x=x, y=fl(b["pS"][1]), p05=fl(b["pS"][0]), p95=fl(b["pS"][2]), color=GREEN)],
                  "position along tube x [cm]", "partial pressure [Pa]", logy=True, vlines=vl, title="MoO3 and S2 partial pressures")
    figs = [f1, f2]
    sm = (extras or {}).get("shape_map")
    if sm:
        figs.append(line_fig([dict(name="shape index, hypothesis", x=sm["x_cm"], y=sm["shape_index"], p05=sm["p05"], p95=sm["p95"], color=PURPLE)],
                             "position along tube x [cm]", "shape index (0 hexagon, 1 triangle) [-]", vlines=vl, title="Deposition shape vs position (synthetic edge rates)")
                    .update_yaxes(range=[-0.05, 1.05]))
    return figs, b["n"]


def ampoule_figs(values, passport):
    L = values["L_cm"]
    s = np.linspace(0, 1, 101)
    T2, T1 = values["T_source_C"], values["T_sink_C"]
    if values["T_profile"] == "two_zone":
        zf = values["zone_frac"]; T = np.interp(s, [0, zf, 1 - zf, 1], [T2, T2, T1, T1])
    else:
        T = T2 + (T1 - T2) * s
    figs = [line_fig([dict(name="wall T", x=s * L, y=T, kind="input", color=ORANGE)], "position from source end [cm]", "temperature [C]", height=230,
                     title="Wall temperature along the ampoule")]
    sp = {q: d for qs in passport["species"].values() for q, d in qs.items()}
    ps, pk = sp.get("p_source_Pa"), sp.get("p_sink_Pa")
    if ps and pk:
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=[0, L], y=[ps["p50"], pk["p50"]], mode="lines", line=dict(color=BLUE, dash="dot", width=1.5), name="straight line between the end values (NOT a model profile)"))
        f2.add_trace(go.Scatter(x=[0, L], y=[ps["p50"], pk["p50"]], mode="markers", marker=dict(color=BLUE, size=10), name="carrier partial pressure at the ends (model output)",
                                error_y=dict(type="data", symmetric=False, array=[ps["p95"] - ps["p50"], pk["p95"] - pk["p50"]],
                                             arrayminus=[ps["p50"] - ps["p05"], pk["p50"] - pk["p05"]], thickness=2, width=6)))
        figs.append(_style(f2, 270, "Carrier partial pressure at source and sink (p05-p95)", "position from source end [cm]", "partial pressure [Pa]"))
    return figs


def sorbent_states(values):
    """Full bed state from the model's own simulate(): z [cm], t [min], T [K] (t, z), y/y_feed (t, z). Read-only use of the public function."""
    from vessels import sorbent
    s, t, co, Y, _ = sorbent.simulate(values)
    ix, n = s["ix"], s["n"]
    z = (np.arange(n) + 0.5) * values["bed_length_cm"] / n
    T = Y[:, :, ix["T"]] if "T" in ix else np.full(Y.shape[:2], s["T0"])
    return z, t / 60, T, Y[:, :, ix["yc"]] / s["yc"]


def sorbent_fig(z, T, c, t_min):
    from plotly.subplots import make_subplots
    f = make_subplots(specs=[[{"secondary_y": True}]])
    f.add_trace(go.Scatter(x=z, y=c, name="CO2 mole fraction / feed (model output)", line=dict(color=BLUE, width=2.4)), secondary_y=False)
    f.add_trace(go.Scatter(x=z, y=T, name="bed temperature (model output)", line=dict(color=ORANGE, width=2.4, dash="dash")), secondary_y=True)
    _style(f, 300, f"Bed state at t = {t_min:.1f} min (no uncertainty band computed)", "position along bed z [cm]", None)
    f.update_yaxes(title_text="y / y_feed [-]", range=[0, 1.05], secondary_y=False)
    f.update_yaxes(title_text="temperature [K]", secondary_y=True, showgrid=False)
    return f


def photon_fig(ex):
    d = ex["photon_flux_vs_depth"]
    return line_fig([dict(name="photon flux density", x=d["x"], y=d["p50"], p05=d["p05"], p95=d["p95"], color=GREEN)], f"{d['x_label']} [{d['x_unit']}]",
                    f"{d['y_label']} [{d['y_unit']}]", title="Photon flux vs depth (Beer-Lambert, p05-p95 over input sigmas)")


def _sorbent_cached(key):
    import functools
    return _sc(key)


import functools as _ft


@_ft.lru_cache(maxsize=4)
def _sc(key):
    return sorbent_states(dict(key))
