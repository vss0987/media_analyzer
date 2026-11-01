import os
import re
import shutil
import time
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat-Pro")

if os.environ.get("VERCEL"):
    DATA_DIR = Path("/tmp/data")
else:
    DATA_DIR = Path(__file__).parent / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# Файлы клиентов хранятся по сессиям: data/sessions/<id>/*.xlsx
SESSIONS_DIR = DATA_DIR / "sessions"
SESSION_TTL_SEC = int(os.getenv("SESSION_TTL_MIN", "30")) * 60  # простой сессии до удаления
SID_RE = re.compile(r"^[0-9a-f]{32}$")


def session_dir(sid: str) -> Path:
    if not SID_RE.fullmatch(sid):
        raise ValueError("Некорректный идентификатор сессии")
    return SESSIONS_DIR / sid


def session_files(sid: str) -> list[str]:
    """Файлы сессии. Каждое обращение продлевает ей жизнь."""
    d = session_dir(sid)
    if not d.is_dir():
        return []
    os.utime(d, None)
    return [str(p) for p in sorted(d.glob("*.xlsx"))]


def drop_session(sid: str) -> None:
    shutil.rmtree(session_dir(sid), ignore_errors=True)


def cleanup_sessions() -> None:
    """Удаляет сессии, к которым не обращались дольше SESSION_TTL_SEC."""
    if not SESSIONS_DIR.is_dir():
        return
    now = time.time()
    for d in SESSIONS_DIR.iterdir():
        try:
            if d.is_dir() and now - d.stat().st_mtime > SESSION_TTL_SEC:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass

def get_files() -> list[str]:
    return [
        str(p) for p in sorted(DATA_DIR.glob("*.xlsx"))
        if p.name != "result.xlsx" and not p.name.startswith("~$")
    ]



class _LiveFiles(list):
    """Список файлов, который при каждом обращении перечитывает папку data.

    Нужен, чтобы код вида `from config import FILES` (например, в agent.py)
    видел файлы, загруженные уже после старта сервера.
    """

    def __iter__(self):
        return iter(get_files())

    def __len__(self):
        return len(get_files())

    def __bool__(self):
        return bool(get_files())

    def __getitem__(self, i):
        return get_files()[i]

    def __contains__(self, x):
        return x in get_files()

    def __repr__(self):
        return repr(get_files())


FILES = _LiveFiles()