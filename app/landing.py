"""Scrolling landing page: hero, the gap, how it works, the five vessels, trust strip. Little prose; detail sits behind info icons."""
import json, pathlib, re
import streamlit as st
from app.theme import info_html, go_to

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATUS_DOC = ROOT / "docs" / "status" / "status_final_oct21.md"

# every on-screen caption lives here so tests can check the word limits (headline <= 10, captions <= 14)
COPY = {
    "headline": "From recipe to vessel to the next calculation",
    "sub": "Model your reactor, see what matters, know what to compute.",
    "btn.try": "Try the workspace",
    "gap.title": "Two people, one missing link",
    "gap.exp": "Which variable matters?",
    "gap.sim": "Which calculation matters?",
    "gap.mid": "VesselTwin",
    "how.title": "How it works",
    "step.1": "Read the procedure", "step.2": "Model the vessel", "step.3": "Say what matters and what to calculate",
    "vessels.title": "Five vessels",
    "vessels.cap": "Pick one to open it in the workspace.",
    "trust.title": "Honest by design",
    "trust.line": "Our own tests are published, including the ones we fail.",
    "footer": "VesselTwin · Anirban Phukan · MIT License · github.com/yeatanir/VesselTwin",
}
INFO = {
    "gap": "Experimentalists tune furnace, flow and geometry. Simulation scientists choose which atomistic calculation to run. VesselTwin links the two with a vessel-scale model and a ranked list of uncertainties.",
    "how": "Procedure text is parsed into parameters. Each carries a unit, a source and a stated, default or missing flag. Tier 0 gives a regime map, Tier 1 a reduced model with Monte Carlo bands, Tier 2 stored CFD.",
    "vessels": "Status chips come from tiers.json and the status report. A chip is never stronger than the evidence behind it.",
}
# (key, title, one line, chip text, chip class). Chips follow tiers.json / docs/status/status_final_oct21.md.
VESSELS = [
    ("cvd_tube", "MoS2 CVD tube", "Boats, hot zones and carrier gas in a furnace.", "growth not validated", "warn"),
    ("ampoule", "Sealed ampoule", "Vapour transport along a temperature gradient.", "CFD-checked (diffusion limit)", ""),
    ("flask", "Stirred flask", "Mixing, power number and reaction selectivity.", "CFD-checked, power number off", "warn"),
    ("sorbent", "Sorbent bed", "Gas breakthrough through a packed column.", "validated vs published breakthrough", ""),
    ("photoreactor", "Photoreactor", "Lamp light, absorption and photochemical rate.", "checked vs actinometry", ""),
]


def trust_facts():
    """Numbers shown behind the trust info icon, read from the status report; falls back to wording without numbers."""
    try:
        t = STATUS_DOC.read_text()
        lo, hi = re.search(r"(\d/9) to (\d/9)", t).groups()
        agent = re.search(r"blind no-tool agent's (\d/9)", t).group(1)
        shape = re.search(r"\(0\.50, the same as always answering triangle\)", t) and "0.50, equal to always answering triangle"
        return (f"Sensitivity direction: model {lo} to {hi} against a blind agent's {agent}. "
                f"Shape class: {shape or 'no better than baseline'}. "
                "CFD verification targets (mesh, regime, surrogate): mostly missed.")
    except Exception:
        return "Sensitivity direction and shape class do not beat simple baselines; CFD verification targets were mostly missed."


def _svg(inner, vb="0 0 120 70"):
    return f'<svg viewBox="{vb}" width="100%" style="max-height:90px" xmlns="http://www.w3.org/2000/svg">{inner}</svg>'


def _dots(y, n, x0, span, r=2, color="#1F5FBF"):
    return "".join(f'<circle class="vt-p" cx="{x0}" cy="{y + (i % 3 - 1) * 5}" r="{r}" fill="{color}" style="--d:{span}px;animation-duration:{3 + i % 3}s;animation-delay:-{i * 0.9:.1f}s"/>' for i in range(n))


