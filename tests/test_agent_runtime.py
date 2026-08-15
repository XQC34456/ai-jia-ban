"""A3.1 Agent Runtime 测试：七意图封闭 / C3.5 参数封闭 / A2 工具封闭 / 四错误封闭 /
拒算两出口 / metrics value→source / limitations 逐字 / 仅 Fake+Null / 零 engine。

约束：A3 只取数·识别·映射·引用·解释，绝不加工·再计算·自行产出财富数字。
"""
from __future__ import annotations

import inspect

import pytest

from app import db
from app.agent import (
    LLMProvider, NullProvider, FakeLLMProvider,
    refusal_gate, route_intent,
    ParamResult, extract_scenario_params,
    dispatch, map_tool_error,
    build_metrics, known_limitations_of,
    handle,
)
from app.agent.tools import ToolError, get_overview
from app.schemas.agent import AGENT_INTENTS, AgentResponse
from app.schemas.scenario import SCENARIO_METRIC_KEYS


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


# ---------- ① 拒算门：两条出口封闭 ----------

def test_refusal_gate_translates_to_invest():
    assert refusal_gate("帮我算 10 年后资产有多少") == {"scenario": "invest"}


def test_refusal_gate_disambiguates_pure_calc():
    assert refusal_gate("帮我算 100 万复利 20 年是多少") == {"disambiguate": True}


def test_refusal_gate_not_compute():
    assert refusal_gate("我的养老够不够") is None


# ---------- ② 意图路由：七意图封闭 ----------

def test_route_intent_deterministic():
    assert route_intent("我的养老够不够") == "CHECK_RETIREMENT"
    assert route_intent("看看我的资产配置") == "CHECK_ALLOCATION"
    assert route_intent("我有什么风险问题") == "CHECK_ISSUES"
    assert route_intent("孩子教育金目标") == "CHECK_GOALS"
    assert route_intent("为什么我的评分低") == "EXPLAIN_RESULT"
    assert route_intent("如果买套房会怎样") == "SCENARIO_COMPARE"
    assert route_intent("随便聊聊天") == "VIEW_OVERVIEW"       # 兜底


def test_route_intent_unemployment_liquidity():
    # 失业/撑多久 = 流动性风险 → CHECK_ISSUES（应急资金月数 emergency_months）
    assert route_intent("如果我失业半年能撑多久") == "CHECK_ISSUES"
    assert route_intent("我失业了能撑多久") == "CHECK_ISSUES"


def test_route_intent_prepay_car_loan_scenario():
    # 「提前还车贷」的「车」夹在「还」「贷」之间，旧关键词「提前还贷/还贷」匹配不到 → 曾落 LLM 兜底不稳定
    assert route_intent("我该不该提前还车贷") == "SCENARIO_COMPARE"
    assert route_intent("我该不该提前还房贷") == "SCENARIO_COMPARE"


def test_route_intent_surplus_investment_allocation():
    # 「剩下的钱怎么投」= 结余配置，非目标非情景 → 确定性 CHECK_ALLOCATION（曾落 LLM 兜底不稳定）
    assert route_intent("我每个月剩下的钱应该怎么投") == "CHECK_ALLOCATION"


def test_route_intent_llm_fallback():
    llm = FakeLLMProvider(router_script=[{"intent": "CHECK_ALLOCATION"}])
    assert route_intent("帮我看看理财结构", llm) == "CHECK_ALLOCATION"


def test_route_intent_llm_invalid_falls_back():
    llm = FakeLLMProvider(router_script=[{"intent": "HACK"}])
    assert route_intent("随便聊聊", llm) == "VIEW_OVERVIEW"    # 非法 → 兜底


def test_route_intent_closed_set():
    msgs = ["养老", "配置", "风险", "目标", "解释", "买房", "你好"]
    for m in msgs:
        assert route_intent(m) in AGENT_INTENTS


# ---------- ③ 参数提取：C3.5 契约封闭 + 绝不脑补 ----------

def test_extract_params_complete():
    llm = FakeLLMProvider([{"amount": 300000, "to_class": "equity"}])
    pr = extract_scenario_params("我想投资 30 万到股票", llm)
    assert pr.scenario == "invest"
    assert pr.params == {"amount": 300000, "to_class": "equity"}
    assert pr.missing == []


def test_extract_params_alias_resolution():
    llm = FakeLLMProvider([{"price": 3000000}])
    pr = extract_scenario_params("我想买套 300 万的房", llm)
    assert pr.scenario == "buy_house"


def test_extract_params_missing_required():
    llm = FakeLLMProvider([{"to_class": "equity"}])           # 只给可选字段，缺必填 amount
    pr = extract_scenario_params("我想投资", llm)
    assert pr.params is None                                  # 不填默认值
    assert "投资金额（元）" in pr.missing


def test_extract_params_no_llm_returns_missing():
    pr = extract_scenario_params("我想投资", NullProvider())
    assert pr.scenario == "invest"
    assert pr.params is None
    assert "投资金额（元）" in pr.missing


def test_extract_params_unknown_scenario():
    pr = extract_scenario_params("随便聊聊", NullProvider())
    assert pr.params is None
    assert pr.missing                              # 场景未识别 → 追问


# ---------- ④ 工具分派：A2 工具封闭 ----------

