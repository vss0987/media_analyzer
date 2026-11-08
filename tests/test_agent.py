import json
import pandas as pd
import pytest

from app.agent import get_themes_from_llm, analyze_themes, check_llm_analysis, LLMError


def test_get_themes_valid_json(mock_llm):
    mock_llm(json.dumps({"themes": [
        {"name": "Тема A", "keywords": ["a", "b"]},
        {"name": "Тема B", "keywords": ["c"]},
    ]}))
    result = get_themes_from_llm(pd.Series(["a", "b", "c"]))
    assert len(result) == 2
    assert result[0]["name"] == "Тема A"


def test_get_themes_invalid_json(mock_llm):
    mock_llm("не json")
    with pytest.raises(LLMError, match="не вернул ни одной темы"):
        get_themes_from_llm(pd.Series(["x"]))


def test_get_themes_empty_list(mock_llm):
    mock_llm('{"themes": []}')
    with pytest.raises(LLMError, match="не вернул ни одной темы"):
        get_themes_from_llm(pd.Series(["x"]))


def test_analyze_themes_counts():
    titles = pd.Series(["Премьера фильма", "Матч по футболу", "Выставка"])
    themes = [
        {"name": "Кино", "keywords": ["премьера", "фильм"]},
        {"name": "Спорт", "keywords": ["матч", "футбол"]},
    ]
    result = analyze_themes(titles, themes)
    assert result[0]["matched_count"] == 1  # "Премьера фильма"
    assert result[1]["matched_count"] == 1  # "Матч по футболу"


def test_analyze_themes_empty_keywords():
    titles = pd.Series(["a", "b"])
    themes = [{"name": "Пусто", "keywords": []}]
    result = analyze_themes(titles, themes)
    assert result[0]["matched_count"] == 0
