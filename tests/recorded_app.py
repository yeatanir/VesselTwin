import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import streamlit as st
from app.trace_tab import render_recorded

render_recorded(st, st.session_state["run"])
