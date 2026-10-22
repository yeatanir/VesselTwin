"""Hallucination control #2: a value is accepted only if its source span is in the text and contains the number."""
import re
from schemas.setupspec import Field, SetupSpec, Status

_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def check_field(f: Field, text: str) -> Field:
    """Downgrade an unproven 'stated' field to missing. Defaults pass through (they come from the table)."""
    if f.status is not Status.stated:
        return f
    ok = f.span in text
    if ok and isinstance(f.value, (int, float)):
        ok = any(abs(float(n) - float(f.value)) < 1e-9 for n in _NUM.findall(f.span))
    if ok:
        return f
    return Field(status=Status.missing, note=f"rejected: span/value not in text (was {f.value!r})")


def check_spec(spec: SetupSpec, text: str) -> SetupSpec:
    return spec.model_copy(update={"params": {k: check_field(v, text) for k, v in spec.params.items()}})


def fabricated(spec: SetupSpec, text: str) -> int:
    """Benchmark metric: stated fields that fail the check. Target: 0 after check_spec."""
    return sum(check_field(v, text).status is not v.status for v in spec.params.values())
