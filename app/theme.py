"""Blue-and-white theme: CSS, info icon, navigation helper, Plotly colour constants (for app/viz)."""
import html
import streamlit as st

BLUE, NAVY, LIGHT, ACCENT, GREY = "#1F5FBF", "#0B1F44", "#EEF4FC", "#F28C28", "#6B7A90"
PAGES = {}  # filled by streamlit_app.py: name -> st.Page

CSS = f"""
<style>
:root{{--b:{BLUE};--n:{NAVY};--l:{LIGHT};--a:{ACCENT};--g:{GREY}}}
#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDeployButton"],.stDeployButton,[data-testid="stStatusWidget"]{{display:none!important}}
header[data-testid="stHeader"]{{background:rgba(255,255,255,.92)}}
.block-container{{padding-top:3.2rem;padding-bottom:2rem;max-width:1180px}}
h1,h2,h3{{color:var(--n);letter-spacing:-.01em}}
.stButton>button,.stDownloadButton>button{{border-radius:999px;border:1px solid var(--b);background:var(--b);color:#fff;font-weight:600;padding:.45rem 1.3rem;transition:transform .15s,box-shadow .15s}}
.stButton>button:hover{{background:#174c9a;border-color:#174c9a;color:#fff;transform:translateY(-1px);box-shadow:0 6px 16px rgba(31,95,191,.3)}}
.vt-hero{{background:linear-gradient(135deg,#fff 0%,#EEF4FC 55%,#D6E6FA 100%);border-radius:24px;padding:2rem 2rem 1rem;box-shadow:0 8px 30px rgba(31,95,191,.12)}}
.vt-hero h1{{font-size:clamp(1.7rem,4.2vw,3rem);line-height:1.1;margin:0 0 .5rem}}
.vt-sub{{color:var(--g);font-size:1.05rem;margin-bottom:.6rem}}
.vt-sec{{margin:3rem 0 .3rem;font-size:1.5rem;font-weight:700;color:var(--n)}}
.vt-cap{{color:var(--g);margin-bottom:1rem}}
.vt-card{{background:#fff;border:1px solid #D6E3F5;border-radius:18px;padding:1.1rem 1.2rem;box-shadow:0 2px 10px rgba(11,31,68,.06);height:100%}}
.vt-card h4{{margin:.2rem 0;color:var(--n)}}
.vt-chip{{display:inline-block;border-radius:999px;padding:.12rem .7rem;font-size:.78rem;font-weight:600;background:var(--l);color:var(--b);border:1px solid #BCD3F2}}
.vt-chip.warn{{background:#FFF3E5;color:#B35F00;border-color:#F6D3A8}}
.vt-chip.grey{{background:#F1F3F6;color:#4B5A70;border-color:#D8DEE8}}
[class*="st-key-vcard_"]{{background:#fff;border:1px solid #D6E3F5;border-radius:18px;padding:1rem;box-shadow:0 2px 10px rgba(11,31,68,.06);transition:transform .2s,box-shadow .2s,border-color .2s}}
[class*="st-key-vcard_"]:hover{{transform:translateY(-4px);box-shadow:0 14px 28px rgba(31,95,191,.2);border-color:var(--b)}}
.vt-i{{position:relative;display:inline-flex;align-items:center;justify-content:center;width:1.15em;height:1.15em;margin-left:.4em;border-radius:50%;border:1.5px solid var(--b);color:var(--b);font:700 .72em/1 serif;cursor:help;vertical-align:middle;outline:none}}
.vt-i .vt-tip{{visibility:hidden;opacity:0;position:absolute;z-index:99;bottom:140%;left:50%;transform:translateX(-50%);width:max-content;max-width:min(320px,80vw);background:var(--n);color:#fff;font:400 .85rem/1.35 sans-serif;padding:.6rem .8rem;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.25);transition:opacity .15s;text-align:left;white-space:normal}}
.vt-i:hover .vt-tip,.vt-i:focus .vt-tip{{visibility:visible;opacity:1}}
/* heading scale + button/card polish (Track V) */
h1{{font-size:2.2rem}}h2{{font-size:1.6rem}}h3{{font-size:1.25rem}}h4{{font-size:1.05rem}}
.stButton>button{{box-shadow:0 1px 3px rgba(11,31,68,.12)}}
.vt-card:hover{{box-shadow:0 10px 24px rgba(31,95,191,.16);border-color:var(--b)}}
@media (max-width:640px){{h1{{font-size:1.7rem}}h2{{font-size:1.3rem}}.vt-sec{{font-size:1.35rem}}}}
/* shared polish: page transition, cards, nav, inputs, tighter spacing */
@keyframes vt-page{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:none}}}}
[data-testid="stMainBlockContainer"]{{animation:vt-page .45s ease both}}
.stApp{{background:linear-gradient(180deg,#fff 0%,#F6F9FE 100%)}}
h1{{font-weight:800}}h2,h3{{font-weight:700}}h2,h3,h4{{color:var(--b)}}
[data-testid="stVerticalBlock"]{{gap:.8rem}}
[data-testid="stMetric"]{{background:#fff;border:1px solid #D6E3F5;border-radius:14px;padding:.7rem .9rem;box-shadow:0 2px 8px rgba(11,31,68,.05)}}
[data-testid="stExpander"]{{border:1px solid #D6E3F5!important;border-radius:14px!important;background:#fff}}
[data-baseweb="tab-list"]{{gap:.3rem}}[data-baseweb="tab"]{{border-radius:10px 10px 0 0}}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"]{{border-radius:12px!important}}
a{{color:var(--b)}}a:hover{{color:#174c9a}}
.stButton>button:focus-visible,a:focus-visible,.vt-i:focus-visible{{outline:3px solid #F28C28;outline-offset:2px}}
.stButton>button:active{{transform:translateY(0);box-shadow:none}}
@media (prefers-reduced-motion:reduce){{[data-testid="stMainBlockContainer"]{{animation:none}}.stButton>button{{transition:none}}}}
/* hero animation */
@keyframes vt-flow{{from{{transform:translateX(0)}}to{{transform:translateX(var(--d,640px))}}}}
@keyframes vt-pulse{{0%,100%{{opacity:.35;transform:scale(1)}}50%{{opacity:1;transform:scale(1.5)}}}}
@keyframes vt-glow{{0%,100%{{opacity:.5}}50%{{opacity:.9}}}}
@keyframes vt-spin{{to{{transform:rotate(360deg)}}}}
@keyframes vt-front{{from{{transform:scaleX(.1)}}to{{transform:scaleX(1)}}}}
@keyframes vt-dash{{to{{stroke-dashoffset:-24}}}}
.vt-p{{animation:vt-flow 5s linear infinite;opacity:.85}}
.vt-pulse{{animation:vt-pulse 1.6s ease-in-out infinite;transform-box:fill-box;transform-origin:center}}
.vt-glow{{animation:vt-glow 3s ease-in-out infinite}}
.vt-spin{{animation:vt-spin 1.4s linear infinite;transform-box:fill-box;transform-origin:center}}
.vt-front{{animation:vt-front 4s ease-in-out infinite alternate;transform-box:fill-box;transform-origin:left}}
.vt-flowline{{stroke-dasharray:6 6;animation:vt-dash .8s linear infinite}}
@media (prefers-reduced-motion:reduce){{.vt-p,.vt-pulse,.vt-glow,.vt-spin,.vt-front,.vt-flowline{{animation:none}}}}
@media (max-width:640px){{.block-container{{padding-left:1rem;padding-right:1rem}}.vt-hero{{padding:1.2rem 1rem .5rem;border-radius:16px}}}}

.st-key-topbar{{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.96);backdrop-filter:blur(6px);border-bottom:1px solid #DCE7F7;padding:.35rem .6rem;margin:0 -1rem 1rem -1rem;padding-top:.7rem}}
.st-key-topbar img{{display:block}}
.st-key-topbar [data-testid="stPageLink"] a{{border-radius:999px;padding:.35rem .9rem;color:#0B2545;font-weight:600;text-decoration:none;justify-content:center}}
.st-key-topbar [data-testid="stPageLink"] a:hover{{background:#EEF4FC;color:#1F5FBF}}
.st-key-topbar [data-testid="stPageLink"] a[aria-current="page"]{{background:#1F5FBF;color:#fff}}
.st-key-topbar [data-testid="stColumn"]:first-child [data-testid="stPageLink"]{{position:absolute;inset:0;z-index:3;opacity:0}}
.st-key-topbar [data-testid="stColumn"]:first-child [data-testid="stPageLink"] a{{height:100%;width:100%}}
@media (max-width:700px){{.st-key-topbar [data-testid="stHorizontalBlock"]{{flex-wrap:wrap}}.st-key-topbar [data-testid="stColumn"]{{min-width:auto}}}}
header[data-testid="stHeader"]{{display:none!important}}
.block-container{{padding-top:0!important}}
</style>
"""


def inject_css():
    st.html(CSS)


def info(text, label=""):
    """Small circled i with a CSS hover/focus tooltip (no JS). Renders inline via st.html; returns None."""
    st.html(info_html(text, label))


def info_html(text, label=""):
    return f'{html.escape(label)}<span class="vt-i" tabindex="0" role="note" aria-label="info">i<span class="vt-tip">{html.escape(text)}</span></span>'


def go_to(page_name, **state):
    """Open a navigation page by name, first storing state in st.session_state (e.g. vt_vessel='sorbent')."""
    st.session_state.update(state)
    if page_name in PAGES:
        st.switch_page(PAGES[page_name])
