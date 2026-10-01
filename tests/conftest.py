import pytest
from fastapi.testclient import TestClient

from backend import common
from backend.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATABASE", tmp_path / "sessions.sqlite")
    monkeypatch.setattr(common, "BUDGET", tmp_path / "budget.sqlite")
    with TestClient(app) as c:
        c.headers.update({"Origin": "http://testserver", "X-Coach-Request": "1"})
        c.get("/api/session")
        yield c
