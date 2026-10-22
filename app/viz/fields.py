"""Stored OpenFOAM field maps: load data/viz_cache/*.npz (made by scripts/export_fields.py) and draw them. Never runs a solver."""
import json, pathlib
import numpy as np
import plotly.graph_objects as go
from app.viz.template import apply_template, ACCENT

CACHE = pathlib.Path(__file__).resolve().parents[2] / "data" / "viz_cache"
CMAP = {"T": "Cividis", "speed": "Blues", "epsilon": "Blues", "nut": "Blues"}  # sequential, colour-blind safe; signed quantities would need a diverging map (none shown)
# parameters compared between the stored case and the live inputs (only keys present in both are compared)
KEYS = {"cvd_tube": ["T_furnace_C", "T_boat_Mo_C", "T_boat_S_C", "flow_sccm", "tube_id_in", "pressure_Pa", "carrier"],
        "ampoule": ["L_cm", "D_mm", "tilt_deg", "T_source_C", "T_sink_C", "agent_mg_per_cm3", "inert_Ar_mbar"],
        "flask": ["stir_rpm", "volume_mL", "bar_mm", "fill_frac", "solvent", "T_C"]}


def load(name):
    z = np.load(CACHE / f"{name}.npz", allow_pickle=False)
    d = {k: z[k] for k in z.files if k != "meta"}
    return d, json.loads(str(z["meta"]))


def available(vessel):
    out = []
    for f in sorted(CACHE.glob("*.npz")) if CACHE.exists() else []:
        try:
            meta = json.loads(str(np.load(f)["meta"]))
        except Exception:
            continue
        if meta["vessel"] == vessel:
            out.append(meta)
    return out


def case_values(meta, vessel):
    """Parameters of the stored case in the dashboard's names (flask: derived from the case file)."""
    v = dict(meta.get("params") or {})
    t2 = meta.get("tier2") or {}
    if vessel == "flask":
        v.setdefault("stir_rpm", round(t2.get("N", 0) * 60, 1) if t2.get("N") else None)
        v.setdefault("bar_mm", round(t2["d"] * 1e3, 2) if t2.get("d") else None)
    return v


def differences(meta, live, vessel):
    cv = case_values(meta, vessel)
    out = []
    for k in KEYS.get(vessel, []):
        if cv.get(k) is not None and k in live and cv[k] != live[k]:
            a, b = cv[k], live[k]
            same = isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) <= 1e-6 * max(abs(a), abs(b), 1)
            if not same:
                out.append(f"{k}: stored {a:g} / live {b:g}" if isinstance(a, (int, float)) and isinstance(b, (int, float)) else f"{k}: stored {a} / live {b}")
    return out


def nearest(metas, live, vessel):
    """Index of the stored case closest to the live parameters (fewest/smallest differences)."""
    def score(m):
        cv, s = case_values(m, vessel), 0.0
        for k in KEYS.get(vessel, []):
            if cv.get(k) is not None and isinstance(live.get(k), (int, float)) and isinstance(cv[k], (int, float)):
                s += abs(cv[k] - live[k]) / (abs(live[k]) + 1e-9)
        return s
    return int(np.argmin([score(m) for m in metas])) if metas else 0


