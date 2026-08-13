"""A4 Agent Chat API 测试：四道硬闸 + 端到端确定性兜底。

硬闸：
① 401：无 Bearer / 格式错误 / 无效 token → 401
② 422：message 缺失 / 空字符串 / 超 2000 字 → 422
③ 透传：API 序列化结果 == handle() 返回值逐字段一致（API 零加工）
④ 密钥隔离：API 源码不 import engine/httpx；不向前端返回 Provider 原始错误

铁律：API 层不得修改 AgentResponse，数字唯一来源是 Wealth Engine。
"""
from __future__ import annotations

import inspect

from app import db
from app.agent import FakeLLMProvider
from app.schemas.agent import AgentRequest, AgentResponse


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


# ---------- ① 401 闸 ----------

def test_agent_chat_requires_auth(client):
    assert client.post("/api/agent/chat", json={"message": "你好"}).status_code == 401
    # 格式错误（非 Bearer）
    assert client.post("/api/agent/chat", json={"message": "你好"},
                       headers={"Authorization": "Token abc"}).status_code == 401
    # 无效 token
    assert client.post("/api/agent/chat", json={"message": "你好"},
                       headers={"Authorization": "Bearer deadbeef"}).status_code == 401


# ---------- ② 422 闸 ----------

def test_agent_chat_message_missing(client, auth_headers):
    assert client.post("/api/agent/chat", json={}, headers=auth_headers).status_code == 422


def test_agent_chat_message_empty(client, auth_headers):
    assert client.post("/api/agent/chat", json={"message": ""}, headers=auth_headers).status_code == 422


def test_agent_chat_message_too_long(client, auth_headers):
    assert client.post("/api/agent/chat", json={"message": "好" * 2001},
                       headers=auth_headers).status_code == 422
    # 边界：2000 字合法，正常走 Agent 兜底（不 422）
    assert client.post("/api/agent/chat", json={"message": "好" * 2000},
                       headers=auth_headers).status_code == 200


# ---------- ③ 端到端：确定性兜底（无 key 不 500） ----------

def test_agent_chat_view_overview_no_key(client, auth_headers, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)   # 模拟未配置 key → NullProvider
    r = client.post("/api/agent/chat", json={"message": "看看我的家庭财富"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "VIEW_OVERVIEW"
    assert body["status"] == "ok"
    assert body["metrics"]
    for m in body["metrics"]:
        if m["value"] is not None:                     # 有值的指标必带 source
            assert m["source"] and m["source"].startswith("overview.")


def test_agent_chat_scenario_free_user_refused(client, auth_headers, monkeypatch):
    _seed(client, auth_headers)
    # 注入 FakeLLM 让参数提取成功 → 免费用户命中 VIP 门 → refused
    monkeypatch.setattr("app.api.agent.get_provider",
                        lambda: FakeLLMProvider([{"amount": 300000}]))
    r = client.post("/api/agent/chat", json={"message": "我想投资 30 万"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "refused"
    assert "upgrade" in body["next_actions"]


def test_agent_chat_scenario_compare_vip_ok(client, auth_headers, monkeypatch):
    _seed(client, auth_headers)
    _vip_user(client, auth_headers)
    monkeypatch.setattr("app.api.agent.get_provider",
                        lambda: FakeLLMProvider([{"amount": 300000, "to_class": "equity"}]))
    r = client.post("/api/agent/chat", json={"message": "我想投资 30 万到股票"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["metrics"]
    for m in body["metrics"]:
        if m["value"] is not None:                     # 数字只能来自 A2 工具（comparison.A.*）
            assert m["source"].startswith("comparison.A.")


# ---------- ④ 透传闸：API 零加工 ----------

def test_agent_chat_passthrough_verbatim(client, auth_headers, monkeypatch):
    fixed = AgentResponse(intent="CHECK_ALLOCATION", status="ok", summary="固定摘要",
                          finding="固定发现", metrics=[], recommendations=["r1"],
                          next_actions=["a1"], limitations=["l1"], source=["s1"])
    monkeypatch.setattr("app.api.agent.handle",
                        lambda message, user, llm=None, context=None: fixed)
    r = client.post("/api/agent/chat", json={"message": "看看我的配置"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == fixed.model_dump()              # 逐字段一致


# ---------- ⑤ 密钥隔离闸 ----------

def test_agent_api_source_has_no_engine_or_http():
    import app.api.agent as a
    src = inspect.getsource(a)
    for banned in ("engine", "httpx", "requests", "openai", "deepseek"):
        assert banned not in src


def test_agent_api_never_returns_raw_provider_error(client, auth_headers, monkeypatch):
    """Provider 内部异常被吞掉 → None → 兜底；原始错误/key 绝不外泄到前端。"""
    import app.agent.providers.deepseek as d

    def boom(*a, **k):
        raise RuntimeError("secret: sk-abc123 internal detail")

    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setattr(d.httpx, "post", boom)
    r = client.post("/api/agent/chat", json={"message": "看看我的家庭财富"}, headers=auth_headers)
    assert r.status_code == 200
    assert "secret" not in r.text
    assert "sk-fake" not in r.text
    assert "sk-abc123" not in r.text


def test_agent_request_schema():
    """AgentRequest 契约：message 必填 1~2000 字，context 可选。"""
    assert AgentRequest(message="你好").message == "你好"
    assert AgentRequest(message="你好").context is None
    assert AgentRequest(message="你好", context={"a": 1}).context == {"a": 1}
