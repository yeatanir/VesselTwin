"""Small visual helpers shared by the Home page: cards, badges, big-number tiles, stepper, status dots.
Pure functions returning HTML strings (render with st.markdown(..., unsafe_allow_html=True)).
Theme-safe: text inherits the theme colour; fills are translucent so they read on light and dark backgrounds.
Palette: Okabe-Ito (colour-blind safe). Every status also has its own glyph, so colour is never the only cue."""
import html

BLUE, ORANGE, VERM, SKY, GREEN, PINK, GREY = "#0072B2", "#E69F00", "#D55E00", "#56B4E9", "#009E73", "#CC79A7", "#8a8f98"

# number status: model output / CFD result / synthetic inputs
STATUS = {"model": (BLUE, "●", "Model estimate"), "cfd": (GREEN, "▲", "CFD result"), "synthetic": (ORANGE, "◆", "Synthetic inputs")}
# extraction status chips
CHIP = {"stated": (BLUE, "✓", "stated"), "default": (ORANGE, "~", "default"), "missing": (PINK, "?", "missing")}
COST = {"cheap": (GREEN, "$"), "medium": (ORANGE, "$$"), "expensive": (VERM, "$$$")}

CSS = f"""<style>
.vt-wrap{{--b:{BLUE};--o:{ORANGE};--v:{VERM};--g:{GREEN};--p:{PINK};}}
.block-container{{padding-top:2.2rem!important}}
.vt-head{{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:.5rem;margin:0 0 .2rem 0}}
.vt-name{{font-size:2rem;font-weight:800;line-height:1.1}}
.vt-pitch{{font-size:1.05rem;opacity:.85}}
.vt-badge{{display:inline-block;border:1.5px solid var(--c);color:var(--c);border-radius:999px;padding:.1em .7em;font-size:.8rem;font-weight:600;white-space:nowrap}}
.vt-steps{{display:flex;gap:.3rem;margin:.4rem 0 .6rem 0}}
.vt-step{{flex:1;text-align:center;border-bottom:4px solid rgba(128,128,128,.35);padding:.25rem .1rem;font-size:.85rem;opacity:.65}}
.vt-step.done{{border-color:{SKY};opacity:.9}}
.vt-step.now{{border-color:{BLUE};opacity:1;font-weight:700}}
.vt-card{{border:2px solid rgba(128,128,128,.35);border-radius:14px;padding:.6rem .8rem;background:rgba(128,128,128,.07);min-height:5.5rem}}
.vt-card.sel{{border-color:{BLUE};background:rgba(0,114,178,.13)}}
.vt-card h4{{margin:.2rem 0 .1rem 0;font-size:1.05rem}}
.vt-cap{{font-size:.85rem;opacity:.75}}
.vt-tiles{{display:flex;flex-wrap:wrap;gap:.7rem}}
.vt-tile{{flex:1 1 9rem;border:2px solid rgba(128,128,128,.35);border-radius:14px;padding:.6rem .9rem;background:rgba(128,128,128,.07)}}
.vt-tile .n{{font-size:2.3rem;font-weight:800;line-height:1.1}}
.vt-tile .u{{font-size:1rem;font-weight:600;opacity:.8;margin-left:.25rem}}
.vt-tile .l{{font-size:.9rem;opacity:.8}}
.vt-chip{{display:inline-block;border:1.5px solid var(--c);background:color-mix(in srgb,var(--c) 18%,transparent);border-radius:8px;padding:0 .4em;margin:.1em .15em;font-weight:600}}
.vt-chip small{{opacity:.75;font-weight:500}}
.vt-text{{max-height:9.5rem;overflow:auto;line-height:1.9;font-size:.95rem;border:1px solid rgba(128,128,128,.3);border-radius:10px;padding:.4rem .6rem}}
.vt-meter{{display:flex;height:2.2rem;border-radius:10px;overflow:hidden;border:1px solid rgba(128,128,128,.4)}}
.vt-meter div{{display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;font-size:.9rem;min-width:2.2rem}}
.vt-rank{{display:flex;align-items:center;justify-content:center;width:2.4rem;height:2.4rem;border-radius:50%;background:{BLUE};color:#fff;font-weight:800;font-size:1.2rem}}
.vt-take{{font-size:1.25rem;font-weight:700;margin:.3rem 0}}
div[data-testid="stButton"] button{{min-height:2.8rem;font-size:1rem}}
</style>"""


def e(s):
    return html.escape(str(s))


def badge(text, color=ORANGE, glyph=""):
    return f'<span class="vt-badge" style="--c:{color}">{glyph} {e(text)}</span>'


