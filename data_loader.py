from __future__ import annotations

from typing import Optional
import pandas as pd

HEADER_KEYWORDS = {"reseña", "resena", "review", "comentario", "texto", "opinion", "opinión", "comment", "feedback"}

def _looks_like_header_row(row_values: list[str]) -> bool:
    vals = [("" if v is None else str(v)).strip().lower() for v in row_values]
    hits = sum(1 for v in vals if v in HEADER_KEYWORDS or v in {"estado", "criterio de moderación", "criterio de moderacion"})
    non_empty = sum(1 for v in vals if v)
    return hits >= 1 and non_empty >= 2

def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cols = []
    for c in df.columns:
        c2 = "" if c is None else str(c).strip()
        if not c2:
            c2 = "columna"
        cols.append(c2)
    df.columns = cols
    return df

def load_reviews_to_dataframe(file_storage) -> pd.DataFrame:
    filename = file_storage.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "csv":
        try:
            return pd.read_csv(file_storage, dtype=str)
        except UnicodeDecodeError:
            file_storage.stream.seek(0)
            return pd.read_csv(file_storage, dtype=str, encoding="latin-1")

    file_storage.stream.seek(0)
    df_raw = pd.read_excel(file_storage, header=None, dtype=str)

    header_row_idx: Optional[int] = None
    for i in range(min(len(df_raw), 10)):
        if _looks_like_header_row(df_raw.iloc[i].tolist()):
            header_row_idx = i
            break

    if header_row_idx is None:
        file_storage.stream.seek(0)
        return pd.read_excel(file_storage, dtype=str)

    header = [("" if v is None else str(v)).strip() for v in df_raw.iloc[header_row_idx].tolist()]
    df = df_raw.iloc[header_row_idx + 1 :].copy()
    df.columns = [h if h else f"col_{idx}" for idx, h in enumerate(header)]
    df = df.dropna(how="all")
    return df

def add_correlativo_and_clean_empty_col(df: pd.DataFrame, correlativo_name: str = "Correlativo") -> pd.DataFrame:
    out = df.copy()

    drop_candidates = []
    for c in out.columns:
        cn = str(c).strip().lower()
        if cn in {"col_0", "columna", "unnamed: 0", "nan"} or cn.startswith("unnamed:"):
            drop_candidates.append(c)
    for c in drop_candidates:
        s = out[c]
        empties = s.isna() | (s.astype(str).str.strip() == "") | (s.astype(str).str.lower() == "nan")
        if float(empties.mean()) >= 0.80:
            out = out.drop(columns=[c])

    name = correlativo_name
    if name in out.columns:
        i = 2
        while f"{name} {i}" in out.columns:
            i += 1
        name = f"{name} {i}"

    out.insert(0, name, range(1, len(out) + 1))
    return out
