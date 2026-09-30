from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Iterable

import pandas as pd


def canonical_col(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [canonical_col(c) for c in out.columns]
    return out


def resolve_column(columns: Iterable[str], candidates: Iterable[str], required: bool = True) -> str | None:
    cols = {canonical_col(c): c for c in columns}
    for candidate in candidates:
        key = canonical_col(candidate)
        if key in cols:
            return cols[key]
    if required:
        raise KeyError(f"Could not find any of {list(candidates)} in columns {list(columns)}")
    return None


def read_csv_flexible(path_or_buffer, **kwargs) -> pd.DataFrame:
    defaults = dict(dtype=str, keep_default_na=False, na_values=[])
    defaults.update(kwargs)
    try:
        return pd.read_csv(path_or_buffer, sep=";", encoding="utf-8", **defaults)
    except UnicodeDecodeError:
        return pd.read_csv(path_or_buffer, sep=";", encoding="latin-1", **defaults)
    except Exception:
        if hasattr(path_or_buffer, "seek"):
            path_or_buffer.seek(0)
        return pd.read_csv(path_or_buffer, sep=None, engine="python", **defaults)


def read_first_csv_from_zip(zip_path: str | Path, chunksize: int | None = None):
    zf = zipfile.ZipFile(zip_path)
    csv_names = [n for n in zf.namelist() if n.lower().endswith((".csv", ".txt"))]
    if not csv_names:
        raise FileNotFoundError(f"No CSV/TXT file found in {zip_path}")
    raw = zf.open(csv_names[0], "r")
    text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")
    if chunksize:
        return pd.read_csv(text, sep=";", dtype=str, keep_default_na=False, chunksize=chunksize)
    return pd.read_csv(text, sep=";", dtype=str, keep_default_na=False)