def dot(kind):
    c, g, name = STATUS[kind]
    return f'<span title="{name}" style="color:{c}">{g}</span>'


def status_legend():
    return " &nbsp; ".join(f'<span style="color:{c}">{g}</span> {n}' for c, g, n in STATUS.values())


def chip(text, kind, sub=""):
    c, g, _ = CHIP[kind]
    return f'<span class="vt-chip" style="--c:{c}">{g} {e(text)}' + (f' <small>{e(sub)}</small>' if sub else "") + "</span>"


def chip_legend():
    return " ".join(f'<span class="vt-chip" style="--c:{c}">{g} {n}</span>' for c, g, n in CHIP.values())


def tile(label, value, unit, kind="model"):
    return (f'<div class="vt-tile"><div class="l">{dot(kind)} {e(label)}</div>'
            f'<div><span class="n">{e(value)}</span><span class="u">{e(unit)}</span></div></div>')


def tiles(items):
    return '<div class="vt-tiles">' + "".join(tile(*i) for i in items) + "</div>"


def card(title, body="", selected=False, icon=""):
    return f'<div class="vt-card{" sel" if selected else ""}">{icon}<h4>{e(title)}</h4><div class="vt-cap">{e(body)}</div></div>'


def stepper(steps, now):
    return '<div class="vt-steps">' + "".join(
        f'<div class="vt-step{" now" if i == now else " done" if i < now else ""}">{i + 1}. {e(s)}</div>' for i, s in enumerate(steps)) + "</div>"


def meter(parts):
    """parts = [(label, count, color)]; segment widths proportional (min width keeps zeros visible)."""
    tot = sum(p[1] for p in parts) or 1
    return '<div class="vt-meter">' + "".join(
        f'<div style="background:{c};flex:{max(n, 0.01) / tot}" title="{e(l)}: {n}">{n}</div>' for l, n, c in parts) + "</div>"


def rank_dot(n):
    return f'<div class="vt-rank">{n}</div>'


def icon(kind):
    """Tiny inline SVG schematics (currentColor strokes so they follow the theme)."""
    s = 'width="84" height="40" viewBox="0 0 84 40" fill="none" stroke="currentColor" stroke-width="2"'
    if kind == "cvd_tube":
        return (f'<svg {s}><rect x="2" y="12" width="80" height="16" rx="8"/><rect x="26" y="8" width="32" height="24" rx="3" stroke="{ORANGE}"/>'
                f'<path d="M8 20h12M64 20h14" stroke="{SKY}"/><path d="M74 16l4 4-4 4" stroke="{SKY}"/></svg>')
    if kind == "ampoule":
        return (f'<svg {s}><path d="M6 14h56a14 6 0 0 1 0 12H6a2 6 0 0 1 0-12z"/><path d="M62 14c8 0 14 3 14 6s-6 6-14 6" /><circle cx="14" cy="20" r="3" stroke="{VERM}"/><circle cx="52" cy="20" r="3" stroke="{BLUE}"/></svg>')
    return (f'<svg {s}><rect x="26" y="2" width="32" height="36" rx="4"/><path d="M26 12h32M26 22h32M26 32h32" stroke="{GREEN}"/><path d="M42 0v2M42 38v2" stroke="{SKY}"/></svg>')


