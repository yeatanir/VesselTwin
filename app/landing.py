"""Scrolling landing page: one story (recipe -> vessel -> next calculation). Pure CSS/SVG animation; detail sits behind info icons."""
import pathlib, re
import streamlit as st
from app.theme import info_html, go_to

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATUS_DOC = ROOT / "docs" / "status" / "status_final_oct21.md"
REPO = "https://github.com/yeatanir/VesselTwin"

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
    "thanks": "Literature search supported by Valency (free API credits) and Edison Scientific.",
    "proto": "Research prototype",
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


N = "#0B1F44"


def _grad(i, stops, vertical=False):
    d = 'x1="0" x2="0" y1="0" y2="1"' if vertical else 'x1="0" x2="1"'
    return f'<linearGradient id="{i}" {d}>' + "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops) + "</linearGradient>"


def _svg(inner, vb="0 0 200 110"):
    return f'<svg viewBox="{vb}" width="100%" style="display:block;max-height:130px" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">{inner}</svg>'


def icon(key):
    if key == "cvd_tube":
        return _svg(f'<defs>{_grad("ig1", [(0, "#BFD7F7"), (.5, "#F28C28"), (1, "#BFD7F7")])}</defs>'
                    '<ellipse class="vt-glow" cx="100" cy="55" rx="55" ry="26" fill="#F28C28" opacity=".35"/>'
                    f'<rect x="12" y="38" width="176" height="34" rx="17" fill="url(#ig1)" stroke="{N}" stroke-width="2.5"/>'
                    f'<rect x="78" y="58" width="14" height="8" rx="2" fill="{N}"/><rect x="108" y="58" width="14" height="8" rx="2" fill="{N}"/>'
                    '<path class="vt-dash" d="M20 50 C50 42 70 58 100 50 S150 42 180 50" stroke="#fff" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-dasharray="4 9"/>'
                    '<circle class="vt-pulse" cx="150" cy="62" r="3.5" fill="#fff" stroke="#1F5FBF" stroke-width="2"/>')
    if key == "ampoule":
        return _svg(f'<defs>{_grad("ig2", [(0, "#F6B26B"), (.5, "#DCE9FB"), (1, "#7FB0F0")])}</defs>'
                    f'<rect x="14" y="30" width="168" height="50" rx="25" fill="url(#ig2)" stroke="{N}" stroke-width="2.5"/>'
                    '<path d="M182 55 h10" stroke="#0B1F44" stroke-width="3" stroke-linecap="round"/>'
                    '<ellipse class="vt-glow" cx="34" cy="55" rx="16" ry="18" fill="#F28C28" opacity=".5"/>'
                    '<ellipse class="vt-glow" cx="164" cy="55" rx="14" ry="16" fill="#1F5FBF" opacity=".35"/>'
                    '<path class="vt-dash" d="M44 42 H152 C168 42 168 68 152 68 H44 C28 68 28 42 44 42Z" stroke="#1F5FBF" stroke-width="2.5" fill="none" stroke-dasharray="5 8" stroke-linecap="round"/>')
    if key == "flask":
        sw = "".join(f'<ellipse class="vt-dash" cx="100" cy="{64 + i * 9}" rx="{30 - i * 6}" ry="{6 - i}" fill="none" stroke="#1F5FBF" stroke-width="2.2" stroke-dasharray="7 6" style="animation-duration:{1 + i * .4}s"/>' for i in range(3))
        return _svg(f'<path d="M86 8 H114 V36 L152 88 Q158 100 144 100 H56 Q42 100 48 88 L86 36Z" fill="#E6F0FC" stroke="{N}" stroke-width="2.5"/>'
                    '<path d="M58 78 Q100 68 142 78 L150 92 Q152 98 144 98 H56 Q48 98 50 92Z" fill="#9CC3F5" opacity=".7"/>' + sw +
                    '<rect class="vt-spin" x="88" y="90" width="24" height="5" rx="2.5" fill="#0B1F44"/>')
    if key == "sorbent":
        beads = "".join(f'<circle cx="{74 + (i % 5) * 13 + (i // 5 % 2) * 6}" cy="{20 + (i // 5) * 13}" r="5.5" fill="#CFE2FA" stroke="#1F5FBF"/>' for i in range(30))
        return _svg('<defs><linearGradient id="ig4" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#F28C28" stop-opacity="0"/><stop offset=".5" stop-color="#F28C28" stop-opacity=".85"/><stop offset="1" stop-color="#F28C28" stop-opacity="0"/></linearGradient></defs>'
                    f'<rect x="64" y="8" width="82" height="94" rx="10" fill="#fff" stroke="{N}" stroke-width="2.5"/>{beads}'
                    '<rect class="vt-front" x="66" y="10" width="78" height="22" fill="url(#ig4)"/>'
                    '<path class="vt-dash" d="M30 55 H62 M148 55 H178" stroke="#1F5FBF" stroke-width="2.5" stroke-dasharray="3 6"/>')
    rays = "".join(f'<line class="vt-dash" x1="34" y1="{36 + i * 10}" x2="84" y2="{36 + i * 10}" stroke="#F28C28" stroke-width="2.5" stroke-dasharray="6 6" stroke-linecap="round" style="animation-delay:-{i * .25}s"/>' for i in range(4))
    return _svg('<defs><linearGradient id="ig5" x1="0" x2="1"><stop offset="0" stop-color="#F28C28" stop-opacity=".85"/><stop offset="1" stop-color="#F28C28" stop-opacity="0"/></linearGradient></defs>'
                f'<rect x="10" y="30" width="16" height="50" rx="5" fill="{N}"/><ellipse class="vt-glow" cx="22" cy="55" rx="22" ry="34" fill="#F28C28" opacity=".35"/>{rays}'
                f'<rect x="84" y="20" width="56" height="70" rx="8" fill="#EAF2FD" stroke="{N}" stroke-width="2.5"/>'
                '<rect class="vt-glow" x="86" y="22" width="52" height="66" rx="6" fill="url(#ig5)"/>'
                '<path d="M146 55 H190" stroke="#1F5FBF" stroke-width="2" stroke-dasharray="2 5" opacity=".5"/>')


