"""A1 Agent 契约冻结守门测试：锁定意图/端点映射/场景别名/输出 Schema。

约束：只 import app.schemas（契约层），不 import app.engine / app.services / app.api，
绝不涉及 LLM 或计算逻辑。Agent 是交互智能层，不是财富计算层。
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import (
    AGENT_INTENTS, INTENT_TO_ENDPOINT, INTENT_SUBFIELD, SCENARIO_ALIASES,
    SCENARIO_NAMES, AgentResponse, MetricRef,
)


# ---------- ① 七意图冻结 ----------

def test_intents_frozen_seven():
    assert AGENT_INTENTS == (
        "VIEW_OVERVIEW", "CHECK_ISSUES", "CHECK_RETIREMENT", "CHECK_ALLOCATION",
        "CHECK_GOALS", "SCENARIO_COMPARE", "EXPLAIN_RESULT",
    )


# ---------- ② 意图 → 唯一端点（LLM 永不自由拼 endpoint） ----------

def test_intent_endpoint_unique():
    """除 EXPLAIN_RESULT 外每个意图唯一映射到已存在路由；EXPLAIN_RESULT 无端点。"""
    assert set(INTENT_TO_ENDPOINT) == set(AGENT_INTENTS)
    assert INTENT_TO_ENDPOINT["EXPLAIN_RESULT"] is None
    for intent in AGENT_INTENTS:
        if intent == "EXPLAIN_RESULT":
            continue
        method, path = INTENT_TO_ENDPOINT[intent]
        assert method in ("GET", "POST")
        assert path.startswith("/api/wealth/")


def test_retirement_allocation_read_overview():
    """CHECK_RETIREMENT / CHECK_ALLOCATION 读 /overview 子区块，不新增端点。"""
    assert INTENT_TO_ENDPOINT["CHECK_RETIREMENT"] == ("GET", "/api/wealth/overview")
    assert INTENT_TO_ENDPOINT["CHECK_ALLOCATION"] == ("GET", "/api/wealth/overview")
    assert INTENT_SUBFIELD["CHECK_RETIREMENT"] == "retirement"
    assert INTENT_SUBFIELD["CHECK_ALLOCATION"] == "asset_allocation"


def test_compare_intent_is_vip_post():
    """SCENARIO_COMPARE 唯一映射到 POST compare 路由（VIP，A2 接权限）。"""
    assert INTENT_TO_ENDPOINT["SCENARIO_COMPARE"] == ("POST", "/api/wealth/scenario/{name}/compare")


# ---------- 场景别名：受 SCENARIO_NAMES 约束 ----------

def test_scenario_aliases_match_frozen_names():
    """别名值必须受 SCENARIO_NAMES 约束，Agent 层不自行扩展场景。"""
    assert set(SCENARIO_ALIASES.values()) <= set(SCENARIO_NAMES)
    assert SCENARIO_ALIASES["买房"] == "buy_house"
    assert SCENARIO_ALIASES["提前还贷"] == "prepay"
    assert SCENARIO_ALIASES["投股票"] == "invest"
    assert SCENARIO_ALIASES["收入下降"] == "income_change"


# ---------- ④ 输出 Schema 防编造闸门 ----------

def test_metric_ref_value_requires_source():
    """带 value 无 source → 拒绝；无 value 可无 source。"""
    with pytest.raises(ValidationError):
        MetricRef(key="rfr", label="RFR", unit="ratio", value=0.85)
    ok = MetricRef(key="rfr", label="RFR", unit="ratio", value=0.85, source="overview.retirement.rfr")
    assert ok.source == "overview.retirement.rfr"
    no_value = MetricRef(key="rfr", label="RFR", unit="ratio")
    assert no_value.value is None and no_value.source is None


def test_agent_response_minimal_ok():
    """最小合法对象可通过 Schema 校验。"""
    r = AgentResponse.model_validate({
        "intent": "VIEW_OVERVIEW",
        "status": "ok",
        "summary": "你的财富评分为 72 分",
        "metrics": [{"key": "wealth_score", "label": "财富评分", "unit": "score",
                     "value": 72, "source": "overview.wealth_score"}],
        "limitations": ["retirement_debt_service_not_included"],
    })
    assert r.intent == "VIEW_OVERVIEW"
    assert r.metrics[0].value == 72
    assert r.limitations == ["retirement_debt_service_not_included"]


def test_agent_response_rejects_bad_intent_status():
    """非法 intent / status 抛错；带数值指标缺 source 也抛错。"""
    with pytest.raises(ValidationError):
        AgentResponse(intent="FREE_FORM_QUERY", status="ok", summary="x")
    with pytest.raises(ValidationError):
        AgentResponse(intent="VIEW_OVERVIEW", status="maybe", summary="x")
    with pytest.raises(ValidationError):
        AgentResponse(
            intent="VIEW_OVERVIEW", status="ok", summary="x",
            metrics=[{"key": "net_worth", "label": "净资产", "unit": "money", "value": 100}],
        )