# ---------------------------------------------------------------- Workspace (blue/white) kit. All classes prefixed wk- to stay clear of theme.py / CSS above.
WB, WN, WO, WG = "#1F5FBF", "#0B1F44", "#F28C28", "#6B7A90"
WS_CSS = """<style>
.stMainBlockContainer{padding-top:2.4rem!important}
/* vessel picker: card = animated icon + invisible full-card button */
.st-key-vpick [data-testid=stHorizontalBlock]{flex-wrap:nowrap!important;overflow-x:auto;gap:.7rem;padding:8px 8px 12px}
.st-key-vpick [data-testid=stColumn]{min-width:150px!important;flex:1 0 150px!important}
[class*="st-key-vp_"]{position:relative;background:linear-gradient(180deg,#F4F8FE,#fff 60%);border:1.5px solid #D6E3F5;border-radius:18px;padding:.5rem .6rem .7rem;transition:transform .2s,box-shadow .2s,border-color .2s;overflow:hidden}
[class*="st-key-vp_"]:hover{transform:translateY(-3px);box-shadow:0 12px 26px rgba(31,95,191,.18);border-color:#1F5FBF}
[class*="st-key-vp_"]:focus-within{outline:3px solid #F28C28;outline-offset:2px}
[class*="st-key-vp_"][class*="__sel"]{border-color:#1F5FBF;box-shadow:0 0 0 3px rgba(31,95,191,.22),0 12px 28px rgba(31,95,191,.25);background:linear-gradient(180deg,#E6F0FC,#fff 70%)}
[class*="st-key-vp_"] [data-testid=stElementContainer]:has(button){position:absolute;inset:0;z-index:2;margin:0}
[class*="st-key-vp_"] button{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer}
[class*="st-key-vp_"] [data-testid=stVerticalBlock]{gap:0}
.wk-vc{text-align:center}.wk-vc svg{max-height:74px;width:100%}
.wk-vc .t{font-weight:700;color:#0B1F44;font-size:.92rem;margin-top:.25rem}
.wk-vc .s{height:3px;border-radius:3px;margin:.35rem auto 0;width:0;background:#1F5FBF;transition:width .25s}
[class*="__sel"] .wk-vc .s{width:46%}
/* cards */
.wk-card{background:#fff;border:1px solid #D6E3F5;border-radius:18px;padding:.9rem 1.1rem;box-shadow:0 2px 10px rgba(11,31,68,.06)}
.wk-h{font-size:.74rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:#6B7A90;margin:0 0 .3rem}
.wk-badge{display:inline-flex;align-items:center;gap:.3rem;border-radius:999px;padding:.12rem .65rem;font-size:.76rem;font-weight:600;background:#EEF4FC;color:#1F5FBF;border:1px solid #BCD3F2;white-space:nowrap}
.wk-badge.o{background:#FFF3E5;color:#B35F00;border-color:#F6D3A8}.wk-badge.g{background:#F1F3F6;color:#4B5A70;border-color:#D8DEE8}
.wk-chip{display:inline-block;border-radius:10px;padding:.1rem .55rem;margin:.12rem .15rem;font-size:.82rem;font-weight:600;border:1px solid}
.wk-chip small{font-weight:500;opacity:.75}
.wk-chip.stated{background:#E6F0FC;color:#1F5FBF;border-color:#9CC3F5}.wk-chip.default{background:#FFF3E5;color:#B35F00;border-color:#F6D3A8}.wk-chip.missing{background:#F1F3F6;color:#6B7A90;border-color:#D8DEE8}
/* tier strip */
.wk-tiers{display:flex;align-items:stretch;gap:.35rem}
.wk-tier{flex:1;border:1.5px solid #D6E3F5;border-radius:12px;padding:.4rem .7rem;background:#fff;color:#6B7A90;font-size:.84rem;line-height:1.25}
.wk-tier b{display:block;color:inherit;font-size:.9rem}
.wk-tier.on{border-color:#1F5FBF;background:linear-gradient(135deg,#1F5FBF,#5B9BEA);color:#fff;box-shadow:0 6px 16px rgba(31,95,191,.3)}
.wk-arrow{align-self:center;color:#9CC3F5;font-weight:700}
.wk-def{color:#3F516B;font-size:.92rem;margin:.45rem 0 .6rem;line-height:2}
/* KPI */
.wk-kpis{display:flex;flex-direction:column;gap:.7rem}
.wk-kpi{background:#fff;border:1px solid #D6E3F5;border-left:5px solid #1F5FBF;border-radius:16px;padding:.7rem 1rem;box-shadow:0 2px 10px rgba(11,31,68,.06)}
.wk-kpi .l{font-size:.8rem;color:#6B7A90;font-weight:600}
.wk-kpi .n{font-size:2.25rem;font-weight:800;color:#0B1F44;line-height:1.1}
.wk-kpi .u{font-size:.95rem;font-weight:600;color:#6B7A90;margin-left:.3rem}
.wk-kpi .d{font-size:.78rem;font-weight:600;color:#6B7A90}.wk-kpi .d.up{color:#1F5FBF}.wk-kpi .d.dn{color:#B35F00}
.wk-dot{display:inline-block;width:.6rem;height:.6rem;border-radius:50%;margin-right:.35rem;vertical-align:middle}
/* knobs */
[class*="st-key-kn_"]{background:#fff;border:1px solid #D6E3F5;border-radius:16px;padding:.65rem .9rem .85rem;box-shadow:0 2px 8px rgba(11,31,68,.05)}
[class*="st-key-kn_"] [data-testid=stVerticalBlock]{gap:.1rem}
[class*="st-key-kn_"] [data-testid=stHorizontalBlock]{flex-wrap:nowrap!important;align-items:center}
[class*="st-key-kn_"] [data-testid=stColumn]{min-width:0!important}
.wk-kh{display:flex;align-items:center;gap:.5rem;font-weight:600;color:#0B1F44;font-size:.92rem}
.wk-kh svg{flex:none}.wk-kh .v{margin-left:auto;background:#EEF4FC;color:#1F5FBF;border:1px solid #BCD3F2;border-radius:999px;padding:.05rem .65rem;font-weight:700;font-size:.85rem;white-space:nowrap}
.wk-ef{display:flex;align-items:center;gap:.5rem;font-size:.72rem;color:#6B7A90;margin-top:-.1rem}
.wk-ef .bar{flex:1;height:5px;border-radius:5px;background:#EEF4FC;overflow:hidden}.wk-ef .bar i{display:block;height:100%;border-radius:5px}
[class*="st-key-kn_"] [data-testid=stSliderThumbValue]{display:none}
[class*="st-key-kn_"] [data-baseweb=slider] [role=slider]{width:20px;height:20px;box-shadow:0 2px 8px rgba(31,95,191,.45)}
[class*="st-key-kn_"] [data-testid=stSliderTickBarMin],[class*="st-key-kn_"] [data-testid=stSliderTickBarMax]{font-size:.7rem;color:#6B7A90}
[class*="st-key-kn_"] [data-testid=stSlider]{padding-bottom:0}
[class*="st-key-rs_"] button{width:22px;height:22px;min-height:22px;padding:0;border-radius:50%;background:#FFF3E5;border:1.5px solid #F28C28;color:#B35F00;font-size:.7rem;line-height:1}
[class*="st-key-rs_"] button:hover{background:#F28C28;color:#fff}
/* ranked cards, meter */
.wk-rank{display:flex;gap:.7rem;align-items:flex-start;height:100%}
.wk-rank .r{flex:none;width:2.1rem;height:2.1rem;border-radius:50%;background:linear-gradient(135deg,#1F5FBF,#5B9BEA);color:#fff;font-weight:800;display:flex;align-items:center;justify-content:center}
.wk-rank .t{font-weight:700;color:#0B1F44}.wk-rank .s{font-size:.86rem;color:#3F516B;margin:.15rem 0 .35rem}
.wk-meter{display:flex;height:1.9rem;border-radius:999px;overflow:hidden}.wk-meter div{display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:.82rem;min-width:1.9rem}
/* LLM strip */
.wk-llm{display:flex;align-items:center;gap:.35rem}.wk-llm .st{flex:1;text-align:center;font-size:.78rem;color:#0B1F44;line-height:1.25}
.wk-llm .ic{width:42px;height:42px;margin:0 auto .25rem;border-radius:50%;background:linear-gradient(135deg,#1F5FBF,#5B9BEA);display:flex;align-items:center;justify-content:center;box-shadow:0 4px 12px rgba(31,95,191,.3)}
.wk-llm .st b{display:block;font-size:.82rem}
.st-key-wk_paste{background:#fff;border:1px solid #BCD3F2;border-radius:18px;padding:.9rem 1.1rem;box-shadow:0 4px 18px rgba(31,95,191,.1)}
.st-key-wk_paste textarea{border-radius:12px;font-size:.9rem}
/* animations scoped to the picker (own keyframes; the landing page redefines the shared ones) */
.wk-vc .vt-dash{animation:wkd 1s linear infinite}.wk-vc .vt-glow{animation:wkg 3s ease-in-out infinite}
.wk-vc .vt-pulse{transform-box:fill-box;transform-origin:center;animation:wkp 1.8s ease-in-out infinite}
.wk-vc .vt-spin{transform-box:fill-box;transform-origin:center;animation:wks 1.6s linear infinite}
.wk-vc .vt-front{animation:wkf 3.6s ease-in-out infinite alternate}
@keyframes wkd{to{stroke-dashoffset:-26}}@keyframes wkg{0%,100%{opacity:.35}50%{opacity:.9}}
@keyframes wkp{0%,100%{opacity:.45;transform:scale(1)}50%{opacity:1;transform:scale(1.35)}}@keyframes wks{to{transform:rotate(360deg)}}
@keyframes wkf{from{transform:translateY(0)}to{transform:translateY(68px)}}
@media (prefers-reduced-motion:reduce){.wk-vc *{animation:none!important}}
@media (max-width:640px){.wk-tier{padding:.3rem .4rem;font-size:.72rem}.wk-tier b{font-size:.78rem}.wk-kpis{flex-direction:row}.wk-kpi{flex:1;padding:.5rem .6rem}.wk-kpi .n{font-size:1.45rem}.wk-kpi .l{font-size:.68rem}.wk-kpi .d{font-size:.66rem}.wk-kpi .u{font-size:.7rem}}
</style>"""

