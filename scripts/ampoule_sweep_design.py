"""Latin-hypercube design for the ampoule CFD verification: (D_mm, L_cm, dT = T_source-T_sink, tilt, agent loading); T_sink 800 C, rest default.
usage: python scripts/ampoule_sweep_design.py <out.json> [n=60]"""
import json, sys
import numpy as np
from scipy.stats import qmc
import vessels.ampoule as amp
from core import params as P

LO, HI = np.array([6, 8, 10, -90, 0.5]), np.array([45, 20, 150, 90, 15])  # D, L, dT, tilt, agent
NAMES = ["D_mm", "L_cm", "dT_K", "tilt_deg", "agent_mg_per_cm3"]


def case_values(x):
    D, L, dT, tilt, ag = x
    return dict(D_mm=round(D, 2), L_cm=round(L, 2), T_source_C=800.0 + round(dT, 1), T_sink_C=800.0, tilt_deg=round(tilt, 1),
                agent_mg_per_cm3=round(ag, 3), cells_per_cm=4.0, n_cross=10)


if __name__ == "__main__":
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    X = qmc.scale(qmc.LatinHypercube(d=5, seed=7).random(n), LO, HI)
    jobs = [{"id": f"s{i:02d}", "values": case_values(x)} for i, x in enumerate(X)]
    for j in jobs:
        p = P.validate(amp.DEFS, {k: v for k, v in j["values"].items() if k not in ("cells_per_cm", "n_cross")})
        j["tier0_f"], j["tier0_regime"] = float(amp._core(p)["f"]), amp.tier0(p)[0].value
    json.dump(jobs, open(sys.argv[1], "w"), indent=1)
    f = np.array([j["tier0_f"] for j in jobs]); print("tier0 f quantiles", np.quantile(f, [0, .25, .5, .75, 1]), "n_conv", sum(j["tier0_regime"] == "convection_assisted" for j in jobs))
