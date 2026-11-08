from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Sequence

import pandas as pd

from app.cache import cache_get, cache_set, files_key
from app.config import get_files
from app.llm import get_llm
from app.main import load_titles

MAX_TITLES_FOR_PROMPT = 100
MAX_THEMES = 10


class LLMError(RuntimeError):
    """LLM не вернул валидный ответ. API-слой должен отдать 502."""


# ---------- LLM ----------

MAX_LLM_CALLS = 30   # предохранитель: сколько запросов можно потратить на поиск «чистых» заголовков
MIN_CHUNK = 8        # меньше этого число заголовков уже не делим — отбрасываем


def _build_prompt(titles: list[str]) -> str:
    titles_block = "\n".join(f"- {t}" for t in titles)
    return (
        "Ниже список заголовков публикаций.\n"
        f"Определи ТОП-{MAX_THEMES} тем по семантике и для каждой темы верни "
        "список ключевых слов/подстрок, по которым заголовки можно отнести к этой теме.\n"
        "ВАЖНО:\n"
        "- НЕ используй слова, которые встречаются во всех темах: месяцы (январь...декабрь), "
        "дни недели, «Москва», «Россия», «город», «день», «год», «премия», «акция», "
        "«конференция», «форум», «мероприятие», «проект», «встреча», «открытие».\n"
        "- НО используй общие слова, специфичные для темы: для «Кино и театр» — "
        "премьера, фильм, спектакль, актер, режиссер, кинотеатр, театр, сериал, триллер; "
        "для «Культура и искусство» — выставка, музей, вернисаж, экспозиция, художник, картина; "
        "для «Спорт» — матч, забег, турнир, соревнование, чемпионат; и т.д.\n"
        "- Ключевые слова должны быть длиной не менее 4 символов.\n"
        "Верни СТРОГО JSON без пояснений и markdown в формате:\n"
        '{"themes": [{"name": "тема", "keywords": ["слово1", "слово2", ...]}, ...]}\n\n'
        f"{titles_block}"
    )


def _ask_llm(prompt: str) -> str:
    try:
        return get_llm(temperature=0.1).invoke(prompt).content.strip()
    except Exception as e:
        raise LLMError(f"Ошибка вызова LLM: {type(e).__name__}: {e}") from e


def _parse_themes(raw: str) -> list[dict] | None:
    """Темы из ответа LLM. None — ответ не удалось разобрать
    (например, сработал фильтр GigaChat и вместо JSON пришла отписка)."""
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()
    # LLM иногда добавляет пояснения вокруг JSON — берём то, что между крайними скобками
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        raw = raw[start:end + 1]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    themes = data.get("themes") if isinstance(data, dict) else None
    if not isinstance(themes, list):
        return None

    validated: list[dict] = []
    for theme in themes[:MAX_THEMES]:
        if not isinstance(theme, dict):
            print(f"✗ Пропускаю тему не-словарь: {theme!r}")
            continue
        name = theme.get("name")
        keywords = theme.get("keywords")
        if not isinstance(name, str) or not name.strip():
            print(f"✗ Пропускаю тему без name: {theme!r}")
            continue
        if not isinstance(keywords, list):
            print(f"✗ Тема {name!r}: keywords не список, пропускаю")
            continue
        keywords = [str(k).strip() for k in keywords if str(k).strip()]
        validated.append({"name": name.strip(), "keywords": keywords})
    return validated or None


def _collect_themes(titles: list[str], budget: dict) -> list[dict]:
    """Спрашивает LLM про заголовки. Если ответ не JSON (фильтр чувствительных тем),
    делит список пополам и повторяет — так «проблемные» заголовки отсеиваются,
    а остальные дают темы."""
    if budget["calls"] >= MAX_LLM_CALLS:
        return []
    budget["calls"] += 1

    themes = _parse_themes(_ask_llm(_build_prompt(titles)))
    if themes is not None:
        return themes
    if len(titles) <= MIN_CHUNK:
        print(f"✗ LLM отклонил заголовки, пропускаю: {titles}")
        return []
    mid = len(titles) // 2
    return _collect_themes(titles[:mid], budget) + _collect_themes(titles[mid:], budget)


def _merge_themes(themes: list[dict]) -> list[dict]:
    """Объединяет темы с одинаковым названием (после деления списка они повторяются)."""
    merged: dict[str, dict] = {}
    for t in themes:
        entry = merged.setdefault(t["name"].lower(), {"name": t["name"], "keywords": []})
        seen = {k.lower() for k in entry["keywords"]}
        for k in t["keywords"]:
            if k.lower() not in seen:
                entry["keywords"].append(k)
                seen.add(k.lower())
    return list(merged.values())[:MAX_THEMES]


def get_themes_from_llm(titles: pd.Series) -> list[dict]:
    """Вызывает LLM и возвращает [{"name": str, "keywords": [str]}, ...].

    Бросает LLMError, если LLM недоступен или не вернул ни одной темы.
    """
    top = [t for t, _ in Counter(titles).most_common(MAX_TITLES_FOR_PROMPT)]
    themes = _merge_themes(_collect_themes(top, {"calls": 0}))
    if not themes:
        raise LLMError(
            "LLM не вернул ни одной темы: ответы отклонены его фильтром "
            "или пришли не в формате JSON"
        )
    return themes


# ---------- подсчёт ----------

def analyze_themes(titles: pd.Series, themes: list[dict]) -> list[dict]:
    """Считает, сколько заголовков попало в каждую тему.

    Возвращает [{"name", "keywords", "matched_count"}, ...].
    """
    lower_titles = titles.str.lower()
    result: list[dict] = []

    for theme in themes:
        kws = [re.escape(k.lower()) for k in theme["keywords"] if k]
        if not kws:
            # пустой keywords → "".join → str.contains("") → True для всех строк.
            # Явно обрабатываем: тема покрывает 0 заголовков.
            print(f"✗ Тема {theme['name']!r}: пустой список keywords, matched=0")
            result.append({
                "name": theme["name"],
                "keywords": theme["keywords"],
                "matched_count": 0,
            })
            continue

        pattern = "|".join(kws)
        matched = titles[lower_titles.str.contains(pattern, regex=True, na=False)]
        result.append({
            "name": theme["name"],
            "keywords": theme["keywords"],
            "matched_count": int(len(matched)),
        })

    return result


# ---------- оркестрация ----------

def check_llm_analysis(files: Sequence[str] | None = None) -> list[dict] | None:
    """Загружает заголовки, спрашивает LLM, считает темы.

    Кэш проверяется по файлам (имя + mtime) ДО чтения Excel —
    повторный запрос не читает .xlsx.

    Возвращает список тем с matched_count или None, если заголовков нет.
    Бросает LLMError, если LLM не ответил / вернул мусор.
    """
    files = get_files() if files is None else list(files)
    if not files:
        return None

    key = files_key(files)
    cached = cache_get(key)
    if cached is not None:
        return cached

    try:
        titles = load_titles(files).dropna().astype(str).str.strip()
    except ValueError:  # ни в одном файле нет столбца с заголовками
        return None
    titles = titles[titles != ""]
    if titles.empty:
        return None

    themes = get_themes_from_llm(titles)
    result = analyze_themes(titles, themes)
    cache_set(key, result)
    return result


if __name__ == "__main__":
    result = check_llm_analysis()
    if result is None:
        print("Нет заголовков для анализа")
    else:
        for t in result:
            print(f"{t['name']} — {t['matched_count']} заголовков")
            print(f"   ключевые слова: {', '.join(t['keywords'])}\n")