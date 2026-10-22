"""Dashboard helpers: safe dataframes (C5), status badges (C4), generic `extras` plots (C4)."""
import altair as alt
import pandas as pd

BLUE, AMBER = "#0072B2", "#E69F00"


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Object columns holding more than one Python type (e.g. 1.0 and 'Ar') crash pyarrow: cast those columns to str."""
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object and len({type(x) for x in df[c].dropna()}) > 1:
            df[c] = df[c].map(lambda x: "" if x is None or x != x else str(x))
    return df


def show_df(st, df, **kw):
    kw.setdefault("width", "stretch")
    return st.dataframe(clean(df), **kw)


def status_badge(synthetic: bool, kind: str = "computed") -> str:
    """Every headline number carries one of: synthetic (placeholder inputs in play), sourced (all inputs sourced), computed by this tier."""
    return (f":orange[synthetic inputs] · {kind}" if synthetic else f":green[sourced inputs] · {kind}")


def _vals(a):
    return [float(v) if isinstance(v, (int, float)) else v for v in a["values"]]


def plot_chart(p: dict) -> alt.Chart:
    """p = {"title", "kind"?: "line"|"bar", "x": {"name","unit","values"}, "y": {...}, "band"?: {"p05": [...], "p95": [...]}}"""
    x, y = p["x"], p["y"]
    xl = f"{x['name']} [{x['unit']}]" if x.get("unit") else x["name"]
    yl = f"{y['name']} [{y['unit']}]" if y.get("unit") else y["name"]
    d = pd.DataFrame({"x": _vals(x), "y": _vals(y)})
    if p.get("kind") == "bar":
        return alt.Chart(d).mark_bar(color=BLUE).encode(x=alt.X("x:N", title=xl, sort=None), y=alt.Y("y:Q", title=yl)).properties(height=200, title=p["title"])
    ch = alt.Chart(d).mark_line(color=BLUE, strokeWidth=2, point=True).encode(x=alt.X("x:Q", title=xl), y=alt.Y("y:Q", title=yl))
    if p.get("band"):
        d["p05"], d["p95"] = p["band"]["p05"], p["band"]["p95"]
        ch = alt.Chart(d).mark_area(opacity=0.25, color=BLUE).encode(x="x:Q", y=alt.Y("p05:Q", title=yl), y2="p95:Q") + ch
    return ch.properties(height=200, title=p["title"])


def plots_from_extras(extras: dict) -> list[dict]:
    """Declared plots if present; otherwise a bar chart from a legacy `sensitivity` {knob: {dln_rate_per_sigma}} dict (photoreactor)."""
    if extras.get("plots"):
        return extras["plots"]
    found = []  # Track E format: extras[name] = {"x", "x_label", "x_unit", "y_label", "y_unit", "p05", "p50", "p95"}
    for k, v in extras.items():
        if isinstance(v, dict) and isinstance(v.get("x"), list) and isinstance(v.get("p50"), list) and len(v["x"]) == len(v["p50"]):
            found.append({"title": k.replace("_", " "), "x": {"name": v.get("x_label", "x"), "unit": v.get("x_unit", ""), "values": v["x"]},
                          "y": {"name": v.get("y_label", "y"), "unit": v.get("y_unit", ""), "values": v["p50"]},
                          **({"band": {"p05": v["p05"], "p95": v["p95"]}} if v.get("p05") and v.get("p95") else {})})
    if found:
        return found
    s = extras.get("sensitivity")
    if isinstance(s, dict) and s and all(isinstance(v, dict) and "dln_rate_per_sigma" in v for v in s.values()):
        return [{"title": "Rate sensitivity per 1-sigma move of each input", "kind": "bar", "x": {"name": "input", "unit": "", "values": list(s)},
                 "y": {"name": "dln(rate) per sigma", "unit": "", "values": [v["dln_rate_per_sigma"] for v in s.values()]}}]
    return []


def render_extras(st, r: dict):
    """Draw whatever plots a vessel result declares in `extras` (schema in docs/handoff/requests-c.md)."""
    ex = r.get("extras") or {}
    ps = plots_from_extras(ex)
    for p in ps:
        st.altair_chart(plot_chart(p), width="stretch")
    for n in ex.get("notes") or []:
        st.caption(str(n))
    if ps:
        st.caption(status_badge(r["passport"]["synthetic"]) + (" · " + ex["text"] if ex.get("text") else ""))
    return len(ps)