def streamlines(d, density=1.3):
    """Streamline polylines (physical coordinates) via matplotlib's integrator on the unit-scaled grid, so lines are evenly spread on the stretched plot."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    x, y, u, v = d["x"].astype(float), d["y"].astype(float), d["u"].astype(float), d["v"].astype(float)
    sx, sy = np.ptp(x) or 1.0, np.ptp(y) or 1.0
    mask = ~np.isfinite(u) | ~np.isfinite(v)
    uu, vv = np.ma.masked_array(np.nan_to_num(u) / sx, mask), np.ma.masked_array(np.nan_to_num(v) / sy, mask)
    ax = Figure().subplots()
    try:
        sp = ax.streamplot(np.linspace(0, 1, len(x)), np.linspace(0, 1, len(y)), uu, vv, density=density, arrowsize=0.1, integration_direction="both")
    except Exception:
        return np.array([]), np.array([])
    xs, ys = [], []
    for seg in sp.lines.get_segments():  # each item is one polyline (n, 2)
        xs += list(seg[:, 0] * sx + x.min()) + [None]
        ys += list(seg[:, 1] * sy + y.min()) + [None]
    return xs, ys


def field_fig(d, meta, field, show_lines=True, xscale=100.0, yscale=1000.0, xunit="cm", yunit="mm", height=300, lines=None, equal=False):
    spec = meta["fields"][field]
    z = d[field].astype(float)
    log = spec.get("log")
    zp = np.log10(np.maximum(z, 1e-30)) if log else z
    title = ("log10 " if log else "") + f"[{spec['unit']}]"
    st = max(1, len(d["x"]) // 200)  # thin wide grids: smaller figure JSON, same look
    zp = zp[:, ::st].astype(np.float32)
    if log:
        z = z[:, ::st]
    f = go.Figure(go.Heatmap(x=d["x"][::st] * xscale, y=d["y"] * yscale, z=zp, colorscale=CMAP.get(field, "Blues"), zsmooth="best",
                             colorbar=dict(title=dict(text=title, side="right"), thickness=12, len=0.9),
                             customdata=z if log else None, hovertemplate=f"x %{{x:.2f}} {xunit}<br>y %{{y:.2f}} {yunit}<br>{spec['label']}: %{{" + ("customdata" if log else "z") + f":.4g}} {spec['unit']}<extra></extra>"))
    if show_lines and lines is not None and len(lines[0]):
        f.add_trace(go.Scatter(x=np.array(lines[0], dtype=float) * xscale, y=np.array(lines[1], dtype=float) * yscale, mode="lines", line=dict(color=ACCENT, width=0.8),
                               opacity=0.8, hoverinfo="skip", showlegend=False))
    f.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), xaxis_title=f"x [{xunit}]", yaxis_title=f"y [{yunit}]", xaxis_automargin=True, yaxis_automargin=True)
    apply_template(f)
    if equal:
        f.update_yaxes(scaleanchor="x", scaleratio=xscale / yscale, range=[float(d["y"].min() * yscale), float(d["y"].max() * yscale)], constrain="domain")
    f.update_xaxes(range=[float(d["x"].min() * xscale), float(d["x"].max() * xscale)], constrain="domain")
    return f


HERO_FIELD = {"cvd_tube": "Y_MoO3", "ampoule": "Y_AIn", "flask": "speed"}


def hero_fig(d, meta, vessel, lines, height=360):
    """Centrepiece: stored-CFD field behind the vessel outline, streamlines with arrowheads, vessel features and one bright marker."""
    fld = HERO_FIELD.get(vessel) or next(iter(meta["fields"]))
    xs, ys = (100.0, 1000.0) if vessel != "flask" else (1000.0, 1000.0)
    xu, yu = ("cm", "mm") if vessel != "flask" else ("mm", "mm")
    f = field_fig(d, meta, fld, False, xs, ys, xu, yu, height, None, equal=vessel != "cvd_tube")
    f.data[0].colorbar.title.text = f"{meta['fields'][fld]['label']} [{meta['fields'][fld]['unit']}]"
    f.data[0].colorbar.title.side = "top"
    f.data[0].colorbar.orientation = "h"; f.data[0].colorbar.y = -0.28; f.data[0].colorbar.yanchor = 'top'; f.data[0].colorbar.len = 0.5; f.data[0].colorbar.thickness = 10; f.data[0].colorbar.x = 0.5
    X, Y = np.array(lines[0], dtype=object), np.array(lines[1], dtype=object)
    f.add_trace(go.Scatter(x=[None if v is None else v * xs for v in lines[0]], y=[None if v is None else v * ys for v in lines[1]], mode="lines",
                           line=dict(color=ACCENT, width=1.1), hoverinfo="skip", showlegend=False))
    # arrowheads: every ~25th vertex of each polyline, rotated along the local direction (screen space, so use the plot aspect)
    ax, ay = float(np.ptp(d["x"]) * xs), float(np.ptp(d["y"]) * ys)
    W, H = 1000.0, float(height)
    if vessel != "cvd_tube":
        H = W * ay / ax
    px, py, ang, run = [], [], [], []
    for xv, yv in zip(lines[0], lines[1]):
        if xv is None:
            for i in (range(12, len(run) - 1, 25) if len(run) >= 30 else []):
                (x0, y0), (x1, y1) = run[i - 1], run[i + 1]
                px.append(x1 * xs); py.append(y1 * ys)
                ang.append(float(np.degrees(np.arctan2((x1 - x0) * xs / ax * W, (y1 - y0) * ys / ay * H))))
            run = []
        else:
            run.append((xv, yv))
    f.add_trace(go.Scatter(x=px, y=py, mode="markers", marker=dict(symbol="arrow", size=9, angle=ang, color=ACCENT, line=dict(color="rgba(11,37,69,0.7)", width=0.6)),
                           hoverinfo="skip", showlegend=False))
    p = meta.get("params") or {}
    ymax = float(d["y"].max() * ys)
    if vessel == "cvd_tube" and p:
        for key, col, nm in (("x_S_boat_cm", "#56B4E9", "S boat"), ("x_MoO3_cm", "#E69F00", "MoO3 boat")):
            if key in p:
                f.add_shape(type="line", x0=p[key], x1=p[key] + 0.25, y0=ymax, y1=ymax, line=dict(color=col, width=8))
                f.add_annotation(x=p[key], y=ymax, text=nm, showarrow=False, yshift=12, font=dict(size=11))
        if "x_MoO3_cm" in p and "x_substrate_cm" in p:
            xsub = p["x_MoO3_cm"] + p["x_substrate_cm"] + 0.5
            f.add_trace(go.Scatter(x=[xsub], y=[ymax], mode="markers+text", text=["growth"], textposition="top center", marker=dict(symbol="star", size=20, color="#FFD400", line=dict(color="#111", width=1.5)),
                                   hoverinfo="skip", showlegend=False))
    elif vessel == "ampoule":
        f.add_trace(go.Scatter(x=[float(d["x"].max() * xs) * 0.97], y=[ymax * 0.5], mode="markers+text", text=["growth (sink)"], textposition="middle left",
                               marker=dict(symbol="star", size=20, color="#FFD400", line=dict(color="#111", width=1.5)), hoverinfo="skip", showlegend=False))
        f.add_annotation(x=float(d["x"].min() * xs), y=ymax, text="source (hot)", showarrow=False, xanchor="left", yanchor="bottom", font=dict(size=11))
    else:  # flask: the fastest fluid, next to the stir bar
        s = np.nan_to_num(d["speed"])
        j, i = np.unravel_index(np.argmax(s), s.shape)
        f.add_trace(go.Scatter(x=[float(d["x"][i] * xs)], y=[float(d["y"][j] * ys)], mode="markers+text", text=["fastest flow"], textposition="top right",
                               marker=dict(symbol="star", size=20, color="#FFD400", line=dict(color="#111", width=1.5)), hoverinfo="skip", showlegend=False))
    f.update_layout(margin=dict(l=10, r=10, t=10, b=110))
    return f