def _flow(path, dur, delay, r=3.2, color="#1F5FBF"):
    return f'<circle class="vt-m" r="{r}" fill="{color}" style="offset-path:path(\'{path}\');animation-duration:{dur}s;animation-delay:-{delay}s"/>'


def hero_svg():
    recipe = ["MoO3  0.1 g", "S  0.5 g", "T  725 °C", "Ar  80 sccm", "20 min"]
    ins = [168 + i * 42 for i in range(5)]
    paths_in = [f"M255 {y} C320 {y} 330 250 395 {232 + i * 9}" for i, y in enumerate(ins)]
    paths_out = ["M830 250 C900 250 880 130 960 130", "M830 252 C900 252 880 380 960 380"]
    lines = "".join(f'<path d="{p}" class="vt-dash" stroke="#7FB0F0" stroke-width="1.6" fill="none" stroke-dasharray="3 8"/>' for p in paths_in + paths_out)
    parts = "".join(_flow(p, 4 + i % 3 * .6, i * .8) for i, p in enumerate(paths_in * 2)) + \
        "".join(_flow(p, 3.4, k * 1.1 + j * .5, 3.4, "#F28C28") for j, p in enumerate(paths_out) for k in range(3))
    rec = "".join(f'<rect x="38" y="{y - 14}" width="204" height="26" rx="13" fill="#EEF4FC"/><circle cx="54" cy="{y - 1}" r="4" fill="#1F5FBF"/>'
                  f'<text x="70" y="{y + 4}" font-size="15" fill="{N}" font-family="sans-serif">{t}</text>' for y, t in zip(ins, recipe))
    gas = "".join(f'<path class="vt-dash" d="M410 {232 + k * 18} C470 {212 + k * 18} 500 {262 + k * 6} 560 {240 + k * 18} S690 {222 + k * 18} 800 {240 + k * 18}" stroke="#fff" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-dasharray="5 12" style="animation-duration:{1.1 + k * .3}s" opacity=".9"/>' for k in range(3))
    swirl = "".join(f'<ellipse class="vt-spin" cx="{600 + k * 4}" cy="250" rx="{30 - k * 8}" ry="{12 - k * 3}" fill="none" stroke="#fff" stroke-width="2" opacity=".8" style="animation-duration:{2 + k}s"/>' for k in range(3))
    bars = "".join(f'<rect class="vt-bar" x="{985 + i * 38}" y="{190 - h}" width="24" height="{h}" rx="4" fill="{c}" style="animation-delay:{i * .3}s"/>' for i, (h, c) in enumerate([(100, "#1F5FBF"), (62, "#7FB0F0"), (40, "#BFD7F7"), (22, "#BFD7F7")]))
    lat = "".join(f'<circle class="vt-pulse" cx="{1000 + (i % 4) * 36}" cy="{338 + (i // 4) * 30}" r="7" fill="{"#F28C28" if i == 5 else "#1F5FBF"}" style="animation-delay:{i * .25}s;animation-duration:3s"/>' for i in range(12))
    latl = "".join(f'<line x1="{1000 + k * 36}" y1="338" x2="{1000 + k * 36}" y2="398" stroke="#BFD7F7" stroke-width="2"/>' for k in range(4)) + \
        "".join(f'<line x1="1000" y1="{338 + k * 30}" x2="1108" y2="{338 + k * 30}" stroke="#BFD7F7" stroke-width="2"/>' for k in range(3))
    return f'''<svg class="vt-hs" viewBox="0 0 1200 500" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Animated scene: a recipe flows into a tube furnace and out to two result cards">
<defs>{_grad("hg", [(0, "#CFE2FA"), (.3, "#7FB0F0"), (.55, "#F28C28"), (.8, "#7FB0F0"), (1, "#CFE2FA")])}
<radialGradient id="hf"><stop offset="0" stop-color="#F28C28" stop-opacity=".65"/><stop offset="1" stop-color="#F28C28" stop-opacity="0"/></radialGradient>
<filter id="sh" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#1F5FBF" flood-opacity=".18"/></filter></defs>
<g filter="url(#sh)"><rect x="20" y="95" width="240" height="310" rx="22" fill="#fff" stroke="#BCD3F2"/>
<rect x="940" y="30" width="230" height="200" rx="22" fill="#fff" stroke="#BCD3F2"/><rect x="940" y="270" width="230" height="200" rx="22" fill="#fff" stroke="#BCD3F2"/></g>
<text x="38" y="125" font-size="13" fill="#6B7A90" font-family="sans-serif" letter-spacing="1.5">RECIPE</text>{rec}
{lines}
<path class="vt-pulsel" d="M1055 232 C1030 245 1080 255 1055 268" stroke="#1F5FBF" stroke-width="3" fill="none"/>
<ellipse class="vt-glow" cx="600" cy="250" rx="270" ry="100" fill="url(#hf)"/>
<rect x="385" y="205" width="450" height="90" rx="45" fill="url(#hg)" stroke="{N}" stroke-width="3.5"/>
<rect x="500" y="190" width="200" height="120" rx="16" fill="none" stroke="#1F5FBF" stroke-width="2" stroke-dasharray="6 5" opacity=".55"/>
<rect x="470" y="268" width="36" height="14" rx="3" fill="{N}"/><rect x="540" y="268" width="36" height="14" rx="3" fill="{N}"/>
<rect x="690" y="276" width="90" height="8" rx="2" fill="{N}"/><circle class="vt-pulse" cx="735" cy="270" r="7" fill="#fff" stroke="#1F5FBF" stroke-width="3"/>
{gas}{swirl}
<text x="600" y="172" text-anchor="middle" font-size="15" fill="{N}" font-family="sans-serif" font-weight="600">725 °C</text>
<text x="430" y="330" text-anchor="middle" font-size="13" fill="#6B7A90" font-family="sans-serif">450 °C</text>
<text x="780" y="330" text-anchor="middle" font-size="13" fill="#6B7A90" font-family="sans-serif">620 °C</text>
<text x="958" y="62" font-size="13" fill="#6B7A90" font-family="sans-serif" letter-spacing="1.5">WHICH KNOB MATTERS</text>
<line x1="975" y1="190" x2="1150" y2="190" stroke="#BCD3F2" stroke-width="2"/>{bars}
<text x="958" y="302" font-size="13" fill="#6B7A90" font-family="sans-serif" letter-spacing="1.5">WHICH CALCULATION</text>{latl}{lat}
{parts}</svg>'''