_G = {  # 20x20 stroke glyphs by physical kind
    "temp": "M10 3v9.5a3.5 3.5 0 1 1-4 0V3a2 2 0 0 1 4 0z", "flow": "M2 7c3-3 5 3 8 0s5 3 8 0M2 13c3-3 5 3 8 0s5 3 8 0",
    "len": "M2 6h16v8H2zM6 6v4M10 6v3M14 6v4", "power": "M11 2L4 11h5l-1 7 7-9h-5z", "spin": "M10 3a7 7 0 1 1-7 7M10 3l-2 3M10 3l-2-3",
    "conc": "M10 2C7 7 4 10 4 13a6 6 0 0 0 12 0c0-3-3-6-6-11z", "gen": "M3 10h14M10 3v14"}


def glyph(unit, name=""):
    n = name.lower()
    k = ("temp" if unit in ("C", "K") or n.startswith("t_") else "flow" if "flow" in n or unit in ("sccm", "mL/min") else "power" if unit == "W" or "rad" in n
         else "spin" if unit == "rpm" else "conc" if unit in ("M", "mg/cm3") or n.startswith("c0") or "y_" in n else "len" if unit in ("cm", "mm", "mL", "deg") else "gen")
    return f'<svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="{WB}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="{_G[k]}"/></svg>'


