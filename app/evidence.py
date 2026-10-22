"""Evidence page: reasoning trace, honest benchmark table, credibility harness. Offline, read-only.
Usage: from app.evidence import render; render()"""
import json, pathlib
import pandas as pd
import streamlit as st
from app.common import show_df

ROOT = pathlib.Path(__file__).resolve().parents[1]
# honest numbers copied from docs/status_oct21.md (the same facts app/trace_tab.py states); verdict: pass | miss | baseline
BENCH = [
    ("Sensitivity direction (tube, original items)", "model 2/8; blind no-tool 6/8; always-increase 4/8", 8, "miss"),
    ("Sensitivity direction, held-out (one paper)", "model 0/3; too small for any claim", 3, "miss"),
    ("Shape class (triangle vs hexagon)", "accuracy 0.50 = always-triangle baseline", 14, "baseline"),
    ("Tube regime call vs stored CFD", "37/40 = 92.5 % (CFD label is a chosen convention)", 40, "pass"),
    ("Ampoule regime call vs stored CFD", "81.7 % (f > 1.1) / 75.0 % (f > 1.2)", 60, "pass"),
    ("Surrogate error vs CFD (target 5 %)", "median error 24-36 % (tube), 27-31 % (ampoule)", 100, "miss"),
    ("Photoreactor vs actinometry (one paper)", "predicted/measured 0.88 collimated, 0.69 diffuse; inside tolerance", 2, "pass"),
    ("CALF-20 breakthrough time", "-3.3 %, +1.9 %, +9.8 %", 3, "pass"),
    ("13X breakthrough time", "38-39 % early; best fix missed its 15 % threshold by 0.6 points, not adopted", 2, "miss"),
    ("Literature quotes verified", "10 of 48", 48, "miss"),
]
GLYPH = {"pass": "● pass", "miss": "▲ missed", "baseline": "◆ baseline only"}


def info(text):
    try:
        from app.theme import info as theme_info
        return theme_info(text)
    except ImportError:
        with st.expander("ⓘ info"):
            st.caption(text)


def harness():
    for f in (ROOT / "cache" / "harness.json", ROOT / "docs" / "harness_snapshot.json"):
        if f.exists():
            return pd.DataFrame(json.loads(f.read_text())), f.name
    return None, None


def _trace():
    st.subheader("Reasoning trace")
    info("A replayable record of how a question was answered, tool call by tool call. Labels come only from llm/trace.py and never go up.")
    try:
        from app.trace_tab import render as render_trace
        render_trace(st)
    except Exception as e:
        st.error(f"Trace unavailable: {e}")


def _bench():
    st.subheader("Benchmarks")
    info("Numbers copied from docs/status_oct21.md. All MoS2 benchmark items are development data, so none of these is a blind test of the shipped model. Missed targets are shown as missed.")
    df = pd.DataFrame(BENCH, columns=["Check", "Result", "n", "Verdict"])
    df["Verdict"] = df["Verdict"].map(GLYPH)
    show_df(st, df, hide_index=True)


def _cred():
    st.subheader("Credibility checks")
    h, name = harness()
    if h is None:
        return st.warning("No harness file found; run `make test`. Nothing is shown as passing without a test.")
    n = int((h.outcome == "passed").sum())
    st.metric("Tests passing", f"{n} / {len(h)}", "all green" if n == len(h) else f"{len(h) - n} not passing", delta_color="off")
    info(f"Read from {name} (written by pytest). Re-run make test to refresh. A passing test checks the code against its stated limit; it is not a validation against experiment.")
    for col in ("vessel", "check"):  # partial runs write rows without tags
        h[col] = h[col].fillna("-") if col in h else "-"
    h["ok"] = h.outcome.map(lambda o: "PASS" if o == "passed" else "FAIL")
    show_df(st, h.pivot_table(index="vessel", columns="check", values="ok", aggfunc=lambda s: "FAIL" if "FAIL" in set(s) else f"PASS x{len(s)}", fill_value=""))
    with st.expander("All checks"):
        show_df(st, h[["vessel", "check", "test", "ok", "duration"]].sort_values(["ok", "vessel"], ascending=[False, True]), hide_index=True)


def render():
    st.title("Evidence")
    try:
        from app import llm_settings
        llm_settings.render()
    except Exception as e:  # noqa: BLE001
        st.caption(f"LLM settings unavailable: {e}")
    a, b, c, d = st.tabs(["Reasoning trace", "Benchmarks", "Credibility", "Literature"])
    with a:
        _trace()
    with b:
        _bench()
    with c:
        _cred()
    with d:
        from app import literature
        literature.render()