def _person(color):
    return (f'<svg viewBox="0 0 80 80" width="72" height="72" aria-hidden="true"><circle cx="40" cy="26" r="14" fill="{color}"/>'
            f'<path d="M12 74 Q12 46 40 46 Q68 46 68 74Z" fill="{color}" opacity=".85"/></svg>')


def _flask_glyph():
    return '<svg viewBox="0 0 40 40" width="28" height="28" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 5h10M17 5v12L7 34h26L23 17V5"/></svg>'


def _atom_glyph():
    return '<svg viewBox="0 0 40 40" width="28" height="28" fill="none" stroke="#fff" stroke-width="2.5" aria-hidden="true"><circle cx="20" cy="20" r="3" fill="#fff"/><ellipse cx="20" cy="20" rx="16" ry="6"/><ellipse cx="20" cy="20" rx="16" ry="6" transform="rotate(60 20 20)"/><ellipse cx="20" cy="20" rx="16" ry="6" transform="rotate(120 20 20)"/></svg>'


def gap_html():
    C = COPY
    conn = ('<svg class="vt-conn" viewBox="0 0 600 120" preserveAspectRatio="none" aria-hidden="true">'
            '<path class="vt-draw" pathLength="1" d="M0 60 C120 10 200 110 300 60 S480 10 600 60" stroke="#1F5FBF" stroke-width="3" fill="none" stroke-linecap="round"/>'
            '<path class="vt-dash" d="M0 60 C120 10 200 110 300 60 S480 10 600 60" stroke="#fff" stroke-width="1.6" fill="none" stroke-dasharray="3 10"/></svg>')
    return (f'<div class="vt-gap vt-rv"><div class="vt-who a">{_person("#1F5FBF")}<div class="t">Experimentalist</div><div class="q">{C["gap.exp"]}</div></div>'
            f'<div class="vt-bridge">{conn}<div class="vt-node">{_flask_glyph()}<b>{C["gap.mid"]}</b>{_atom_glyph()}</div></div>'
            f'<div class="vt-who b">{_person("#0B1F44")}<div class="t">Simulation scientist</div><div class="q">{C["gap.sim"]}</div></div></div>')


