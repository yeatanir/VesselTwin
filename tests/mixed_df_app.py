import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pandas as pd, streamlit as st
from app.common import show_df, clean

show_df(st, pd.DataFrame({"value": [1.0, "Ar", None], "unit": ["a", "b", "c"]}))
st.session_state["cleaned"] = clean(pd.DataFrame({"value": [1.0, "Ar"]}))["value"].tolist()
