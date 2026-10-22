"""B2 scoring (run ONCE after the pre-registration commit a060deb). Writes tier2/verification/b2_results.json.
usage: python tier2/verification/b2_score.py"""
import json, math, pathlib, sys
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
from core import params as P
import vessels.ampoule as amp
from surrogate import correction as C
from tier2.verification.tier0 import f_variant

OUT = pathlib.Path(__file__).with_name("b2_results.json")


def metrics(pred, cfd):
    e = np.abs(np.asarray(pred) / np.asarray(cfd) - 1)
    return dict(n=len(e), median=float(np.median(e)), mean=float(e.mean()), frac_le_5=float((e <= .05).mean()), frac_le_20=float((e <= .2).mean()))


def evaluate(kind, rawX, t1, cfd, mask, tag):
    y = np.log10(np.asarray(cfd) / np.asarray(t1))
    yh, ys = C.loo(kind, rawX, y)
    pred = np.asarray(t1) * 10**yh
    z = np.abs(yh - y) / ys
    spread = dict(std=float(y.std()), min=float(y.min()), max=float(y.max()), range_decades=float(y.max() - y.min()), mean=float(y.mean()))
    out = dict(tag=tag, y_spread=spread, learnable=bool(spread["range_decades"] <= 3),
               within_1sigma=float((z <= 1).mean()), within_2sigma=float((z <= 2).mean()), mean_y_std=float(ys.mean()),
               surrogate_all=metrics(pred, cfd), tier1_all=metrics(t1, cfd))
    if mask is not None and mask.sum() < len(mask):
        out["surrogate_unseen"] = metrics(pred[mask], np.asarray(cfd)[mask]); out["tier1_unseen"] = metrics(np.asarray(t1)[mask], np.asarray(cfd)[mask])
    return out, y, yh, ys


res = {}
# ---- ampoule
rows = [r for r in json.load(open(ROOT / "docs/ampoule_cfd_verification.json"))["sweep"] if r["ok"]]
ps = [P.validate(amp.DEFS, {k: v for k, v in r["values"].items() if k not in ("cells_per_cm", "n_cross")}) for r in rows]
rawX = [C.raw("ampoule", r["values"]) for r in rows]
cfd = [r["f_cfd"] for r in rows]
near = np.array([abs(r["values"]["tilt_deg"]) <= 10 and 12 <= r["values"]["L_cm"] <= 18 for r in rows])
res["ampoule_n"] = len(rows); res["ampoule_near_fit_scan_ids"] = [r["id"] for r, n in zip(rows, near) if n]
t1_post = [f_variant(p, "duct") for p in ps]
t1_pre = [f_variant(p, "legacy_L3") for p in ps]
for tag, t1 in (("post_fix_tier1 (shipped; fix chosen after seeing all 60 sweep cases: optimistic)", t1_post), ("pre_fix_tier1 (aa4e98c; fitted only to the tilt-0 scan: sweep unseen)", t1_pre)):
    r, y, yh, ys = evaluate("ampoule", rawX, t1, cfd, ~near, tag)
    res.setdefault("ampoule", []).append(r)
    C.save("ampoule", "post" if "post" in tag.split()[0] else "pre", rawX, y)
# ---- tube
sys.path.insert(0, str(ROOT / "scripts"))
import tube_cfd_verification as TV
sw = [r for r in json.load(open(ROOT / "docs/tube_cfd_verification.json"))["sweep"] if r["ok"]]
rawT = [C.raw("tube", r["values"]) for r in sw]
t1 = [TV.tier1(r["values"]) for r in sw]
outs = {"ratio_Mo_S": ("ratio_Mo_S", "ratio_Mo_S"), "supersaturation_MoO3_wallT": ("supersaturation_MoO3_wallT", "ss_wallT"), "ss_gasT": ("ss_gasT", "ss_gasT"),
        "p_MoO3_Pa": ("p_MoO3_Pa", "p_MoO3_Pa"), "p_S2_Pa": ("p_S2_Pa", "p_S2_Pa")}
res["tube_n"] = len(sw); res["tube"] = {}
for name, (kc, kt) in outs.items():
    r, y, yh, ys = evaluate("tube", rawT, [a[kt] for a in t1], [s[kc] for s in sw], None, name)
    res["tube"][name] = r
    C.save("tube", name, rawT, y)
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps(res, indent=1))
