# Media Analyzer

Анализ скачиваний фотографий изданиями: ETL из Excel, топ-5 тем через LLM (GigaChat), кэш в Redis, API на FastAPI, дашборд на Streamlit.

## Что умеет

- Читает `.xlsx` со скачиваниями (издание, URL, заголовок, даты публикации и скачивания).
- Считает количество скачиваний по изданиям, собирает URL и заголовки.
- Просит LLM (GigaChat) определить ТОП-5 тем и ключевые слова для каждой.
- Детерминированно считает в Python, сколько заголовков попало в каждую тему.
- Отдаёт API: `/api/v1/themes`, `/api/v1/editions`, `/api/v1/url_titles`, `/api/v1/upload`, `/api/v1/session`.
- Кэширует ответы LLM в Redis (ключ по имени и `mtime` файлов).
- Показывает дашборд на Streamlit: метрики тем, таблица изданий, ссылки с темами.
- Покрыт тестами (`pytest`, 19 тестов) и CI (GitHub Actions).

## Стек

- **Python 3.12**
- **FastAPI** + **Uvicorn** — API
- **Streamlit** — дашборд
- **pandas** + **openpyxl** — чтение `.xlsx`
- **GigaChat** (через `langchain-gigachat`) — LLM
- **Redis** — кэш ответов LLM
- **Docker** + **Docker Compose** — запуск api + dashboard + redis
- **pytest** — тесты
- **GitHub Actions** — CI

## Структура проекта

```
media_analyzer/
├── app/
│   ├── __init__.py
│   ├── api.py            # FastAPI-приложение, эндпоинты
│   ├── agent.py          # вызов LLM, валидация ответа, подсчёт тем
│   ├── app.py            # GUI-оркестрация (pick_files → load → build)
│   ├── cache.py          # Redis-кэш (files_key по mtime)
│   ├── config.py         # .env, FILES, SID_RE, session-хелперы
│   ├── dashboard.py      # Streamlit-дашборд
│   ├── llm.py            # обёртка над GigaChat
│   ├── main.py           # load_titles (чтение .xlsx)
│   ├── parser.py         # парсинг (если используется)
│   ├── services.py       # load_data, build_result, human, compute_stats
│   ├── themes.py         # best_theme (STOPWORDS, веса)
│   └── ui.py             # tkinter-диалог выбора файлов
├── tests/
│   ├── conftest.py       # фикстуры: sample_xlsx, mock_llm
│   ├── test_agent.py
│   ├── test_api.py
│   ├── test_services.py
│   └── test_themes.py
├── static/
│   └── swagger/          # локальный Swagger UI (без CDN)
├── data/                 # .xlsx (в .gitignore)
├── .github/workflows/
│   ├── ci.yml            # pytest на push/PR
│   └── wake.yml          # пинг Streamlit-приложения
├── Dockerfile
├── Dockerfile.dashboard
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

## Быстрый старт (Docker)

1. Скопируй `.env.example` в `.env` и заполни:

   ```env
   GIGACHAT_CREDENTIALS=ваш_ключ
   GIGACHAT_SCOPE=GIGACHAT_API_PERS
   GIGACHAT_MODEL=GigaChat-Pro
   ```

2. Положи `.xlsx` со скачиваниями в `data/`.

3. Запусти:

   ```bash
   docker compose up -d --build
   ```

4. Открой:

   - API + Swagger: <http://localhost:8000/docs>
   - Дашборд: <http://localhost:8501>

## Запуск локально (без Docker)

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # Linux/macOS

pip install -e .
pip install pytest httpx python-multipart
```

Запуск API:

```bash
uvicorn app.api:app --reload --port 8000
# или, если установлен entry point:
media-analyzer
```

Запуск дашборда (в другом терминале):

```bash
streamlit run app/dashboard.py
```

> Для работы дашборда нужен запущенный API (по умолчанию `http://127.0.0.1:8000`). Redis — опционален: без него кэш не работает, но API продолжает отвечать.

## Переменные окружения

| Переменная | Обязательна | По умолчанию | Назначение |
|---|---|---|---|
| `GIGACHAT_CREDENTIALS` | да | — | Ключ авторизации GigaChat |
| `GIGACHAT_SCOPE` | нет | `GIGACHAT_API_PERS` | Scope GigaChat |
| `GIGACHAT_MODEL` | нет | `GigaChat-Pro` | Модель |
| `REDIS_HOST` | нет | `127.0.0.1` | Хост Redis (в Docker — `redis`) |
| `REDIS_PORT` | нет | `6379` | Порт Redis |

## API

### `GET /api/v1/themes`

ТОП-5 тем с количеством заголовков.

```json
{"themes": [{"name": "Выборы в Госдуму", "keywords": ["..."], "matched_count": 411}]}
```

Требует заголовок `X-Session-Id` (UUID).

### `GET /api/v1/editions`

Издания с количеством скачиваний и списком URL.

```json
{"rows": [{"Издание": "...", "Количество скачиваний": 422, "URL страницы файла": ["..."]}]}
```

### `GET /api/v1/url_titles`

URL → заголовок публикации (из `.xlsx`).

```json
{"rows": [{"url": "https://...", "title": "Премьера фильма ..."}]}
```

### `POST /api/v1/upload`

Загрузка `.xlsx` в сессию (multipart, до 25 МБ). Проверяет обязательные столбцы.

### `DELETE /api/v1/session`

Очищает файлы сессии.

## Тесты

```bash
pytest -v
```

Покрыто:

- `test_services.py` — `load_data`, `build_result`, `human`, `compute_stats`;
- `test_agent.py` — `get_themes_from_llm` (мок LLM), `analyze_themes`;
- `test_themes.py` — `best_theme` на реальных кейсах (`1491475`, `814282`, `1552274`, `октябрь`, `премии`);
- `test_api.py` — эндпоинты через `TestClient`.

CI: GitHub Actions (`.github/workflows/ci.yml`) запускает `pytest` на каждый push в `master`/`dev` и на PR.

## Ограничения и известные проблемы

- **Streamlit Community Cloud «засыпает»** после периода бездействия. Wake — `.github/workflows/wake.yml` (`curl` каждые 6 часов). Если `curl` не будит (Streamlit требует WebSocket), нужен headless-браузер (Playwright).
- **Темы определяются эвристикой**: `STOPWORDS` + веса в `app/themes.py`. Возможны ложные срабатывания; список стоп-слов пополняется по мере обнаружения.
- **LLM недетерминирован**: при `temperature=0.1` ответы стабильнее, но не гарантированы. Кэш в Redis снижает разброс.
- **`.xlsx` в `data/` не коммитятся** (`.gitignore`). Для демо — положи файлы локально.

## Разработка

- Код — в `app/`, тесты — в `tests/`.
- Запуск линтера (если добавишь `ruff`):

  ```bash
  ruff check app tests
  ```

- Форматирование: `ruff format app tests`.

## Лицензия

Внутренний проект. Не для публичного распространения.