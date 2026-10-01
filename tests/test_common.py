import pytest

from backend import common, providers


def test_origin_guard(client):
    r = client.delete("/api/session", headers={"Origin": "https://example.com"})
    assert r.status_code == 403


def test_delete_is_session_scoped(client):
    client.get("/api/session")
    assert client.delete("/api/session").status_code == 200
    assert client.get("/api/session").json() == {"revision": 0}


def test_budget_shared_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "BUDGET", tmp_path / "budget.sqlite")
    common.reserve("deepseek", "test", 4.9)
    with pytest.raises(ValueError, match="预算"):
        common.reserve("xai", "test", 0.2)
    assert common.budget_status()["requests"] == 1


def test_missing_key_no_fake_reply(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ValueError, match="未调用AI"):
        providers.call_json("test", {}, "deepseek")