def test_dispatch_maps_intents(client, auth_headers):
    _seed(client, auth_headers)
    u = _user(auth_headers)
    assert "wealth_score" in dispatch("VIEW_OVERVIEW", u)
    assert "issues" in dispatch("CHECK_ISSUES", u)
    assert "goals" in dispatch("CHECK_GOALS", u)
    assert "retirement" in dispatch("CHECK_RETIREMENT", u)
    assert "asset_allocation" in dispatch("CHECK_ALLOCATION", u)
    assert dispatch("EXPLAIN_RESULT", u) is None


# ---------- ⑤ 错误映射：四种 ToolError 封闭 ----------

def test_map_tool_error_four_kinds():
    assert map_tool_error("forbidden")[0] == "refused"
    assert map_tool_error("unknown_scenario")[0] == "need_clarification"
    assert map_tool_error("invalid_params")[0] == "need_clarification"
    assert map_tool_error("unexecutable")[0] == "refused"
    assert map_tool_error("forbidden")[2] == ["upgrade"]      # 结构化升级动作


# ---------- ⑥ metrics value→source 封闭 ----------

def test_build_metrics_every_value_has_source(client, auth_headers):
    _seed(client, auth_headers)
    o = get_overview(_user(auth_headers))
    for intent in ("VIEW_OVERVIEW", "CHECK_RETIREMENT", "CHECK_ALLOCATION"):
        for m in build_metrics(intent, o):
            assert m.value is not None and m.source is not None
            assert m.source.startswith("overview.")


# ---------- ⑦ limitations 逐字透传 ----------

def test_known_limitations_verbatim(client, auth_headers):
    _seed(client, auth_headers)
    o = get_overview(_user(auth_headers))
    expected = o["retirement"]["known_limitations"]
    assert expected                                    # 有 person + 支出 → 非空
    assert known_limitations_of(o) == expected         # 逐字相等


# ---------- ⑧ 守门：仅 Fake/Null，零 engine ----------

def test_provider_only_fake_and_null():
    import app.agent.provider as p
    src = inspect.getsource(p)
    for sdk in ("deepseek", "openai", "anthropic", "requests", "httpx"):
        assert sdk not in src.lower()
    assert hasattr(p, "LLMProvider") and hasattr(p, "NullProvider") and hasattr(p, "FakeLLMProvider")


def test_agent_layer_does_not_import_engine():
    import app.agent.runtime as rt
    import app.agent.router as r
    import app.agent.params as pr
    import app.agent.response as resp
    import app.agent.dispatch as d
    for mod in (rt, r, pr, resp, d):
        assert "engine" not in inspect.getsource(mod)


# ---------- 端到端 handle() ----------

def test_handle_view_overview(client, auth_headers):
    resp = handle("看看我的家庭财富", _user(auth_headers), llm=NullProvider())
    assert isinstance(resp, AgentResponse)
    assert resp.intent == "VIEW_OVERVIEW" and resp.status == "ok"
    assert resp.metrics and all(m.source for m in resp.metrics)


def test_handle_scenario_compare_ok(client, auth_headers):
    _seed(client, auth_headers)
    llm = FakeLLMProvider([{"amount": 300000, "to_class": "equity"}])
    resp = handle("我想投资 30 万到股票", _vip_user(client, auth_headers), llm=llm)
    assert resp.intent == "SCENARIO_COMPARE" and resp.status == "ok"
    assert [m.key for m in resp.metrics] == list(SCENARIO_METRIC_KEYS)   # 九指标按序


def test_handle_scenario_missing_params(client, auth_headers):
    resp = handle("我想投资", _vip_user(client, auth_headers), llm=NullProvider())
    assert resp.status == "need_clarification"
    assert "投资金额" in resp.summary


def test_handle_disambiguate_pure_calc(client, auth_headers):
    resp = handle("帮我算 100 万复利 20 年", _user(auth_headers), llm=NullProvider())
    assert resp.status == "need_clarification"
    assert "复利" in resp.summary


def test_handle_forbidden_free_user(client, auth_headers):
    llm = FakeLLMProvider([{"amount": 300000}])
    resp = handle("我想投资 30 万", _user(auth_headers), llm=llm)
    assert resp.status == "refused"
    assert "upgrade" in resp.next_actions


# ---------- P0 修复 B：router 注入记忆上下文（指代消解） ----------

class _SpyRouter(FakeLLMProvider):
    def __init__(self, intent="CHECK_RETIREMENT"):
        super().__init__(router_script=[{"intent": intent}])
        self.seen_user = None

    def complete_json(self, system, user, schema, context=None):
        self.seen_user = user
        return super().complete_json(system, user, schema, context)


def test_route_intent_injects_memory_for_coreference():
    """router 支持 memory_context：指代消解所需的历史被注入 LLM prompt。"""
    spy = _SpyRouter()
    route_intent("这笔钱怎么安排", spy,
                 memory_context="【近期对话】\n用户:「给父母留养老钱」")
    assert "给父母留养老钱" in spy.seen_user


def test_handle_passes_memory_context_to_router(client, auth_headers, monkeypatch):
    """runtime 层：handle 确实把 memory_context 透传给 route_intent（防「router 支持但 runtime 忘传」）。"""
    captured = {}

    def _spy_route(message, llm=None, wealth_context=None, memory_context=None):
        captured["memory_context"] = memory_context
        return "CHECK_RETIREMENT"

    monkeypatch.setattr("app.agent.runtime.route_intent", _spy_route)
    handle("看看我的养老", _user(auth_headers), llm=NullProvider(),
           memory_context="【近期对话】用户:「给父母留养老钱」")
    assert "给父母留养老钱" in (captured["memory_context"] or "")
