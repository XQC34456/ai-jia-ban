"""A3.2 DeepSeek Provider 测试：五道硬闸。

① Provider 隔离（核心层不 import HTTP/SDK，只有 deepseek.py 可以）
② 模型名配置化（不硬编码具体型号）
③ LLM 输出结构化（response_format=json_object，返回 dict）
④ LLM 数字不能成为财富数字来源（夹带伪造数字必被丢弃）
⑤ 失败安全降级（超时/HTTP/非 JSON → None → 确定性兜底）
"""
from __future__ import annotations

import importlib
import inspect

import httpx
import pytest

from app import db
from app.agent import FakeLLMProvider, NullProvider, extract_scenario_params, handle

# 核心 Agent 文件（A3.2 红线：不得 import HTTP / SDK）
_CORE_MODULES = (
    "app.agent.runtime",
    "app.agent.router",
    "app.agent.params",
    "app.agent.response",
    "app.agent.provider",
    "app.agent.providers",
)


def _token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def _user(headers: dict) -> dict:
    return db.get_user_by_token(_token(headers))


def _vip_user(client, headers) -> dict:
    client.post("/api/upgrade", headers=headers)
    return db.get_user_by_token(_token(headers))


def _seed(client, headers):
    client.post("/api/family/entity/person", headers=headers,
                json={"name": "本人", "relation": "本人", "birth_year": 1990})
    client.post("/api/family/entity/asset", headers=headers,
                json={"type": "存款", "name": "现金", "value": 1500000})
    client.post("/api/family/entity/asset", headers=headers,
                json={"type": "股票", "name": "股票", "value": 1500000})
    client.post("/api/family/entity/liability", headers=headers,
                json={"type": "房贷", "name": "房贷", "principal": 2000000,
                      "monthly_payment": 12000, "interest_rate": 0.035, "remaining_months": 240})
    client.post("/api/family/entity/cashflow", headers=headers,
                json={"flow_type": "income", "amount": 50000, "period": "月"})
    client.post("/api/family/entity/cashflow", headers=headers,
                json={"flow_type": "expense", "amount": 20000, "period": "月"})


class _FakeResp:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


class _ErrorResp:
    def raise_for_status(self):
        raise RuntimeError("http error")


# ---------- ① Provider 隔离 ----------

def test_core_agent_files_do_not_import_http_sdk():
    for name in _CORE_MODULES:
        mod = importlib.import_module(name)
        src = inspect.getsource(mod)
        for sdk in ("httpx", "requests", "openai"):
            assert sdk not in src, f"{name} 不得 import {sdk}"


def test_only_deepseek_module_imports_http():
    import app.agent.providers.deepseek as d
    assert "httpx" in inspect.getsource(d).lower()


# ---------- ② 模型名配置化 ----------

def test_no_hardcoded_model_name():
    import app.agent.providers.deepseek as d
    import app.agent.providers as prov
    for mod in (d, prov):
        src = inspect.getsource(mod)
        assert "deepseek-v4-pro" not in src
        assert "deepseek-chat" not in src          # 不冻结具体型号
    # 模型名必须来自 LLM_MODEL 配置
    assert "LLM_MODEL" in inspect.getsource(prov)


# ---------- ③ 结构化输出 ----------

def test_complete_json_requests_json_object_and_parses(monkeypatch):
    import app.agent.providers.deepseek as d
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        captured["headers"] = kwargs["headers"]
        return _FakeResp('{"intent": "CHECK_ALLOCATION"}')

    monkeypatch.setattr(d.httpx, "post", fake_post)
    provider = d.DeepSeekProvider(api_key="sk-test", model="test-model")

    result = provider.complete_json("sys", "user msg",
                                    {"type": "object",
                                     "properties": {"intent": {"type": "string"}},
                                     "required": ["intent"]})

    assert result == {"intent": "CHECK_ALLOCATION"}     # 返回 dict，不是字符串
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["json"]["model"] == "test-model"
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert "intent" in captured["json"]["messages"][0]["content"]   # schema 注入 system


# ---------- ④ LLM 数字不能成为财富数字来源 ----------

def test_llm_extra_wealth_numbers_discarded():
    """LLM 夹带 wealth_score_after → C3.5 校验后必被丢弃。"""
    llm = FakeLLMProvider([{"amount": 300000, "to_class": "equity",
                            "wealth_score_after": 9999}])
    pr = extract_scenario_params("我想投资 30 万到股票", llm)
    assert pr.params == {"amount": 300000, "to_class": "equity"}
    assert "wealth_score_after" not in pr.params


def test_handle_metrics_never_from_llm(client, auth_headers):
    """端到端：即使 LLM 伪造财富数字，AgentResponse 数值也只能来自 A2 工具。"""
    _seed(client, auth_headers)
    llm = FakeLLMProvider([{"amount": 300000, "to_class": "equity",
                            "wealth_score_after": 9999}])
    resp = handle("我想投资 30 万到股票", _vip_user(client, auth_headers), llm=llm)
    assert resp.status == "ok"
    assert resp.metrics
    for m in resp.metrics:
        assert m.value != 9999
        if m.value is not None:                      # 有值的指标必须带 A2 来源路径
            assert m.source and m.source.startswith("comparison.A.")


# ---------- ⑤ 失败安全降级 ----------

def test_complete_json_timeout_returns_none(monkeypatch):
    import app.agent.providers.deepseek as d

    def fake_post(*a, **k):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(d.httpx, "post", fake_post)
    provider = d.DeepSeekProvider(api_key="k", model="m")
    assert provider.complete_json("s", "u", {}) is None


def test_complete_json_http_error_returns_none(monkeypatch):
    import app.agent.providers.deepseek as d
    monkeypatch.setattr(d.httpx, "post", lambda *a, **k: _ErrorResp())
    provider = d.DeepSeekProvider(api_key="k", model="m")
    assert provider.complete_json("s", "u", {}) is None


def test_complete_json_bad_json_returns_none(monkeypatch):
    import app.agent.providers.deepseek as d
    monkeypatch.setattr(d.httpx, "post", lambda *a, **k: _FakeResp("not json"))
    provider = d.DeepSeekProvider(api_key="k", model="m")
    assert provider.complete_json("s", "u", {}) is None


def test_complete_json_non_dict_returns_none(monkeypatch):
    import app.agent.providers.deepseek as d
    monkeypatch.setattr(d.httpx, "post", lambda *a, **k: _FakeResp('["a", "b"]'))
    provider = d.DeepSeekProvider(api_key="k", model="m")
    assert provider.complete_json("s", "u", {}) is None


def test_get_provider_missing_key_returns_null(monkeypatch):
    from app.agent.providers import get_provider
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_MODEL", "m")
    assert isinstance(get_provider(), NullProvider)


def test_get_provider_missing_model_returns_null(monkeypatch):
    from app.agent.providers import get_provider
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert isinstance(get_provider(), NullProvider)


def test_get_provider_wrong_provider_returns_null(monkeypatch):
    from app.agent.providers import get_provider
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    assert isinstance(get_provider(), NullProvider)


def test_get_provider_deepseek_ok(monkeypatch):
    from app.agent.providers import get_provider, DeepSeekProvider
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    assert isinstance(get_provider(), DeepSeekProvider)
