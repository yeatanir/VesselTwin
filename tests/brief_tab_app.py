import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import streamlit as st
from app.brief_tab import render

render(st, st.session_state.get("vessel", "sorbent"), {})
