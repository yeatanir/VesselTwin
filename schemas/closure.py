"""Closure contract: atomistic results -> parameters of physically valid laws (atomistic -> vessel model)."""
from typing import Literal
from pydantic import BaseModel


class Closure(BaseModel):
    name: str  # e.g. "k_attach", "gamma_edge_Mo_zigzag"
    law: Literal["arrhenius", "langmuir", "linear", "const"]
    params: dict[str, float]  # arrhenius: A, Ea_eV ; langmuir: qmax, b ; ...
    sigma: dict[str, float] = {}  # 1-sigma per param (ensemble disagreement)
    reverse: "Closure | None" = None  # detailed balance partner, if any
    method: str  # "DFT-PBE", "MACE-MP-0", "ReaxFF-MoSO", "literature"
    source: str  # ref / run id
    synthetic: bool = False
