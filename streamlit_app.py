"""VesselTwin entry point (Streamlit Community Cloud main file). Run: streamlit run streamlit_app.py"""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import streamlit as st
from app import theme
from app.theme import go_to  # noqa: F401  (re-exported helper)

try:
    from PIL import Image
    _icon = Image.open(ROOT / "assets" / "icon.png")
except Exception:  # Pillow missing or file absent: fall back to an emoji
    _icon = "🧪"
st.set_page_config(page_title="VesselTwin", page_icon=_icon, layout="wide", initial_sidebar_state="collapsed")

st.session_state["vt_embedded"] = True
theme.inject_css()


def _optional(modname, title):
    """Page callable for a module owned by another track; placeholder if it is not there yet."""
    def page():
        try:
            mod = __import__(modname, fromlist=["render"])
        except ImportError as e:
            st.title(title)
            st.info(f"The {title} page could not be loaded: {e}. Run `pip install -r requirements.txt` and restart the app.")
            return
        mod.render()  # errors inside the page are shown by Streamlit, not hidden
    return page


def _home():
    from app import landing
    landing.render()


pages = {
    "Home": st.Page(_home, title="Home", url_path="home", default=True),
    "Workspace": st.Page(_optional("app.workspace", "Workspace"), title="Workspace", url_path="workspace"),
    "Studio": st.Page(_optional("app.studio", "Studio"), title="Studio", url_path="studio"),
    "Evidence": st.Page(_optional("app.evidence", "Evidence & literature"), title="Evidence & literature", url_path="evidence"),
    "Advanced": st.Page(str(ROOT / "app" / "dashboard.py"), title="Advanced", url_path="advanced"),
}
theme.PAGES.update(pages)
current = st.navigation(list(pages.values()), position="hidden")  # Streamlit's own top nav sits inside the toolbar that theme.py hides, so we draw ours


def _topbar():
    with st.container(key="topbar"):
        cols = st.columns([2.2, 1, 1.2, 1, 1.9, 1.1], vertical_alignment="center")
        with cols[0]:
            st.page_link(pages["Home"], label=" ", icon=None)  # invisible full-logo link target (styled in theme.py)
            try:
                st.image(str(ROOT / "assets" / "logo_small.png"), width=170)
            except Exception:
                st.markdown("**VesselTwin**")
        for col, key, label in zip(cols[1:], ["Home", "Workspace", "Studio", "Evidence", "Advanced"],
                                   ["Home", "Workspace", "Studio", "Evidence & literature", "Advanced"]):
            with col:
                st.page_link(pages[key], label=label)


_topbar()
current.run()
