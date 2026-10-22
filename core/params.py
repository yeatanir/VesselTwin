"""Editable parameters. Every dimension/knob of a vessel is a ParamDef: the single source of truth for
solver defaults, bounds, units, uncertainty and the future front end (see core.api.schema)."""
from dataclasses import dataclass, asdict, field
from llm.units import to_unit
from schemas.setupspec import SetupSpec, Status


@dataclass
class ParamDef:
    name: str
    label: str
    unit: str  # canonical unit; the solver sees values in this unit
    default: float | str
    lo: float | None = None  # hard bounds: out of range bounces the spec back
    hi: float | None = None
    sigma: float = 0.0  # 1-sigma for Monte-Carlo; relative if sigma_rel else absolute
    sigma_rel: bool = True
    choices: list[str] | None = None  # for string params
    group: str = "general"  # geometry | operation | thermo | model ... for UI grouping
    source: str = "default"  # "synthetic" = illustrative placeholder (tagged in UI), else citation
    help: str = ""


def defaults(defs: list[ParamDef]) -> dict:
    return {d.name: d.default for d in defs}


def validate(defs: list[ParamDef], values: dict) -> dict:
    by = {d.name: d for d in defs}
    bad = set(values) - set(by)
    if bad:
        raise ValueError(f"unknown params: {sorted(bad)}")
    out = defaults(defs) | values
    for k, v in out.items():
        d = by[k]
        if d.choices is not None:
            if v not in d.choices:
                raise ValueError(f"{k}={v!r} not in {d.choices}")
        elif (d.lo is not None and v < d.lo) or (d.hi is not None and v > d.hi):
            raise ValueError(f"{k}={v} {d.unit} outside [{d.lo}, {d.hi}]")
    return out


def from_spec(defs: list[ParamDef], spec: SetupSpec) -> tuple[dict, dict]:
    """SetupSpec -> (values in canonical units, provenance per key: stated|default|missing->default)."""
    by = {d.name: d for d in defs}
    vals, prov = {}, {}
    for k, f in spec.params.items():
        d = by[k]
        if f.status is Status.missing:
            continue  # falls back to ParamDef.default, reported below
        vals[k] = f.value if d.choices else (to_unit(f.value, f.unit, d.unit) if f.unit else f.value)
        prov[k] = f.status.value
    for d in defs:
        prov.setdefault(d.name, "synthetic" if d.source == "synthetic" else "default")
    return validate(defs, vals), prov


def ui_schema(defs: list[ParamDef]) -> list[dict]:
    return [asdict(d) for d in defs]
