"""Evidence figure for the write-up: predicted/measured against published experiments, and the MoS2 results against baselines.
Values come from bench/*/results.json and docs/status/status_final_oct21.md. Run: python scripts/make_fig_evidence.py"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BLUE, NAVY, ORANGE, GREY = "#1F5FBF", "#0B2545", "#F28C28", "#8A97AB"
fig, (a, b) = plt.subplots(1, 2, figsize=(14, 5.2), gridspec_kw={"width_ratios": [1.35, 1]})
rows = [("Photoreactor, collimated beam", 0.879, BLUE, (1 / 1.25, 1.25)), ("Photoreactor, diffuse light", 0.688, BLUE, (1 / 1.5, 1.5)),
        ("Sorbent CALF-20, feed 1", 0.967, BLUE, None), ("Sorbent CALF-20, feed 2", 1.019, BLUE, None), ("Sorbent CALF-20, feed 3", 1.098, BLUE, None),
        ("Sorbent 13X, flow 1", 0.621, ORANGE, None), ("Sorbent 13X, flow 2", 0.609, ORANGE, None)]
y = np.arange(len(rows))[::-1]
a.axvline(1, color=GREY, lw=1, ls="--")
for yi, (n, v, c, tol) in zip(y, rows):
    if tol:
        a.hlines(yi, tol[0], tol[1], color="#BCD0EE", lw=9, zorder=1)
    a.plot(v, yi, "o", color=c, ms=9, zorder=3)
    a.text(v * 1.04, yi + 0.28, f"{v:.2f}", fontsize=9, color=NAVY, ha="left")
a.hlines(-1.2, 1, 38, color=ORANGE, lw=6)
a.text(1.05, -1.75, "Ampoule vs published WO2/HgX2 rates: over-predicts 1x to 38x (range)", fontsize=9, color=NAVY)
a.set_yticks(list(y))
a.set_yticklabels([r[0] for r in rows], fontsize=10, color=NAVY)
a.set_xscale("log")
a.set_xlim(0.45, 45)
a.set_ylim(-2.1, len(rows) - 0.3)
a.set_xticks([0.5, 1, 2, 5, 10, 20, 40])
a.set_xticklabels(["0.5", "1", "2", "5", "10", "20", "40"])
a.set_xlabel("predicted / measured (log scale); shaded band = pre-registered tolerance", color=NAVY)
a.set_title("A  Against published experiments", loc="left", fontsize=13, color=NAVY, fontweight="bold")
for s in ("top", "right"):
    a.spines[s].set_visible(False)
xm, xb, xa = [-0.27, 0.73], [0, 1.0], [0.27, 1.27]
b.bar(xm[0], 3 / 9, width=0.24, color=BLUE, label="VesselTwin (1/9 to 3/9)")
b.bar(xm[0], 1 / 9, width=0.24, color=NAVY)
b.bar(xb[0], 6 / 9, width=0.24, color=GREY, label="No-tool LLM")
b.bar(xa[0], 4 / 9, width=0.24, color="#C9D3E3", label="Always 'increase' / always 'triangle'")
b.bar(xm[1], 0.5, width=0.24, color=BLUE)
b.bar(xa[1], 0.5, width=0.24, color="#C9D3E3")
for xv, h, t in [(xm[0], 3 / 9, "1-3 / 9"), (xb[0], 6 / 9, "6 / 9"), (xa[0], 4 / 9, "4 / 9"), (xm[1], 0.5, "0.50"), (xa[1], 0.5, "0.50")]:
    b.text(xv, h + 0.02, t, ha="center", fontsize=9, color=NAVY)
b.set_xticks([0, 1.0])
b.set_xticklabels(["MoS2 trend calls\n(9 literature items)", "MoS2 shape class\n(8 in-scope cases)"], fontsize=10, color=NAVY)
b.set_ylim(0, 1)
b.set_ylabel("accuracy", color=NAVY)
b.set_title("B  Where the flagship model does not work", loc="left", fontsize=13, color=NAVY, fontweight="bold")
b.legend(frameon=False, fontsize=8.5, loc="upper right")
for s in ("top", "right"):
    b.spines[s].set_visible(False)
fig.text(0.01, 0.01, "All MoS2 items are development data (no held-out set). Sorbent 13X (orange): the model runs too hot, about 38% early. Values from the repository's results files.", fontsize=8.5, color=GREY)
plt.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig("docs/screens/fig_evidence.png", dpi=130)