STEP_ICONS = ["M8 4h12l8 8v24H8z M20 4v8h8 M12 20h12 M12 26h12", "M6 18h36v12H6z M12 18v12 M36 18v12 M24 8v10", "M6 38l12-14 8 8 14-20 M30 12h10v10"]


def how_html():
    C = COPY
    steps = "".join(
        f'<div class="vt-step vt-rv" style="animation-delay:{i * .15}s"><div class="vt-ic"><svg viewBox="0 0 48 48" width="40" height="40" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="{STEP_ICONS[i]}"/></svg></div>'
        f'<div class="n">{i + 1}</div><div class="t">{C[f"step.{i + 1}"]}</div></div>' for i in range(3))
    return f'<div class="vt-steps"><svg class="vt-sl" viewBox="0 0 100 4" preserveAspectRatio="none" aria-hidden="true"><line class="vt-dash" x1="0" y1="2" x2="100" y2="2" stroke="#1F5FBF" stroke-width="3" stroke-dasharray="4 4" vector-effect="non-scaling-stroke"/></svg>{steps}</div>'


def H(markup):
    """Raw HTML incl. inline SVG (st.html strips svg). Newlines removed so markdown cannot split the block."""
    st.markdown(markup.replace("\n", ""), unsafe_allow_html=True)


def _title(text, tip=None, cap=None):
    H(f'<div class="vt-sec vt-rv">{text}{info_html(tip) if tip else ""}</div>' + (f'<div class="vt-cap">{cap}</div>' if cap else ""))


