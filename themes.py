import re
from collections import Counter

STOPWORDS = {
    "январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август",
    "сентябрь", "октябрь", "ноябрь", "декабрь",
    "москва", "москве", "москвы", "россия", "россии", "город", "городе",
    "день", "года", "год", "году",
    # общие слова, которые LLM кладёт в разные темы:
    "премия", "премии", "премий", "премию",
    "акция", "акции", "акций", "акцию",
    "конференция", "конференции", "форум", "форуме",
    "мероприятие", "мероприятия", "проект", "проекта",
    "встреча", "встречи", "открытие", "открытия",
    "конкурс", "конкурса", "выставка", "выставки",
    "герой", "герои", "героев", "героям", "героя",
    "спорт", "спорта", "спорту", "спорте", "спортивный", "спортивная", "спортивные",
    "гимнастика", "гимнастики", "гимнастике",
    "винер",
    "ии",
}


def _is_stopword(k: str) -> bool:
    kl = k.lower()
    return any(sw in kl for sw in STOPWORDS)


def _word_theme_count(themes: list[dict]) -> Counter:
    c = Counter()
    for t in themes:
        for k in set(k.lower() for k in t["keywords"] if k):
            c[k] += 1
    return c


def best_theme(title: str, themes: list[dict]) -> str | None:
    lower = title.lower()
    wtc = _word_theme_count(themes)
    best_name, best_score = None, 0.0

    for t in themes:
        kws = [
            k.lower() for k in t["keywords"]
            if k and len(k) >= 4 and not _is_stopword(k)
        ]
        score = 0.0
        for k in kws:
            if re.search(rf"\b{re.escape(k)}", lower):
                score += len(k) / wtc.get(k, 1)
        if score > best_score:
            best_name, best_score = t["name"], score

    return best_name