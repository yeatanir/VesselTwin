"""VesselTwin entry point (Streamlit Community Cloud main file). Run: streamlit run streamlit_app.py"""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import streamlit as st
from app import theme
from app.theme import go_to  # noqa: F401  (re-exported helper)

st.set_page_config(page_title="VesselTwin", page_icon="🧪", layout="wide", initial_sidebar_state="collapsed")
st.session_state["vt_embedded"] = True
theme.inject_css()


def _optional(modname, title):
    """Page callable for a module owned by another track; placeholder if it is not there yet."""
    def page():
        try:
            mod = __import__(modname, fromlist=["render"])
            mod.render()
        except ImportError:
            st.title(title)
            st.info(f"The {title} page is not available in this build yet. Use Home or Advanced.")
    return page


def _home():
    from app import landing
    landing.render()


pages = {
    "Home": st.Page(_home, title="Home", url_path="home", default=True),
    "Workspace": st.Page(_optional("app.workspace", "Workspace"), title="Workspace", url_path="workspace"),
    "Evidence": st.Page(_optional("app.evidence", "Evidence"), title="Evidence", url_path="evidence"),
    "Advanced": st.Page(str(ROOT / "app" / "dashboard.py"), title="Advanced", url_path="advanced"),
}
theme.PAGES.update(pages)
st.navigation(list(pages.values()), position="top").run()
