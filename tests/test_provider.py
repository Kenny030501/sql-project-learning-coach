import json

import httpx
import pytest

from backend import common, providers


@pytest.fixture
def configured(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "BUDGET", tmp_path / "budget.sqlite")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-real")
    monkeypatch.setenv("PAID_CALLS_ENABLED", "true")
    monkeypatch.setenv("TEXT_PROVIDER", "deepseek")
    monkeypatch.setenv("TEXT_MODEL", "deepseek-chat")
    providers.CATALOG.clear()


def test_real_adapter_with_http_stub(configured, monkeypatch):
    def handler(req):
        if req.url.path == "/models":
            return httpx.Response(200, json={"data": [{"id": "deepseek-chat"}]})
        body = json.loads(req.content)
        assert body["model"] == "deepseek-chat"
        return httpx.Response(
            200,
            json={
                "model": "deepseek-chat",
                "choices": [{"message": {"content": '{"answer":"ok"}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            },
        )

    real = httpx.Client
    monkeypatch.setattr(
        providers.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)
    )
    assert providers.call_json("test", {}) == {"answer": "ok"}
    assert common.budget_status()["requests"] == 1
    assert common.budget_status()["estimated_or_reserved_usd"] > 0


def test_bad_provider_response_is_not_success(configured, monkeypatch):
    def handler(req):
        if req.url.path == "/models":
            return httpx.Response(200, json={"data": [{"id": "deepseek-chat"}]})
        return httpx.Response(503, json={"error": "upstream unavailable"})

    real = httpx.Client
    monkeypatch.setattr(
        providers.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)
    )
    with pytest.raises(ValueError, match="请求失败"):
        providers.call_json("test", {})
    assert common.budget_status()["estimated_or_reserved_usd"] > 0
