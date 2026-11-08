from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
from app.config import get_files

TITLE_CANDIDATES = ["Заголовок файла", "Заголовок", "Заголовки", "Название"]


def _find_title_column(df: pd.DataFrame) -> str | None:
    for c in TITLE_CANDIDATES:
        if c in df.columns:
            return c
    for col in df.columns:
        if "заголов" in str(col).lower():
            return col
    return None


def load_titles(files: Sequence[str] | None = None) -> pd.Series:
    if files is None:
        files = get_files()

    frames = []
    for f in files:
        try:
            df = pd.read_excel(f)
        except FileNotFoundError:
            print(f"✗ Файл не найден, пропускаю: {f}")
            continue

        col = _find_title_column(df)
        if col is None:
            print(f"✗ В файле {f} не найден столбец с заголовками, пропускаю")
            continue
        frames.append(df[col].rename("Заголовок"))

    if not frames:
        raise ValueError("Ни в одном файле не найден столбец с заголовками")
    return pd.concat(frames, ignore_index=True)