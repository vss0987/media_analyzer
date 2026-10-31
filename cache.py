# cache.py
import hashlib
import json
import os
from pathlib import Path

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=0,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)


def cache_get(key: str) -> list[dict] | None:
    try:
        raw = r.get(key)
    except redis.RedisError:
        return None
    return json.loads(raw) if raw else None


def cache_set(key: str, value: list[dict], ttl_seconds: int = 3600) -> None:
    try:
        r.set(key, json.dumps(value, ensure_ascii=False), ex=ttl_seconds)
    except redis.RedisError:
        pass


def titles_key(titles) -> str:
    """Ключ по содержимому заголовков (оставлен для совместимости)."""
    h = hashlib.sha256("\n".join(sorted(set(titles))).encode()).hexdigest()
    return f"themes:{h}"


def files_key(files) -> str:
    """Ключ по содержимому файлов (sha256 байтов).

    Не зависит ни от имени файла, ни от времени загрузки: тот же файл,
    загруженный повторно (в том числе в новой сессии), попадёт в тот же кэш.
    """
    hashes = []
    for f in files:
        try:
            hashes.append(hashlib.sha256(Path(f).read_bytes()).hexdigest())
        except OSError:
            hashes.append("missing")
    h = hashlib.sha256("\n".join(sorted(hashes)).encode()).hexdigest()
    return f"themes:{h}"