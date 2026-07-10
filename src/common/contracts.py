"""Pydantic data contracts + frame validation. Loaded frames are validated on load and
fail loudly on drift (missing columns, wrong dtypes, broken keys)."""

from __future__ import annotations

from typing import Type

import pandas as pd
from pydantic import BaseModel


class ContractViolation(Exception):
    """Raised when a frame does not satisfy its data contract."""


def validate_frame(
    df: pd.DataFrame,
    model: Type[BaseModel],
    name: str,
    sample_rows: int = 200,
) -> pd.DataFrame:
    """Validate a frame against a pydantic row model.

    - All contract fields must exist as columns.
    - A sample of rows (head+tail) is instantiated through the model so type errors surface.
    Returns the frame unchanged on success; raises ContractViolation on failure.
    """
    missing = [f for f in model.model_fields if f not in df.columns]
    if missing:
        raise ContractViolation(f"{name}: missing contract columns {missing}")

    if len(df):
        sample = pd.concat([df.head(sample_rows // 2), df.tail(sample_rows // 2)])
        for record in sample.to_dict(orient="records"):
            try:
                model.model_validate({k: (None if pd.isna(v) else v) for k, v in record.items()
                                      if k in model.model_fields})
            except Exception as exc:  # noqa: BLE001 - re-raise with context
                raise ContractViolation(f"{name}: row failed contract: {exc}\nrow={record}") from exc
    return df