def icon(key):
    grad = '<defs><linearGradient id="g{0}" x1="0" x2="1"><stop offset="0" stop-color="#9CC3F5"/><stop offset=".5" stop-color="#F28C28"/><stop offset="1" stop-color="#9CC3F5"/></linearGradient></defs>'.format(key)
    if key == "cvd_tube":
        return _svg(grad + f'<rect x="6" y="22" width="108" height="26" rx="13" fill="url(#g{key})" stroke="#0B1F44" stroke-width="2"/><rect x="40" y="38" width="10" height="6" fill="#0B1F44"/><rect x="66" y="38" width="10" height="6" fill="#0B1F44"/>' + _dots(35, 5, 12, 90, 1.8, "#0B1F44"))
    if key == "ampoule":
        return _svg(grad + f'<path d="M8 35 Q8 20 24 20 H96 Q112 20 112 35 Q112 50 96 50 H24 Q8 50 8 35Z" fill="url(#g{key})" stroke="#0B1F44" stroke-width="2"/><path d="M112 35 h6" stroke="#0B1F44" stroke-width="2"/>' + _dots(35, 4, 18, 80, 2, "#fff"))
    if key == "flask":
        return _svg('<path d="M48 8 H72 V26 L100 56 Q104 64 94 64 H26 Q16 64 20 56 L48 26Z" fill="#D6E6FA" stroke="#0B1F44" stroke-width="2"/><rect class="vt-spin" x="48" y="54" width="24" height="5" rx="2.5" fill="#1F5FBF"/><circle class="vt-pulse" cx="60" cy="40" r="3" fill="#F28C28"/>')
    if key == "sorbent":
        beads = "".join(f'<circle cx="{34 + (i % 6) * 10}" cy="{18 + (i // 6) * 10}" r="3.5" fill="#9CC3F5" stroke="#1F5FBF"/>' for i in range(24))
        return _svg(f'<rect x="26" y="10" width="68" height="50" rx="6" fill="#fff" stroke="#0B1F44" stroke-width="2"/>{beads}<rect class="vt-front" x="28" y="30" width="64" height="6" rx="3" fill="#F28C28" opacity=".7"/>')
    rays = "".join(f'<line class="vt-glow" x1="60" y1="35" x2="{60 + 44 * c:.0f}" y2="{35 + 44 * s:.0f}" stroke="#F28C28" stroke-width="2" style="animation-delay:-{i * .4}s"/>' for i, (c, s) in enumerate([(1, 0), (.7, .7), (0, 1), (-.7, .7), (-1, 0), (-.7, -.7), (0, -1), (.7, -.7)]))
    return _svg(f'{rays}<rect x="38" y="13" width="44" height="44" rx="8" fill="#EEF4FC" stroke="#0B1F44" stroke-width="2"/><rect x="56" y="18" width="8" height="34" rx="4" fill="#F28C28" class="vt-glow"/>')


def hero_svg():
    tube = ('<defs><linearGradient id="hg" x1="0" x2="1"><stop offset="0" stop-color="#9CC3F5"/><stop offset=".25" stop-color="#5B9BEA"/>'
            '<stop offset=".55" stop-color="#F28C28"/><stop offset=".85" stop-color="#5B9BEA"/><stop offset="1" stop-color="#9CC3F5"/></linearGradient>'
            '<radialGradient id="hf"><stop offset="0" stop-color="#F28C28" stop-opacity=".6"/><stop offset="1" stop-color="#F28C28" stop-opacity="0"/></radialGradient></defs>'
            '<ellipse class="vt-glow" cx="500" cy="130" rx="230" ry="75" fill="url(#hf)"/>'
            '<rect x="40" y="95" width="820" height="70" rx="35" fill="url(#hg)" stroke="#0B1F44" stroke-width="3"/>'
            '<rect x="330" y="82" width="320" height="96" rx="14" fill="none" stroke="#1F5FBF" stroke-width="2" stroke-dasharray="6 5" opacity=".5"/>'
            '<rect x="180" y="140" width="46" height="14" rx="3" fill="#0B1F44"/><rect x="262" y="140" width="46" height="14" rx="3" fill="#0B1F44"/>'
            '<rect x="660" y="146" width="90" height="8" rx="2" fill="#0B1F44"/>'
            '<circle class="vt-pulse" cx="705" cy="142" r="7" fill="#fff" stroke="#1F5FBF" stroke-width="3"/>'
            '<text x="705" y="196" text-anchor="middle" font-size="14" fill="#0B1F44" font-family="sans-serif">substrate</text>'
            '<path d="M10 130 H55" class="vt-flowline" stroke="#1F5FBF" stroke-width="3" fill="none"/>')
    dots = "".join(f'<circle class="vt-p" cx="70" cy="{112 + (i * 17) % 50}" r="{2.5 + i % 2}" fill="#fff" style="--d:{700 + (i % 3) * 40}px;animation-duration:{4 + i % 4}s;animation-delay:-{i * .7:.1f}s"/>' for i in range(14))
    return f'<svg viewBox="0 0 900 230" width="100%" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Animated CVD tube">{tube}{dots}</svg>'


