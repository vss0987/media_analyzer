import ast
import io
import logging
import os
import re
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from agent import check_llm_analysis, LLMError
from config import (
    SID_RE, cleanup_sessions, drop_session, session_dir, session_files,
)
from services import (
    load_data, build_result, missing_columns, REQUIRED_COLS, URL_COL, TITLE_COL,
)

app = FastAPI(title="Media Analyzer", docs_url=None)
# app = FastAPI(title="Media Analyzer")

RESULT_XLSX = Path(__file__).parent / "result.xlsx"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
log = logging.getLogger("media_analyzer")


def _parse_urls(val):
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = ast.literal_eval(val)
            return parsed if isinstance(parsed, list) else [val]
        except (ValueError, SyntaxError):
            return [val] if val else []
    return []


def get_sid(x_session_id: str = Header(...)) -> str:
    if not SID_RE.fullmatch(x_session_id):
        raise HTTPException(status_code=400, detail="Некорректный идентификатор сессии")
    return x_session_id


@app.get("/api/v1/editions")
def editions(sid: str = Depends(get_sid)):
    data = load_data(session_files(sid))
    result = build_result(data)
    rows = result.to_dict(orient="records")
    # заменяем NaN/NaT на None, чтобы JSON был валидным
    for row in rows:
        for k, v in row.items():
            if isinstance(v, float) and v != v:  # NaN
                row[k] = None
            elif v is pd.NaT:
                row[k] = None
    return {"rows": rows}


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
    "ии",  # на всякий случай, хотя len < 4
}


def best_theme(title: str, themes: list[dict]) -> str | None:
    lower = title.lower()
    best_name, best_score = None, 0
    for t in themes:
        kws = [
            k.lower() for k in t["keywords"]
            if k and len(k) >= 4 and k.lower() not in STOPWORDS
        ]
        score = 0
        for k in kws:
            if re.search(rf"\b{re.escape(k)}", lower):
                score += 1
        if score > best_score:
            best_name, best_score = t["name"], score
    return best_name


@app.get("/api/v1/url_titles")
def url_titles(sid: str = Depends(get_sid)):
    data = load_data(session_files(sid))
    url_title = {}
    for url, title in zip(data[URL_COL], data[TITLE_COL]):
        if pd.notna(url) and pd.notna(title) and url not in url_title:
            url_title[url] = str(title).strip()
    return {"rows": [{"url": u, "title": t} for u, t in url_title.items()]}


@app.get("/api/v1/themes")
def themes(sid: str = Depends(get_sid)):
    files = session_files(sid)
    if not files:
        return {"themes": []}
    try:
        result = check_llm_analysis(files)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:  # причина попадёт и в лог контейнера, и в дашборд
        log.exception("Ошибка анализа тем")
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}") from e
    if result is None:
        return {"themes": []}
    return {"themes": result}


def _safe_filename(name: str | None) -> str:
    n = Path(name or "").name.strip()
    if not n.lower().endswith(".xlsx") or n.startswith("~$") or n.lower() == "result.xlsx":
        raise HTTPException(status_code=400, detail="Нужен файл .xlsx (не result.xlsx)")
    return n


@app.post("/api/v1/upload")
def upload(file: UploadFile = File(...), sid: str = Depends(get_sid)):
    """Принимает Excel со скачиваниями, проверяет столбцы и кладёт в data/."""
    name = _safe_filename(file.filename)
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Файл больше 25 МБ")

    try:
        df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail="Не удалось прочитать Excel-файл") from e

    missing = missing_columns(df)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Нет столбцов: {', '.join(missing)}. Нужны: {', '.join(REQUIRED_COLS)}",
        )
    if df.empty:
        raise HTTPException(status_code=422, detail="В файле нет строк")

    cleanup_sessions()  # заодно убираем чужие просроченные сессии
    folder = session_dir(sid)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    replaced = target.exists()
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(content)
    os.replace(tmp, target)  # атомарно: читатели не увидят полузаписанный файл

    return {"filename": name, "rows": len(df), "replaced": replaced}


@app.delete("/api/v1/session")
def clear_session(sid: str = Depends(get_sid)):
    """Удаляет все файлы этой сессии."""
    drop_session(sid)
    return {"cleared": True}


STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Media Analyzer - Swagger UI</title>
        <link rel="stylesheet" type="text/css" href="/static/swagger/swagger-ui.css" />
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="/static/swagger/swagger-ui-bundle.js" charset="UTF-8"></script>
        <script>
        window.onload = function() {{
            window.ui = SwaggerUIBundle({{
                url: "/openapi.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis
                ]
            }});
        }};
        </script>
        <script defer src="https://cdn.vercel-insights.com/v1/script.js"></script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


def main() -> None:
    """Точка входа для `media-analyzer` (см. [project.scripts])."""
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()