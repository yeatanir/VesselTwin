"""A vessel is a template: editable ParamDefs + a fast scalar solver. New vessel = new file + register()."""
from dataclasses import dataclass, field
from typing import Callable
from core import uq
from core.dimensionless import Regime
from core.params import ParamDef
from schemas.passport import Passport

REGISTRY: dict[str, "Vessel"] = {}


@dataclass
class Vessel:
    name: str
    title: str
    defs: list[ParamDef]  # every dimension and knob; the front end edits these
    tier0: Callable[[dict], tuple[Regime, float, dict]]  # values -> regime, margin (>=1 confident), numbers shown to the user
    solve: Callable[[dict], dict]  # values -> scalar outputs (Tier 1 reduced model)
    units: dict[str, str]  # output key -> unit
    site: Callable[[dict], str]  # passport site label
    source: str  # e.g. "tier1:boundary-layer"
    anchors: list[str] = field(default_factory=list)  # known-answer references
    profile: Callable[[dict], dict] | None = None  # optional deterministic 1D profiles for plotting
    extras: Callable[[dict], dict] | None = None  # optional extra analyses (e.g. shape map), returned under 'extras'

    @property
    def params(self) -> list[str]:
        return [d.name for d in self.defs]

    def tier1(self, values: dict, synthetic: bool = True, n: int = 100, seed: int = 0) -> Passport:
        mc = uq.monte_carlo(self.solve, self.defs, values, n=n, seed=seed)
        return uq.to_passport(self.name, self.site(values), self.source, mc, self.units, synthetic)


def register(v: Vessel) -> Vessel:
    REGISTRY[v.name] = v
    return v


def load_all():
    """Import every package/module in vessels/ (names starting with '_' skipped): a dropped-in file registers itself."""
    import importlib, pkgutil, vessels
    for m in pkgutil.iter_modules(vessels.__path__):  # ponytail: a broken vessel raises loudly, no silent skip
        if not m.name.startswith("_"):
            importlib.import_module(f"vessels.{m.name}")
    return REGISTRY
