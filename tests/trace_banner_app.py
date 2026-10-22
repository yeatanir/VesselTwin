import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import streamlit as st
from app import trace_tab

tr = st.session_state["tr"]
trace_tab._step_compare(st, next(s for s in tr["steps"] if s["name"] == "compare"))
