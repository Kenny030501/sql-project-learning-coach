import json
import os

import httpx

from backend.common import reserve, settle

BASES = {"deepseek": "https://api.deepseek.com", "zhipu": "https://open.bigmodel.cn/api/paas/v4"}
KEYS = {"deepseek": "DEEPSEEK_API_KEY", "zhipu": "ZHIPU_API_KEY"}
CATALOG = {}
LAST_USAGE = {}


def provider_status():
    provider = os.environ.get("TEXT_PROVIDER", "deepseek")
    return {
        "provider": provider,
        "model": os.environ.get("TEXT_MODEL", "待核验账号模型"),
        "text_key_available": bool(os.environ.get(KEYS.get(provider, ""), "")),
        "speech_key_available": bool(os.environ.get("XAI_API_KEY")),
        "paid_enabled": os.environ.get("PAID_CALLS_ENABLED", "false").lower() == "true",
    }


def config(provider=None):
    provider = provider or os.environ.get("TEXT_PROVIDER", "deepseek")
    if provider not in BASES:
        raise ValueError("仅支持DeepSeek/智谱官方文本服务")
    key = os.environ.get(KEYS[provider], "")
    if not key:
        raise ValueError(f"请在本地配置{KEYS[provider]}；当前未调用AI，也没有用模拟结果替代。")
    return provider, BASES[provider], key


def model_catalog(provider=None):
    provider, base, key = config(provider)
    try:
        with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
            r = client.get(base + "/models", headers={"Authorization": "Bearer " + key})
            r.raise_for_status()
            names = [m["id"] for m in r.json()["data"]]
    except (httpx.HTTPError, KeyError, TypeError):
        raise ValueError("无法核验账号模型列表，请检查官方API权限。") from None
    return names


def select_model(provider):
    requested = (
        os.environ.get("TEXT_MODEL")
        if provider == os.environ.get("TEXT_PROVIDER", "deepseek")
        else os.environ.get("ZHIPU_MODEL", "glm-4.7-flash")
    )
    cache_key = (provider, requested)
    if cache_key in CATALOG:
        return CATALOG[cache_key]
    names = model_catalog(provider)
    options = (
        [requested]
        if requested
        else ["deepseek-chat", "deepseek-v4.1-flash", "deepseek-v4-flash", "deepseek-flash"]
    )
    model = next((x for x in options if x in names), None)
    if not model:
        raise ValueError("配置模型不在账号模型列表中。请运行check_models.py核验并填写TEXT_MODEL。")
    CATALOG[cache_key] = model
    return model


def call_json(system, payload, provider=None):
    provider, base, key = config(provider)
    if os.environ.get("PAID_CALLS_ENABLED", "false").lower() != "true":
        raise ValueError("付费调用未启用；请在本地配置PAID_CALLS_ENABLED=true。")
    model = select_model(provider)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    in_rate = float(os.environ.get("INPUT_USD_PER_M", "10"))
    out_rate = float(os.environ.get("OUTPUT_USD_PER_M", "30"))
    if min(in_rate, out_rate) <= 0:
        raise ValueError("调用前须配置正的保守单价")
    maximum = 2200
    # UTF-8 byte count plus framing over-reserves typical BPE input usage.
    estimated_input = len(json.dumps(messages, ensure_ascii=False).encode()) + 1024
    ticket = reserve(provider, model, (estimated_input * in_rate + maximum * out_rate) / 1e6)
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": maximum,
        "response_format": {"type": "json_object"},
    }
    try:
        with httpx.Client(timeout=50, follow_redirects=False, trust_env=False) as client:
            r = client.post(
                base + "/chat/completions", headers={"Authorization": "Bearer " + key}, json=body
            )
            r.raise_for_status()
            result = r.json()
        usage = result.get("usage", {})
        if "prompt_tokens" in usage and "completion_tokens" in usage:
            charge = (
                usage["prompt_tokens"] * in_rate + usage["completion_tokens"] * out_rate
            ) / 1e6
            settle(ticket, charge)
        else:
            settle(ticket, None, "completed_usage_unknown")
        LAST_USAGE.update(
            provider=provider, model=result.get("model", model), usage=usage, ticket=ticket
        )
        output = json.loads(result["choices"][0]["message"]["content"])
        if not isinstance(output, dict):
            raise ValueError("模型未返回JSON对象")
        return output
    except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError):
        settle(ticket, None, "failed_or_invalid_response")
        raise ValueError("模型请求失败、超时或返回格式无效；没有生成有效结果。") from None


def transcribe(audio, filename, seconds):
    key = os.environ.get("XAI_API_KEY", "")
    if not key or os.environ.get("PAID_CALLS_ENABLED", "false").lower() != "true":
        raise ValueError("语音服务未配置或付费调用未启用；可先输入文字测试流程。")
    model = "grok-voice-transcribe-2.0"
    ticket = reserve("xai", model, max(seconds, 1) / 3600 * 0.10)
    try:
        with httpx.Client(timeout=50, trust_env=False, follow_redirects=False) as client:
            r = client.post(
                "https://api.x.ai/v1/stt",
                headers={"Authorization": "Bearer " + key},
                data={"model": model, "format": "true"},
                files={"file": (filename, audio, "application/octet-stream")},
            )
            r.raise_for_status()
            data = r.json()
        text = data.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("音频没有识别出有效文字。")
        settle(ticket, max(float(data.get("duration", seconds)), 1) / 3600 * 0.10)
        return {"text": text, "model": model, "duration": seconds}
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        settle(ticket, None, "failed_or_invalid_response")
        raise ValueError("语音转写失败或没有可识别语音，请重录或手动输入。") from None
