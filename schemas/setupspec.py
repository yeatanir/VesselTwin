"""SetupSpec: LLM front-door output. Contract between C (extraction) and everyone else."""
from enum import Enum
from pydantic import BaseModel, model_validator


class Status(str, Enum):
    stated = "stated"    # value found in the text, span proves it
    default = "default"  # filled from vetted defaults table (shown amber)
    missing = "missing"  # unknown, never invented


class Field(BaseModel):
    value: float | str | None = None
    unit: str | None = None
    span: str | None = None  # verbatim source text
    status: Status = Status.missing
    note: str | None = None  # e.g. which defaults row was used

    @model_validator(mode="after")
    def _consistent(self):
        if self.status is Status.stated and not self.span:
            raise ValueError("stated field needs a source span")
        if self.status is Status.missing and self.value is not None:
            raise ValueError("missing field cannot carry a value")
        if self.status is Status.default and self.value is None:
            raise ValueError("default field needs a value")
        return self


class SetupSpec(BaseModel):
    vessel: str  # key in core.registry
    params: dict[str, Field]  # keys constrained per vessel (Vessel.params)
    source_text: str | None = None
    synthetic: bool = False
