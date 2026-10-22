"""Template vessel: copy to vessels/<name>.py (or a package) and it appears in the dashboard, no other edit.
Files starting with '_' are skipped by core.registry.load_all(). Contracts: ParamDef (editable, bounded, sourced),
tier0 (regime + margin + shown numbers), solve (scalar outputs; Monte Carlo and the Passport are built for you).
Anything illustrative: source="synthetic" (amber badge in the UI). See docs/ADDING_A_VESSEL.md."""
from core.dimensionless import classify
from core.params import ParamDef as P
from core.registry import Vessel, register

DEFS = [
    P("L_cm", "Length", "cm", 10.0, 1, 100, group="geometry"),
    P("rate_1_s", "Rate constant", "1/s", 0.1, 1e-6, 1e3, 0.2, source="synthetic", group="model"),  # sigma 0.2 = 20% relative
]


def tier0(p):  # values -> (Regime, margin >= 1 means confident, numbers shown to the user)
    Da = p["rate_1_s"] * p["L_cm"]
    r, margin = classify(Da)
    return r, margin, {"Da": Da}


def solve(p):  # values -> scalar outputs, keys must match `units` below
    return {"T_K": 298.15, "conversion": 1 - 2.718281828 ** (-p["rate_1_s"] * p["L_cm"])}


register(Vessel("template_demo", "Template demo vessel", DEFS, tier0, solve, {"conversion": ""},
                lambda p: "outlet", "tier1:toy", ["analytic limit"]))