LCSS = """
<style>
.vt-hero{position:relative;overflow:hidden;min-height:72vh;border-radius:28px;padding:2.2rem 1.6rem 4.2rem;text-align:center;
 background:linear-gradient(120deg,#fff,#E6F0FC,#CFE2FA,#EEF4FC,#fff);background-size:300% 300%;animation:vt-bg 18s ease-in-out infinite;box-shadow:0 10px 40px rgba(31,95,191,.14)}
@keyframes vt-bg{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
.vt-hero h1{position:relative;font-size:clamp(1.7rem,3.6vw,2.7rem);line-height:1.1;margin:0 0 .5rem;font-weight:800;
 background:linear-gradient(90deg,#0B1F44,#1F5FBF,#5B9BEA,#1F5FBF,#0B1F44);background-size:250% 100%;-webkit-background-clip:text;background-clip:text;color:transparent;animation:vt-txt 8s linear infinite}
@keyframes vt-txt{to{background-position:-250% 0}}
.vt-sub{position:relative;color:#3F516B;font-size:1.1rem;margin-bottom:1rem}
.vt-hs{position:relative;width:100%;height:auto;display:block}
.vt-fp{position:absolute;border-radius:50%;background:#7FB0F0;opacity:.25;animation:vt-up linear infinite}
@keyframes vt-up{from{transform:translateY(0)}to{transform:translateY(-110vh)}}
.vt-m{offset-rotate:0deg;animation:vt-mv linear infinite;opacity:.95}
@keyframes vt-mv{0%{offset-distance:0%;opacity:0}12%{opacity:1}88%{opacity:1}100%{offset-distance:100%;opacity:0}}
.vt-dash{animation:vt-dash 1s linear infinite}
@keyframes vt-dash{to{stroke-dashoffset:-26}}
.vt-glow{animation:vt-glow 3s ease-in-out infinite}
@keyframes vt-glow{0%,100%{opacity:.35}50%{opacity:.9}}
.vt-pulse{transform-box:fill-box;transform-origin:center;animation:vt-pulse 1.8s ease-in-out infinite}
@keyframes vt-pulse{0%,100%{opacity:.45;transform:scale(1)}50%{opacity:1;transform:scale(1.35)}}
.vt-pulsel{animation:vt-glow 2.4s ease-in-out infinite}
.vt-spin{transform-box:fill-box;transform-origin:center;animation:vt-spin 1.6s linear infinite}
@keyframes vt-spin{to{transform:rotate(360deg)}}
.vt-bar{transform-box:fill-box;transform-origin:bottom;animation:vt-bar 3.6s ease-in-out infinite alternate}
@keyframes vt-bar{from{transform:scaleY(.82)}to{transform:scaleY(1)}}
.vt-front{animation:vt-fr 3.6s ease-in-out infinite alternate}
@keyframes vt-fr{from{transform:translateY(0)}to{transform:translateY(68px)}}
/* scroll reveal: plain fade-in fallback, scroll-driven where supported */
.vt-rv{animation:vt-in .9s ease both}
@keyframes vt-in{from{opacity:0;transform:translateY(26px)}to{opacity:1;transform:none}}
.vt-draw{stroke-dasharray:1;stroke-dashoffset:1;animation:vt-dr 2.2s ease .3s forwards}
@keyframes vt-dr{to{stroke-dashoffset:0}}
@supports (animation-timeline:view()){
 .vt-rv{animation:vt-in linear both;animation-timeline:view();animation-range:entry 0% entry 55%}
 .vt-draw{animation:vt-dr linear both;animation-timeline:view();animation-range:entry 10% cover 45%}
}
.vt-sec{margin:3.6rem 0 .4rem;font-size:1.7rem;font-weight:800;color:var(--n);text-align:center}
.vt-cap{color:var(--g);margin-bottom:1rem}.vt-sec+.vt-cap{text-align:center}
.vt-gap{display:flex;align-items:center;justify-content:center;gap:0;margin:1.4rem 0}
.vt-who{flex:0 0 240px;background:#fff;border:1px solid #D6E3F5;border-radius:22px;padding:1.2rem;text-align:center;box-shadow:0 8px 24px rgba(31,95,191,.1)}
.vt-who .t{font-weight:700;color:var(--n);margin-top:.3rem}.vt-who .q{color:#1F5FBF;font-weight:600;margin-top:.3rem}
.vt-bridge{position:relative;flex:1 1 260px;height:130px;min-width:160px}
.vt-conn{position:absolute;inset:0;width:100%;height:100%}
.vt-node{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:flex;align-items:center;gap:.5rem;padding:.7rem 1.1rem;border-radius:999px;color:#fff;background:linear-gradient(120deg,#1F5FBF,#5B9BEA);animation:vt-halo 2.6s ease-in-out infinite;white-space:nowrap}
@keyframes vt-halo{0%,100%{box-shadow:0 0 0 0 rgba(91,155,234,.55)}50%{box-shadow:0 0 0 16px rgba(91,155,234,0)}}
.vt-steps{position:relative;display:flex;gap:1.2rem;justify-content:space-between;margin:1.6rem 0}
.vt-sl{position:absolute;left:8%;right:8%;top:36px;width:84%;height:4px}
.vt-step{position:relative;flex:1;text-align:center}
.vt-ic{width:72px;height:72px;margin:0 auto .5rem;border-radius:50%;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#1F5FBF,#5B9BEA);box-shadow:0 6px 18px rgba(31,95,191,.35)}
.vt-step .n{font-weight:800;color:#1F5FBF}.vt-step .t{color:var(--n);font-weight:600;max-width:200px;margin:0 auto}
[class*="st-key-vcard_"]{background:linear-gradient(180deg,#F4F8FE,#fff 55%)!important;overflow:hidden}
[class*="st-key-vcard_"]:hover svg{filter:drop-shadow(0 0 8px rgba(242,140,40,.45))}
.vt-chips{display:flex;flex-wrap:wrap;gap:.6rem;justify-content:center;margin:1rem 0}
.vt-chips .vt-chip{font-size:.95rem;padding:.3rem 1rem;animation:vt-halo 3s ease-in-out infinite}
.vt-chips .vt-chip:nth-child(2){animation-delay:-1s}.vt-chips .vt-chip:nth-child(3){animation-delay:-2s}
.vt-trust{text-align:center;color:var(--n);font-weight:600}
.vt-foot{text-align:center;color:var(--g);font-size:.9rem;margin-top:3rem;padding-top:1rem;border-top:1px solid #D6E3F5}
.st-key-try_ws{width:100%!important;display:flex;justify-content:center;margin-top:-4.2rem;position:relative;z-index:3}
.st-key-try_ws button{font-size:1.15rem;padding:.7rem 2.2rem;box-shadow:0 8px 24px rgba(31,95,191,.4);animation:vt-halo 2.6s ease-in-out infinite}
@media (max-width:760px){
 .vt-hero{padding:1.2rem .6rem 4rem;min-height:0}
 .vt-hs{width:230%;margin-left:-65%}
 .vt-gap{flex-direction:column}.vt-who{flex:none;width:100%}.vt-bridge{width:100%;flex:none;height:110px}
 .vt-steps{flex-direction:column;gap:1.6rem}.vt-sl{display:none}
}
@media (prefers-reduced-motion:reduce){.vt-hero,.vt-hero *,.vt-gap *,.vt-steps *,.vt-chips *,.vt-rv,.vt-draw,.st-key-hero button,[class*="st-key-vcard_"] *{animation:none!important}
 .vt-draw{stroke-dashoffset:0}.vt-m{display:none}}
</style>
"""


