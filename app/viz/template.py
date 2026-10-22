"""Plotly template 'vesseltwin': white paper, light grid, navy text, blue primary. No network resources (system fonts only)."""
import plotly.graph_objects as go
import plotly.io as pio

try:  # Track P owns app/theme.py; same constants as a fallback
    from app.theme import BLUE, NAVY, LIGHT, ACCENT, GREY
except Exception:
    BLUE, NAVY, LIGHT, ACCENT, GREY = "#1F5FBF", "#0B2545", "#EEF4FC", "#F28C28", "#7A8699"
SKY, TEAL, PINK = "#56B4E9", "#009E73", "#CC79A7"
SEQ = [BLUE, ACCENT, SKY, TEAL, PINK, GREY]  # colour-blind safe, anchored on blue
FONT = "Inter, 'Helvetica Neue', Arial, sans-serif"
GRID = "#DCE5F2"

pio.templates["vesseltwin"] = go.layout.Template(layout=dict(
    paper_bgcolor="white", plot_bgcolor="white", colorway=SEQ, font=dict(family=FONT, color=NAVY, size=12),
    margin=dict(l=10, r=10, t=36, b=10), hovermode="closest", hoverlabel=dict(bgcolor="white", bordercolor=BLUE, font=dict(color=NAVY, size=12)),
    xaxis=dict(gridcolor=GRID, linecolor=NAVY, zerolinecolor=GRID, automargin=True), yaxis=dict(gridcolor=GRID, linecolor=NAVY, zerolinecolor=GRID, automargin=True),
    colorscale=dict(sequential="Blues"), title=dict(font=dict(size=14, color=NAVY), x=0.01, xanchor="left"),
    legend=dict(font=dict(size=11), bgcolor="rgba(255,255,255,0.7)"), dragmode="pan"))


def apply_template(fig):
    """Apply the VesselTwin look (explicit white backgrounds so dark-mode hosts cannot make navy text unreadable)."""
    fig.update_layout(template="vesseltwin", paper_bgcolor="white", plot_bgcolor="white", font=dict(color=NAVY, family=FONT), dragmode=fig.layout.dragmode or "pan")
    fig.update_xaxes(gridcolor=GRID)
    fig.update_yaxes(gridcolor=GRID)
    return fig