def _title(text, tip=None, cap=None):
    st.html(f'<div class="vt-sec">{text}{info_html(tip) if tip else ""}</div>' + (f'<div class="vt-cap">{cap}</div>' if cap else ""))


def render():
    C = COPY
    with st.container(key="hero"):
        st.html(f'<div class="vt-hero"><h1>{C["headline"]}</h1><div class="vt-sub">{C["sub"]}</div>{hero_svg()}</div>')
        if st.button(C["btn.try"], key="try_ws", type="primary"):
            go_to("Workspace")

    _title(C["gap.title"], INFO["gap"])
    a, mid, b = st.columns([5, 3, 5], vertical_alignment="center")
    a.html(f'<div class="vt-card"><h4>Experimentalist</h4><div class="vt-cap">{C["gap.exp"]}</div></div>')
    b.html(f'<div class="vt-card"><h4>Simulation scientist</h4><div class="vt-cap">{C["gap.sim"]}</div></div>')
    mid.html('<svg viewBox="0 0 220 90" width="100%"><line class="vt-flowline" x1="0" y1="45" x2="220" y2="45" stroke="#1F5FBF" stroke-width="3"/>'
             f'<rect x="30" y="20" width="160" height="50" rx="25" fill="#1F5FBF"/><text x="110" y="52" text-anchor="middle" fill="#fff" font-size="18" font-weight="700" font-family="sans-serif">{C["gap.mid"]}</text></svg>')

    _title(C["how.title"], INFO["how"])
    icons = ["M8 4h12l8 8v24H8z M20 4v8h8 M12 20h12 M12 26h12", "M6 18h36v12H6z M12 18v12 M36 18v12 M24 8v10", "M6 38l12-14 8 8 14-20 M30 12h10v10"]
    for col, i in zip(st.columns(3), range(3)):
        col.html(f'<div class="vt-card" style="text-align:center"><svg viewBox="0 0 48 48" width="48" height="48" fill="none" stroke="#1F5FBF" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="{icons[i]}"/></svg>'
                 f'<h4>{i + 1}. {C[f"step.{i + 1}"]}</h4></div>')

    _title(C["vessels.title"], INFO["vessels"], C["vessels.cap"])
    for row in (VESSELS[:3], VESSELS[3:]):
        for col, (key, title, line, chip, cls) in zip(st.columns(3), row):
            with col, st.container(key=f"vcard_{key}"):
                st.html(f'{icon(key)}<h4 style="margin:.4rem 0 .1rem;color:#0B1F44">{title}</h4><div class="vt-cap" style="margin-bottom:.4rem">{line}</div><span class="vt-chip {cls}">{chip}</span>')
                if st.button("Open", key=f"open_{key}"):
                    go_to("Workspace", vt_vessel=key)

    _title(C["trust.title"])
    st.html('<span class="vt-chip">benchmarked</span> <span class="vt-chip grey">uncertain</span> <span class="vt-chip warn">hypothesis</span>'
            f'<p style="margin-top:.8rem;color:#0B1F44;font-weight:600">{C["trust.line"]}{info_html(trust_facts())}</p>')
    st.html(f'<hr style="border:0;border-top:1px solid #D6E3F5;margin:2.5rem 0 .6rem"><div class="vt-cap">{C["footer"].replace("github.com/yeatanir/VesselTwin", '<a href="https://github.com/yeatanir/VesselTwin" target="_blank" rel="noopener">github.com/yeatanir/VesselTwin</a>')}<br>Research prototype</div>')
