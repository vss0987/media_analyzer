from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from collections.abc import Sequence

import pandas as pd
from app.config import get_files


FMT = "%Y-%m-%d %H:%M:%S %z"
COMPANY_COL = "Компания"
URL_COL = "URL страницы файла"
TITLE_COL = "Заголовок файла"
PUB_COL = "Дата публикации"
DL_COL = "Скачивание"
REQUIRED_COLS = [COMPANY_COL, PUB_COL, DL_COL, URL_COL, TITLE_COL]


def missing_columns(df: pd.DataFrame) -> list[str]:
    """Обязательные столбцы, которых нет в файле."""
    return [c for c in REQUIRED_COLS if c not in df.columns]


# ---------- загрузка ----------

def load_data(files: Sequence[str] | None = None) -> pd.DataFrame:
    if files is None:
        files = get_files()
    frames = []
    for f in files:
        if not Path(f).exists():
            print(f"✗ Файл не найден, пропускаю: {f}")
            continue
        df = pd.read_excel(f)
        df[PUB_COL] = pd.to_datetime(df[PUB_COL], format=FMT, errors="coerce", utc=True)
        df[DL_COL] = pd.to_datetime(df[DL_COL], format=FMT, errors="coerce", utc=True)
        df["pub_dt"] = df[PUB_COL]
        df["dl_dt"] = df[DL_COL]
        df["elapsed"] = df["dl_dt"] - df["pub_dt"]
        frames.append(df)

    if not frames:  # папка data пуста — это не ошибка, просто данных ещё нет
        return pd.DataFrame(columns=REQUIRED_COLS + ["pub_dt", "dl_dt", "elapsed"])
    return pd.concat(frames, ignore_index=True)


# ---------- агрегаты ----------

def build_result(data: pd.DataFrame) -> pd.DataFrame:
    """Считает количество скачиваний по изданиям + собирает URL и первый заголовок."""
    total = Counter(data[COMPANY_COL].dropna())
    urls: dict[str, dict[str, None]] = defaultdict(dict)
    titles: dict[str, str] = {}  # Издание -> первый непустой заголовок

    if URL_COL in data.columns and TITLE_COL in data.columns:
        for company, url, title in zip(data[COMPANY_COL], data[URL_COL], data[TITLE_COL]):
            if pd.notna(company):
                if pd.notna(url):
                    urls[company].setdefault(url, None)
                if company not in titles and pd.notna(title):
                    titles[company] = str(title).strip()

    result = pd.DataFrame(
        total.most_common(),
        columns=["Издание", "Количество скачиваний"],
    )
    result["Заголовок файла"] = result["Издание"].map(titles)
    result["URL страницы файла"] = result["Издание"].map(
        lambda x: list(urls.get(x, []))
    )
    return result

def get_lst(data: pd.DataFrame) -> dict[str, int]:
    """Словарь {издание: количество скачиваний}."""
    return dict(Counter(data[COMPANY_COL].dropna()).most_common())


# ---------- время ----------

def human(delta: pd.Timedelta) -> str:
    """'5 лет 11 мес. 7 дн.'"""
    if pd.isna(delta):
        return "—"
    total_seconds = int(delta.total_seconds())
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)
    total_days = total_seconds // 86400
    years = total_days // 365
    months = (total_days % 365) // 30
    days = total_days - years * 365 - months * 30
    hours = (total_seconds % 86400) // 3600
    parts = []
    if years: parts.append(f"{years} г.")
    if months: parts.append(f"{months} мес.")
    if days: parts.append(f"{days} дн.")
    if not parts:
        parts.append(f"{hours} ч.")
    return sign + " ".join(parts)


def compute_stats(data: pd.DataFrame) -> dict:
    """Возвращает словарь со статистикой (без печати)."""
    valid = data.dropna(subset=["pub_dt", "dl_dt"]).copy()
    valid = valid[valid["elapsed"] >= pd.Timedelta(0)]

    if valid.empty:
        return {"total_rows": len(data), "valid_rows": 0, "skipped": len(data)}

    mean_elapsed = valid["elapsed"].mean()
    min_row = valid.loc[valid["elapsed"].idxmin()]
    max_row = valid.loc[valid["elapsed"].idxmax()]

    return {
        "total_rows": len(data),
        "valid_rows": len(valid),
        "skipped": len(data) - len(valid),
        "mean_elapsed": mean_elapsed,
        "min_elapsed": valid["elapsed"].min(),
        "max_elapsed": valid["elapsed"].max(),
        "min_row": min_row,
        "max_row": max_row,
    }


def format_stats(stats: dict) -> str:
    lines = [
        "=" * 70,
        "ВРЕМЯ ОТ ПУБЛИКАЦИИ ДО СКАЧИВАНИЯ",
        "=" * 70,
        f"Всего строк в файлах:               {stats['total_rows']}",
        f"Строк с датой публикации (учтено):  {stats['valid_rows']}",
        f"Строк без даты публикации (пропуск): {stats['skipped']}",
        "",
    ]
    if stats["valid_rows"] == 0:
        lines.append("Нет валидных строк для статистики.")
        return "\n".join(lines)

    mean_elapsed = stats["mean_elapsed"]
    min_row, max_row = stats["min_row"], stats["max_row"]
    lines += [
        f"Среднее время:  {human(mean_elapsed)}",
        f"                ({mean_elapsed.total_seconds()/86400:,.1f} дней)",
        "",
        f"Минимальная разница:  {human(stats['min_elapsed'])}",
        f"  материал:   {min_row[TITLE_COL]}",
        f"  издание:    {min_row[COMPANY_COL]}",
        f"  опубликован: {min_row['pub_dt']:%d.%m.%Y %H:%M}",
        f"  скачан:      {min_row['dl_dt']:%d.%m.%Y %H:%M}",
        "",
        f"Максимальная разница: {human(stats['max_elapsed'])}",
        f"  материал:   {max_row[TITLE_COL]}",
        f"  издание:    {max_row[COMPANY_COL]}",
        f"  опубликован: {max_row['pub_dt']:%d.%m.%Y %H:%M}",
        f"  скачан:      {max_row['dl_dt']:%d.%m.%Y %H:%M}",
    ]

    result = "\n".join(lines)
    return result


if __name__ == "__main__":
    data = load_data()
    build_result(data).to_excel("result.xlsx", index=False)
    print(format_stats(compute_stats(data)))