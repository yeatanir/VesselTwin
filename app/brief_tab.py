"""Brief tab: conditions the chemistry sees (with tails), ranked atomistic calculations, downloadable brief.
Usage from the dashboard: `from app.brief_tab import render; render(st, vessel, values)` (values = canonical-unit overrides)."""
import json
import altair as alt
import pandas as pd
from atomistic import brief as B
from app.common import show_df


def render(st, vessel: str, values: dict | None = None, n_mc: int = 60):
    key = json.dumps(values or {}, sort_keys=True)
    b = st.cache_data(show_spinner="Building brief...")(lambda v, k, n: B.make_brief(v, json.loads(k), n_mc=n))(vessel, key, n_mc)
    if b["synthetic"]:
        st.warning("SYNTHETIC: reduced-model constants are illustrative placeholders; the workflow is real, the numbers are not predictions.")
    st.subheader("Conditions the chemistry sees")
    show_df(st, pd.DataFrame(b["conditions"]).rename(columns={"low_tail": "low-outcome tail", "high_tail": "high-outcome tail"}), hide_index=True)
    st.subheader("Which atomistic calculation would most change the outcome")
    if b["ranking"]:
        df = pd.DataFrame(b["ranking"])
        df["label"] = df["rank"].astype(str) + ". " + df["param"] + " (" + df["cost"] + ")"
        st.altair_chart(alt.Chart(df).mark_bar().encode(
            y=alt.Y("label", sort=None, title=None), x=alt.X("delta", title=f"expected change in outcome ({b['outcome']['unit'] or 'dimensionless'})"),
            color=alt.Color("cost", scale=alt.Scale(domain=["cheap", "medium", "expensive"], range=["#2a9d8f", "#e9c46a", "#e76f51"])),
            tooltip=["calc", "param", "cost", "delta"]), width="stretch")
        show_df(st, df[["rank", "calc", "param", "cost", "sigma", "unit", "delta", "rationale"]], hide_index=True)
    st.subheader("Report")
    md = B.to_markdown(b)
    st.markdown(md)
    c1, c2 = st.columns(2)
    c1.download_button("Download brief (markdown)", md, file_name=f"brief_{vessel}.md", mime="text/markdown")
    c2.download_button("Download brief (JSON)", json.dumps(b, indent=1, default=float), file_name=f"brief_{vessel}.json", mime="application/json")
