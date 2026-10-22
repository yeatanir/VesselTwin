"""Unit normalization with pint. Raises on dimension mismatch so the spec bounces back."""
import re
import pint

ureg = pint.UnitRegistry()
ureg.define("sccm = cm**3 / minute = sccm")  # standard cc/min; T,P reference handled in the vessel model
_ALIAS = {"Torr": "torr", "C": "degC", "°C": "degC", "": "dimensionless", "%": "percent"}


def norm(u: str) -> str:
    """Text unit -> pint string: 'mg cm-3'/'mg/cm3' -> mg/cm**3, 'C' -> degC (pint reads C as coulomb), 'g L-1' -> g/L."""
    u = re.sub(r"\s+", " ", u.strip().replace("−", "-"))
    u = re.sub(r"\b([a-zA-Z]+) ([a-zA-Z]+)-(\d)\b", r"\1/\2**\3", u)  # 'mg cm-3' -> mg/cm**3
    u = re.sub(r"\b([a-zA-Z]+)-1\b", r"1/\1", u)  # 'L-1' fragment
    u = re.sub(r"(?<=[a-zA-Z])(\d)\b", r"**\1", u).replace(" ", "")
    return _ALIAS.get(u, u)


def to_unit(value: float, unit: str, target: str) -> float:
    return ureg.Quantity(value, norm(unit)).to(norm(target)).magnitude  # Quantity() so offset units (degC) convert
