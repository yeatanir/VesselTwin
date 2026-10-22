"""Mimics the streamlit_app.py page loader (import by module name, then render) from a foreign cwd."""
import os, sys, pathlib, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(tempfile.gettempdir())  # real servers may run from any cwd
import streamlit as st
for m in ("app.workspace", "app.evidence"):
    mod = __import__(m, fromlist=["render"])
    if m == "app.workspace":
        mod.render()
