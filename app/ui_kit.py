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
