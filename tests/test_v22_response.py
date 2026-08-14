"""V2.2 回答组装 + 数字防编造测试：metrics 从 tool_results 取（带 source），LLM 只定性。

铁律：
- 最终 AgentResponse 的 metrics 数字全部来自 tool_results（Engine/Decision/Sandbox），带 source。
- LLM 文字（summary/finding/recommendations/next_actions）含任何数字 → 丢弃/过滤，绝不带数。
- 无 tool_results 时 metrics 为空（即使 LLM 在 JSON 里塞了数字字段也不取）。
"""
import pytest

from app import db
from app.agent.response import assemble_advisor_response
from app.agent.tool_schemas import execute_tool


@pytest.fixture
def family(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    fid = db.create_family("测试家庭")
    db.apply_action(fid, {"kind": "person",
                          "fields": {"name": "本人", "relation": "本人", "birth_year": 1990}})
    db.apply_action(fid, {"kind": "income",
                          "fields": {"category": "工资", "amount": 30000, "period": "月"}})
    db.apply_action(fid, {"kind": "expense",
                          "fields": {"category": "日常", "amount": 20000, "period": "月"}})
    return fid


# ---------- metrics 从 tool_results 取（带 source） ----------

def test_metrics_from_overview_tool(family):
    ov = execute_tool("get_wealth_overview", {}, {"family_id": family})
    resp = assemble_advisor_response(
        [{"name": "get_wealth_overview", "result": ov}],
        {"summary": "你的财务整体健康"}, "VIEW_OVERVIEW")
    keys = [m.key for m in resp.metrics]
    assert "wealth_score" in keys
    ws = next(m for m in resp.metrics if m.key == "wealth_score")
    assert ws.source == "overview.wealth_score"
    assert ws.value == ov["overview"]["wealth_score"]


def test_metrics_from_scenario_tool(family):
    sc = execute_tool("run_scenario",
                      {"name": "income_change", "params": {"pct_change": -0.3}},
                      {"family_id": family, "tier": "vip"})
    resp = assemble_advisor_response(
        [{"name": "run_scenario", "result": sc}],
        {"summary": "收入下降会影响应急"}, "SCENARIO_COMPARE")
    assert any(m.source == "comparison.A.cashflow.delta" for m in resp.metrics)


def test_cashflow_metrics_from_get_cashflow(family):
    cf = execute_tool("get_cashflow", {}, {"family_id": family})
    resp = assemble_advisor_response(
        [{"name": "get_cashflow", "result": cf}],
        {"summary": "你的现金流有结余"}, "VIEW_OVERVIEW")
    keys = {m.key for m in resp.metrics}
    assert "cashflow_surplus" in keys
    surplus = next(m for m in resp.metrics if m.key == "cashflow_surplus")
    assert surplus.source == "overview.cashflow.surplus"


def test_metrics_empty_without_tool_results():
    llm_json = {"summary": "净资产 320 万", "finding": "负债 100 万"}  # LLM 塞数字也没用
    resp = assemble_advisor_response([], llm_json, "VIEW_OVERVIEW")
    assert resp.metrics == []


# ---------- 数字防编造：LLM 文字含数字 → 丢弃 ----------

def test_llm_numeric_text_rejected():
    llm_json = {
        "summary": "你的净资产 320 万，评分 46",
        "finding": "因为负债 100 万",
        "recommendations": ["先还贷", "每月存 3000 元"],
        "next_actions": ["帮我比较方案", "存 5 万应急"],
    }
    resp = assemble_advisor_response([], llm_json, "VIEW_OVERVIEW")
    assert resp.summary == ""                 # 含数字 → 丢弃
    assert resp.finding is None               # 含数字 → 丢弃
    assert resp.recommendations == ["先还贷"]  # 含数字条目过滤
    assert resp.next_actions == ["帮我比较方案"]


def test_llm_clean_text_preserved():
    llm_json = {
        "summary": "你的负债偏高，需要优先处理",
        "finding": "主要是房贷占收入比例过高",
        "recommendations": ["先补应急", "降低月供压力"],
    }
    resp = assemble_advisor_response([], llm_json, "VIEW_OVERVIEW")
    assert resp.summary == "你的负债偏高，需要优先处理"
    assert resp.recommendations == ["先补应急", "降低月供压力"]
