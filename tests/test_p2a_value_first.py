"""P2-A Free→VIP 价值前置测试：先基础判断，再展示 VIP 能补什么（不再冷拒「升级」）。

铁律守门：所有注入话术全定性、无数字；数字仍只走 metrics/source；不触碰 Engine/Decision。

覆盖：
- value_first：四情景 + 默认兜底（基础判断 + 进一步分析，定性无数字）
- _attach_vip_boundary：仅 Free + SCENARIO_COMPARE + 无对比时注入；VIP/非情景/有对比不注入
- advise（advisor 路径）：Free 情景问题 → 注入 vip_boundary + status ok + scenario_comparison None
- 确定性兜底（handle）：forbidden + SCENARIO_COMPARE → status ok（非 refused）+ vip_boundary + 升级 next_action
"""
from __future__ import annotations

from app import db
from app.agent.advisor import _attach_vip_boundary, advise
from app.agent.provider import FakeLLMProvider
from app.agent.runtime import handle
from app.agent.vip import VIP_BOUNDARY, value_first
from app.schemas.agent import AgentResponse


def _token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def _user(headers: dict) -> dict:
    return db.get_user_by_token(_token(headers))


# ---------- value_first：四情景 + 默认兜底（定性无数字） ----------

def test_value_first_covers_four_scenarios():
    for name in ("buy_house", "prepay", "invest", "income_change"):
        basic, further = value_first(name)
        assert basic and further
        assert not any(ch.isdigit() for ch in basic)      # 铁律：话术模板不编数字
        assert not any(ch.isdigit() for ch in further)


def test_value_first_default_for_unknown():
    basic, further = value_first(None)
    assert basic and further == VIP_BOUNDARY


# ---------- _attach_vip_boundary：注入边界条件封闭 ----------

def test_attach_free_scenario_injects():
    resp = AgentResponse(intent="SCENARIO_COMPARE", status="ok", summary="基础判断")
    out = _attach_vip_boundary(resp, {"tier": "free"}, "SCENARIO_COMPARE")
    assert out.vip_boundary == VIP_BOUNDARY


def test_attach_vip_no_inject():
    resp = AgentResponse(intent="SCENARIO_COMPARE", status="ok", summary="x")
    assert _attach_vip_boundary(resp, {"tier": "vip"}, "SCENARIO_COMPARE").vip_boundary is None


def test_attach_non_scenario_no_inject():
    resp = AgentResponse(intent="CHECK_ISSUES", status="ok", summary="x")
    assert _attach_vip_boundary(resp, {"tier": "free"}, "CHECK_ISSUES").vip_boundary is None


def test_attach_with_comparison_no_inject():
    resp = AgentResponse(intent="SCENARIO_COMPARE", status="ok", summary="x",
                         scenario_comparison={"A": []})
    assert _attach_vip_boundary(resp, {"tier": "free"}, "SCENARIO_COMPARE").vip_boundary is None


# ---------- advisor 路径：Free 情景问题 → 注入「进一步分析」边界 ----------

def _scenario_chat_llm() -> FakeLLMProvider:
    """tool_loop：先调 run_scenario（被 VIP 门挡），再输出定性基础判断。"""
    return FakeLLMProvider(
        chat_script=[
            {"content": None, "tool_calls": [
                {"id": "c1", "name": "run_scenario",
                 "arguments": {"name": "收入下降", "params": {"pct_change": -0.2}}}]},
            {"content": "收入下降后你的现金流会明显收窄，应急缓冲会变薄。", "tool_calls": []},
        ],
        script=[{"summary": "按你当前收支结构，收入下降后现金流会收窄。", "finding": None}],
    )


def test_advise_free_scenario_injects_vip_boundary(client, auth_headers):
    resp = advise(_user(auth_headers), "如果我明年收入下降20%还能撑多久",
                  _scenario_chat_llm(), intent="SCENARIO_COMPARE")
    assert resp is not None
    assert resp.status == "ok"                     # 先交付基础价值，非 refused
    assert resp.scenario_comparison is None        # 情景未执行（被 VIP 门挡）
    assert resp.vip_boundary == VIP_BOUNDARY       # 注入确定性「进一步分析」
    assert not any(ch.isdigit() for ch in resp.vip_boundary)


# ---------- 确定性兜底路径：forbidden + SCENARIO_COMPARE → 价值前置 ----------

def test_handle_forbidden_free_user_value_first(client, auth_headers):
    # script 驱动参数提取（amount=300000），chat 无脚本 → advise 降级 → 确定性兜底命中 VIP 门
    llm = FakeLLMProvider([{"amount": 300000}])
    resp = handle("我想投资 30 万", _user(auth_headers), llm=llm)
    assert resp.intent == "SCENARIO_COMPARE"
    assert resp.status == "ok"                     # 不再冷拒「该功能需要升级」
    assert resp.vip_boundary                       # 展示 VIP 能补什么
    assert any("升级" in a for a in resp.next_actions)
    assert resp.summary and not any(ch.isdigit() for ch in resp.summary)


def test_handle_forbidden_free_user_basic_before_boundary(client, auth_headers):
    """验收红线：基础判断在前、VIP 边界在后（summary 非空且为定性基础判断）。"""
    llm = FakeLLMProvider([{"pct_change": -0.2}])
    resp = handle("如果我明年收入下降 20% 还能撑多久", _user(auth_headers), llm=llm)
    assert resp.intent == "SCENARIO_COMPARE"
    assert resp.status == "ok"
    assert resp.summary and not any(ch.isdigit() for ch in resp.summary)   # 基础判断定性
    assert resp.vip_boundary                                               # 再展示 VIP 边界