def vessel_card(key, title):
    try:
        from app.landing import icon as _icon
        svg = _icon(key)
    except Exception:  # noqa: BLE001  fall back to the small static schematic
        svg = icon(key)
    return f'<div class="wk-vc"><div>{svg}</div><div class="t">{e(title)}</div><div class="s"></div></div>'.replace("\n", "")


def tier_strip(active):
    """active: 0, 1 or 2."""
    names = [("Tier 0", "Regime check"), ("Tier 1", "Live model"), ("Tier 2", "CFD (stored)")]
    parts = [f'<div class="wk-tier{" on" if i == active else ""}"><b>{a}</b>{b}</div>' for i, (a, b) in enumerate(names)]
    return '<div class="wk-tiers">' + '<span class="wk-arrow">›</span>'.join(parts) + "</div>"


def kpi(label, value, unit, kind="model", delta=None):
    c = STATUS[kind][0]
    if delta is None:
        d = '<span class="d">at preset</span>'
    else:
        d = f'<span class="d {"up" if delta > 0 else "dn"}">{"▲" if delta > 0 else "▼"} {delta:+.0f} % vs preset</span>'
    return (f'<div class="wk-kpi"><div class="l"><span class="wk-dot" style="background:{c}" title="{STATUS[kind][2]}"></span>{e(label)}</div>'
            f'<div><span class="n">{e(value)}</span><span class="u">{e(unit)}</span></div>{d}</div>')


def kpis(items):
    return '<div class="wk-kpis">' + "".join(kpi(*i) for i in items) + "</div>"


def knob_head(label, unit, name, value_text):
    return f'<div class="wk-kh">{glyph(unit, name)}<span>{e(label)}</span><span class="v">{e(value_text)}</span></div>'


def effect_bar(frac, sign, what):
    """frac 0..1 = |effect| relative to the strongest knob; sign sets colour."""
    w = {True: "strong", False: "moderate"}[frac >= .6] if frac >= .25 else "weak"
    col = WB if sign >= 0 else WO
    return (f'<div class="wk-ef" title="How strongly this knob moves {e(what)} (one small step)"><span>effect</span>'
            f'<span class="bar"><i style="width:{max(4, frac * 100):.0f}%;background:{col}"></i></span><span>{w}</span></div>')


def wk_meter(parts):
    tot = sum(p[1] for p in parts) or 1
    return '<div class="wk-meter">' + "".join(f'<div style="background:{c};flex:{max(n, .01) / tot}" title="{e(l)}: {n}">{n}</div>' for l, n, c in parts) + "</div>"


def llm_strip():
    st = [("M6 3h9l4 4v14H6z M9 12h7 M9 16h7", "Reads your procedure", "values extracted, span-checked"),
          ("M4 20l6-6 M14 4l6 6-8 8-6-6z", "Calls the physics tools", "solve, rank, literature"),
          ("M4 5h16v11H9l-5 4z", "Explains the result", "never invents numbers")]
    s = '<span class="wk-arrow">›</span>'.join(
        f'<div class="st"><div class="ic"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="{p}"/></svg></div><b>{a}</b>{b}</div>' for p, a, b in st)
    return f'<div class="wk-llm">{s}</div>'
