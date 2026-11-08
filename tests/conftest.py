import pandas as pd
import pytest


@pytest.fixture
def sample_xlsx(tmp_path):
    """Создаёт временный .xlsx с двумя строками и возвращает путь."""
    df = pd.DataFrame({
        "Компания": ["Издание А", "Издание Б"],
        "Дата публикации": ["2026-09-01 10:00:00 +0300", "2026-09-02 11:00:00 +0300"],
        "Скачивание": ["2026-09-03 10:00:00 +0300", "2026-09-04 11:00:00 +0300"],
        "URL страницы файла": ["https://a/1", "https://b/2"],
        "Заголовок файла": ["Премьера фильма", "Матч по футболу"],
        "width": [3000, 2000],
        "height": [2000, 1000],
        "Архив": ["", ""],
    })
    path = tmp_path / "test.xlsx"
    df.to_excel(path, index=False)
    return str(path)


@pytest.fixture
def mock_llm(monkeypatch):
    """Мокает agent.get_llm, чтобы не ходить в GigaChat."""
    class FakeResponse:
        def __init__(self, content): self.content = content

    class FakeLLM:
        def __init__(self, content): self._content = content
        def invoke(self, prompt): return FakeResponse(self._content)

    def _set(content):
        monkeypatch.setattr("app.agent.get_llm", lambda temperature=0.1: FakeLLM(content))

    return _set