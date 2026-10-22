"""Front-end facing API: everything a UI needs, all JSON-serialisable. No Streamlit/FastAPI dependency here."""
import json, pathlib
from core import params as P
from core.registry import REGISTRY, load_all
from schemas.closure import Closure
from schemas.setupspec import SetupSpec

PRESETS = pathlib.Path(__file__).resolve().parents[1] / "presets"


def list_vessels() -> list[dict]:
    return [{"name": v.name, "title": v.title, "anchors": v.anchors} for v in load_all().values()]


def schema(vessel: str) -> list[dict]:
    """ParamDef list (label, unit, default, bounds, sigma, choices, group, source) for building edit forms."""
    return P.ui_schema(load_all()[vessel].defs)


def defaults(vessel: str) -> dict:
    return P.defaults(load_all()[vessel].defs)


def presets(vessel: str) -> list[str]:
    return sorted(f.stem for f in PRESETS.glob(f"{vessel}__*.json"))


def _load_preset(name: str) -> tuple[dict, dict]:
    """-> (params, _meta). `_meta` ({'title','source'}) is documentation, never validated."""
    d = json.loads((PRESETS / f"{name}.json").read_text())
    return d, d.pop("_meta", {})


def preset_info(vessel: str) -> list[dict]:
    """Chemistry sets for a vessel: name, title, source, params (for the dropdown)."""
    out = []
    for n in presets(vessel):
        d, m = _load_preset(n)
        out.append({"name": n, "title": m.get("title", n.split("__", 1)[1]), "source": m.get("source", "synthetic"), "params": d})
    return out


def apply_closures(v, values: dict, closures: list[Closure]) -> dict:
    """Atomistic -> vessel: closure 'isotherm' with params {qmax,b0,Q} sets params 'isotherm.qmax' etc."""
    out = dict(values)
    for c in closures:
        for k, x in c.params.items():
            if f"{c.name}.{k}" in v.params:
                out[f"{c.name}.{k}"] = x
    return out


def solve(vessel: str, overrides: dict | None = None, preset: str | None = None, closures: list[Closure] | None = None,
          n_mc: int = 100, seed: int = 0, spec: SetupSpec | None = None, extras: bool = True) -> dict:
    """Run tier0 + tier1 (+ deterministic profiles). `overrides` are canonical-unit values (what the UI edits)."""
    v = load_all()[vessel]
    prov = {}
    base = {}
    if spec is not None:
        base, prov = P.from_spec(v.defs, spec)
    if preset:
        pv, meta = _load_preset(preset)
        base |= pv
        sourced = "synthetic" not in meta.get("source", "synthetic").lower() and "illustrative" not in meta.get("source", "").lower()
        prov |= {k: ("sourced" if sourced else "synthetic") for k in pv}  # preset values carry the preset's own provenance
    base |= overrides or {}
    prov |= {k: "edited" for k in (overrides or {})}
    vals = P.validate(v.defs, base)
    if closures:
        vals = P.validate(v.defs, apply_closures(v, vals, closures))
    for d in v.defs:
        prov.setdefault(d.name, "edited" if d.name in (overrides or {}) else ("synthetic" if d.source == "synthetic" else "default"))
    synthetic = any(prov[d.name] == "synthetic" for d in v.defs)
    regime, margin, numbers = v.tier0(vals)
    passport = v.tier1(vals, synthetic=synthetic, n=n_mc, seed=seed)
    return {"vessel": vessel, "values": vals, "provenance": prov, "regime": regime.value, "margin": margin,
            "numbers": numbers, "passport": passport.model_dump(), "profile": v.profile(vals) if v.profile else None,
            "extras": v.extras(vals) if (extras and v.extras) else None}
