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
try:
    st.logo(str(ROOT / "assets" / "logo_small.png"), icon_image=str(ROOT / "assets" / "icon.png"), size="large")
except Exception:  # older Streamlit without st.logo options
    pass
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
st.navigation(list(pages.values()), position="top").run()