def render():
    C = COPY
    st.html(LCSS)  # st.html sanitises <svg> away; markdown keeps it, so content goes through H()
    with st.container(key="hero"):
        ps = "".join(f'<span class="vt-fp" style="left:{(i * 53) % 100}%;bottom:-{10 + i * 7 % 30}px;width:{4 + i % 4 * 3}px;height:{4 + i % 4 * 3}px;animation-duration:{14 + i * 3 % 11}s;animation-delay:-{i * 2.3:.1f}s"></span>' for i in range(14))
        H(f'<div class="vt-hero">{ps}<h1>{C["headline"]}</h1><div class="vt-sub">{C["sub"]}</div>{hero_svg()}</div>')
        if st.button(C["btn.try"], key="try_ws", type="primary"):
            go_to("Workspace")

    _title(C["gap.title"], INFO["gap"])
    H(gap_html())

    _title(C["how.title"], INFO["how"])
    H(how_html())

    _title(C["vessels.title"], INFO["vessels"], C["vessels.cap"])
    for row, widths in ((VESSELS[:3], [1, 1, 1]), (VESSELS[3:], [.5, 1, 1, .5])):
        cols = st.columns(widths)
        for col, (key, title, line, chip, cls) in zip(cols[1:-1] if len(widths) == 4 else cols, row):
            with col, st.container(key=f"vcard_{key}"):
                H(f'{icon(key)}<h4 style="margin:.4rem 0 .1rem;color:#0B1F44">{title}</h4><div class="vt-cap" style="margin-bottom:.4rem">{line}</div><span class="vt-chip {cls}">{chip}</span>')
                if st.button("Open", key=f"open_{key}"):
                    go_to("Workspace", vt_vessel=key)

    _title(C["trust.title"])
    H('<div class="vt-chips"><span class="vt-chip">benchmarked</span><span class="vt-chip grey">uncertain</span><span class="vt-chip warn">hypothesis</span></div>'
            f'<p class="vt-trust">{C["trust.line"]}{info_html(trust_facts())}</p>')
    link = f'<a href="{REPO}" target="_blank" rel="noopener">github.com/yeatanir/VesselTwin</a>'
    H(f'<div class="vt-foot">{C["footer"].replace("github.com/yeatanir/VesselTwin", link)}<br>{C["thanks"]}<br>{C["proto"]}</div>')
