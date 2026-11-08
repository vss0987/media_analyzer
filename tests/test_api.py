from unittest.mock import patch
from fastapi.testclient import TestClient
import uuid
SID = uuid.uuid4().hex

from api import app

client = TestClient(app)


def test_themes_ok():
    fake = [{"name": "T", "keywords": ["x"], "matched_count": 1}]
    with patch("api.check_llm_analysis", return_value=fake):
        r = client.get("/api/v1/themes", headers={"X-Session-Id": SID})
    assert r.status_code == 200


def test_editions_ok(sample_xlsx, monkeypatch):
    monkeypatch.setattr("api.session_files", lambda sid: [sample_xlsx])
    r = client.get("/api/v1/editions", headers={"X-Session-Id": SID})
    assert r.status_code == 200


def test_url_titles_ok(sample_xlsx, monkeypatch):
    monkeypatch.setattr("api.session_files", lambda sid: [sample_xlsx])
    r = client.get("/api/v1/url_titles", headers={"X-Session-Id": SID})
    assert r.status_code == 200