import html
import os
import uuid

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Media Analyzer", page_icon="📰", layout="wide")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --muted: #8A94A0;
  --line: rgba(128,128,128,.25);
  --soft: rgba(128,128,128,.12);
  --accent: #14A89B;
}
html, body, [class*="css"], .stApp { font-family: 'Inter', system-ui, sans-serif; }
header[data-testid="stHeader"], footer, #MainMenu { display: none; }
.block-container { padding: 1.1rem 2rem 1rem; max-width: 1400px; }
div[data-testid="stVerticalBlock"] { gap: .7rem; }

/* шапка */
.top { display:flex; align-items:baseline; gap:.75rem; margin-bottom:.1rem; }
.top h1 { color:inherit; font-size:1.35rem; font-weight:700; margin:0; padding:0; letter-spacing:-.01em; }
.top span { color:var(--muted); font-size:.85rem; }

/* KPI */
.kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:.6rem; margin-bottom:1rem; }
.kpi { background:var(--soft); border-radius:10px; padding:.55rem .85rem; min-width:0; color:inherit; }
.kpi .v { color:inherit; font-size:1.35rem; font-weight:700; line-height:1.2; letter-spacing:-.01em;
          white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.kpi .l { font-size:.74rem; color:var(--muted); margin-top:1px; }

/* заголовки секций */
.sec { color:inherit; font-size:.9rem; font-weight:600; margin:0 0 .15rem; }
.sec small { color:var(--muted); font-weight:400; margin-left:.4rem; }

/* темы */
.theme { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:.1rem .6rem;
         align-items:center; padding:.32rem 0; border-bottom:1px solid var(--line); }
.theme:last-child { border-bottom:none; }
.theme .n { color:inherit; font-size:.84rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.theme .c { color:inherit; font-size:.84rem; font-weight:600; font-variant-numeric:tabular-nums; }
.theme .bar { grid-column:1 / -1; height:4px; background:var(--soft); border-radius:2px; overflow:hidden; }
.theme .bar i { display:block; height:100%; background:var(--accent); border-radius:2px; }

/* поля и вкладки */
div[data-testid="stHorizontalBlock"] { margin-top:.6rem; }
div[data-testid="stTextInput"] input { border-radius:8px; font-size:.88rem; }
button[data-baseweb="tab"] { padding:.3rem .9rem; font-size:.88rem; }
div[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:10px; overflow:hidden; }
.empty { color:var(--muted); font-size:.85rem; padding:.6rem 0; }
</style>
<script defer src="https://cdn.vercel-insights.com/v1/script.js"></script>
""",
    unsafe_allow_html=True,
)


# ---------- данные ----------
# Каждая сессия браузера (обновление страницы = новая сессия) работает
# только со своими файлами. sid и ver — часть ключа st.cache_data,
# поэтому кэш не пересекается между клиентами и сбрасывается после загрузки.

st.session_state.setdefault("sid", uuid.uuid4().hex)
st.session_state.setdefault("data_ver", 0)
SID = st.session_state.sid
HEADERS = {"X-Session-Id": SID}


@st.cache_data(ttl=300)
def load_editions(sid: str, ver: int) -> list[dict]:
    r = requests.get(f"{API_URL}/api/v1/editions", headers={"X-Session-Id": sid}, timeout=30)
    r.raise_for_status()
    return r.json()["rows"]


@st.cache_data(ttl=300)
def load_url_titles(sid: str, ver: int) -> dict[str, str]:
    r = requests.get(f"{API_URL}/api/v1/url_titles", headers={"X-Session-Id": sid}, timeout=30)
    r.raise_for_status()
    return {x["url"]: x["title"] for x in r.json()["rows"]}


@st.cache_data(ttl=300)
def load_themes(sid: str, ver: int) -> list[dict]:
    r = requests.get(f"{API_URL}/api/v1/themes", headers={"X-Session-Id": sid}, timeout=120)
    if not r.ok:  # показываем причину от API, а не только код ответа
        try:
            detail = r.json().get("detail")
        except ValueError:
            detail = None
        raise requests.HTTPError(f"{r.status_code}: {detail or r.reason}")
    return r.json()["themes"]


try:
    rows = load_editions(SID, st.session_state.data_ver)
    url_titles = load_url_titles(SID, st.session_state.data_ver)
except requests.RequestException as e:
    st.error(f"API недоступен ({API_URL}): {e}")
    st.stop()

df = pd.DataFrame(
    {
        "Издание": [x["Издание"] for x in rows],
        "Скачиваний": [x["Количество скачиваний"] for x in rows],
    }
)
urls_by_edition = {x["Издание"]: (x.get("URL страницы файла") or []) for x in rows}
total_links = sum(len(v) for v in urls_by_edition.values())


# ---------- шапка и KPI ----------

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
st.session_state.setdefault("uploader_n", 0)
if msg := st.session_state.pop("upload_msg", None):
    st.toast(msg, icon="✅")


def _error_text(r: requests.Response) -> str:
    try:
        detail = r.json().get("detail")
        if isinstance(detail, str):
            return detail
    except ValueError:
        pass
    return f"ошибка {r.status_code}"


def upload_files(files) -> tuple[list[str], list[str]]:
    done, failed = [], []
    for f in files:
        try:
            r = requests.post(
                f"{API_URL}/api/v1/upload",
                files={"file": (f.name, f.getvalue(), XLSX_MIME)},
                headers=HEADERS,
                timeout=120,
            )
        except requests.RequestException:
            failed.append(f"{f.name}: API недоступен")
            continue
        if r.ok:
            j = r.json()
            done.append(f"{f.name} — {j['rows']} строк" + (" (заменён)" if j["replaced"] else ""))
        else:
            failed.append(f"{f.name}: {_error_text(r)}")
    return done, failed


@st.dialog("Загрузить файл")
def upload_dialog(has_data: bool):
    uploaded = st.file_uploader(
        "Excel со скачиваниями",
        type=["xlsx"],
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_n}",
        label_visibility="collapsed",
    )
    st.caption(
        "Столбцы: Компания, Дата публикации, Скачивание, URL страницы файла, "
        "Заголовок файла. Данные видны только в этой сессии: после обновления "
        "страницы файл нужно загрузить заново."
    )
    if st.button("Добавить в данные", type="primary", disabled=not uploaded, use_container_width=True):
        with st.spinner("Загружаю…"):
            done, failed = upload_files(uploaded)
        if done:
            st.session_state.data_ver += 1
            parts = ["Загружено: " + "; ".join(done)]
            if failed:
                parts.append("Не загружено: " + "; ".join(failed))
            st.session_state.upload_msg = "\n".join(parts)
            st.session_state.uploader_n += 1  # сбрасываем виджет
            st.rerun()  # перезапуск закрывает окно
        for line in failed:
            st.error(line)
    if has_data and st.button("Очистить данные", use_container_width=True):
        requests.delete(f"{API_URL}/api/v1/session", headers=HEADERS, timeout=30)
        st.session_state.data_ver += 1
        st.session_state.uploader_n += 1
        st.rerun()


head_l, head_r = st.columns([5, 1.4], vertical_alignment="center")
with head_l:
    st.markdown(
        '<div class="top"><h1>Media Analyzer</h1><span>скачивания материалов по изданиям</span></div>',
        unsafe_allow_html=True,
    )
with head_r:
    if st.button("Загрузить файл", use_container_width=True):
        upload_dialog(bool(rows))

top_name = df.iloc[0]["Издание"] if len(df) else "—"
kpis = [
    (f"{len(df):,}".replace(",", " "), "изданий"),
    (f"{int(df['Скачиваний'].sum()):,}".replace(",", " "), "скачиваний"),
    (f"{total_links:,}".replace(",", " "), "уникальных ссылок"),
    (html.escape(str(top_name)), "лидер по скачиваниям"),
]
st.markdown(
    '<div class="kpis">'
    + "".join(f'<div class="kpi"><div class="v">{v}</div><div class="l">{l}</div></div>' for v, l in kpis)
    + "</div>",
    unsafe_allow_html=True,
)


# ---------- основная область ----------

left, right = st.columns([3, 2], gap="medium")

with left:
    query = st.text_input(
        "Поиск", placeholder="Найти издание…", label_visibility="collapsed"
    )
    view = df[df["Издание"].str.contains(query, case=False, na=False, regex=False)] if query else df
    view = view.reset_index(drop=True)

    event = st.dataframe(
        view,
        hide_index=True,
        height=430,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Издание": st.column_config.TextColumn("Издание", width="large"),
            "Скачиваний": st.column_config.ProgressColumn(
                "Скачиваний",
                format="%d",
                min_value=0,
                max_value=int(df["Скачиваний"].max()) if len(df) else 1,
                width="medium",
            ),
        },
    )
    if len(df):
        st.caption(f"Показано {len(view)} из {len(df)} · клик по строке открывает ссылки издания")
    else:
        st.info("Данных пока нет. Нажмите «Загрузить файл» в правом верхнем углу и добавьте Excel со скачиваниями.")

selected = None
if len(view):
    picked = event.selection.rows
    selected = view.iloc[picked[0]]["Издание"] if picked else view.iloc[0]["Издание"]

with right:
    tab_links, tab_themes = st.tabs(["Ссылки", "Темы"])

    with tab_links:
        if selected is None:
            st.markdown('<div class="empty">Ничего не найдено — измените запрос.</div>', unsafe_allow_html=True)
        else:
            urls = urls_by_edition.get(selected, [])
            st.markdown(
                f'<div class="sec">{html.escape(str(selected))}<small>{len(urls)} ссылок</small></div>',
                unsafe_allow_html=True,
            )
            if urls:
                st.dataframe(
                    pd.DataFrame({"Заголовок": [url_titles.get(u, "—") for u in urls], "Ссылка": urls}),
                    hide_index=True,
                    height=400,
                    use_container_width=True,
                    column_config={
                        "Заголовок": st.column_config.TextColumn("Заголовок", width="medium"),
                        "Ссылка": st.column_config.LinkColumn(
                            "Ссылка", display_text=r"https?://(?:www\.)?([^/]+)", width="small"
                        ),
                    },
                )
            else:
                st.markdown('<div class="empty">У этого издания нет ссылок.</div>', unsafe_allow_html=True)

    themes_box = tab_themes.container()


# Темы считает LLM и могут грузиться долго — рисуем их последними,
# чтобы остальная страница появлялась сразу.
with themes_box:
    themes = None
    if rows:
        with st.spinner("LLM анализирует темы…"):
            try:
                themes = load_themes(SID, st.session_state.data_ver)
            except requests.RequestException as e:
                st.warning(f"Не удалось получить темы: {e}")
    else:
        st.markdown('<div class="empty">Загрузите файл со скачиваниями — темы появятся после анализа.</div>', unsafe_allow_html=True)

    if themes:
        themes = sorted(themes, key=lambda t: t.get("matched_count", 0), reverse=True)
        peak = max((t.get("matched_count", 0) for t in themes), default=0) or 1
        st.markdown(
            "".join(
                f'<div class="theme"><span class="n">{html.escape(str(t["name"]))}</span>'
                f'<span class="c">{t.get("matched_count", 0)}</span>'
                f'<div class="bar"><i style="width:{t.get("matched_count", 0) / peak * 100:.0f}%"></i></div></div>'
                for t in themes
            ),
            unsafe_allow_html=True,
        )
    elif themes is not None:
        st.markdown('<div class="empty">Темы пока не определены.</div>', unsafe_allow_html=True)