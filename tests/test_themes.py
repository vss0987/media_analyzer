import pytest
from app.themes import best_theme


def _themes():
    return [
        {"name": "Спорт", "keywords": ["марафон", "забег", "турнир", "героев спорта", "гимнастики"]},
        {"name": "Кино и театр", "keywords": ["премьера", "фильм", "триллер", "кинотеатр", "актер", "концерт", "гала-концерт"]},
        {"name": "Погода", "keywords": ["погода", "дождь", "октябрь"]},
        {"name": "Культура", "keywords": ["выставка", "музей", "вернисаж"]},
    ]


def test_shurale_is_cinema():
    title = "Актер Рузиль Минекаев ... на премьере мистического триллера «Шурале» ... в кинотеатре «Октябрь»."
    assert best_theme(title, _themes()) == "Кино и театр"


def test_ecological_awards_not_sport():
    title = "Исполнительный директор ... экологическим премиям правительства Москвы."
    assert best_theme(title, _themes()) is None


def test_gala_concert_not_sport():
    title = "Гала-концерт IV Всероссийской премии «Мы верим твердо в героев спорта» во Дворце гимнастики Ирины Винер."
    assert best_theme(title, _themes()) in (None, "Кино и театр")
    assert best_theme(title, _themes()) != "Спорт"


def test_october_not_weather():
    title = "Премьера фильма в кинотеатре «Октябрь»."
    assert best_theme(title, _themes()) != "Погода"


def test_marathon_is_sport():
    title = "Московский марафон собрал тысячи участников."
    assert best_theme(title, _themes()) == "Спорт"


def test_none_for_unknown():
    title = "Совершенно нейтральный заголовок без ключевых слов."
    assert best_theme(title, _themes()) is None