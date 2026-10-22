"""Conditions passport: what the chemistry experiences, as distributions (vessel model -> atomistic)."""
from pydantic import BaseModel


class Dist(BaseModel):
    p05: float | None = None
    p50: float
    p95: float | None = None
    unit: str = ""


class Passport(BaseModel):
    vessel: str
    site: str  # e.g. "substrate_x=12.0cm"
    T_K: Dist
    species: dict[str, dict[str, Dist]] = {}  # species -> {quantity -> Dist}
    derived: dict[str, Dist] = {}  # e.g. ratio_Mo_S, supersaturation
    source: str  # e.g. "openfoam:run_0412", "tier1:schafer"
    tier: int
    synthetic: bool  # True = illustrative, shown with a visible tag
