"""V2.2 handle 集成端到端：顾问感场景（理解/追问/数据/推理/表达/行动）。

铁律：
- 有 LLM（chat_script）时，非 EXPLAIN_RESULT 意图走 advisor_path（tool_loop 多步）。
- 无 LLM / chat 失败 → 回退确定性 dispatch（现有测试锁定）。
- 数字只来自 metrics（带 source），summary 是定性人话、不含数字、不甩内部标识。
"""
import pytest

from app import db
from app.agent import FakeLLMProvider
from app.agent.runtime import handle


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


def _user(fid, tier="free"):
    return {"family_id": fid, "tier": tier}


def _call(name, args=None):
    return {"id": "c1", "name": name, "arguments": args or {}}


def _no_digits(s: str) -> bool:
    return not any(ch.isdigit() for ch in s)


# ---------- 多步决策链路（T1：买房 → overview + issues → 缺房价追问） ----------

def test_handle_advisor_multi_step_house(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [
            _call("get_wealth_overview"), _call("get_wealth_issues"),
        ]},
        {"content": None, "tool_calls": []},
    ], script=['{"summary": "现在买房压力偏大", "missing": ["房价"]}'])
    resp = handle("我现在适合买房吗", _user(family), llm=fake)
    assert resp.intent == "SCENARIO_COMPARE"
    assert resp.status == "need_clarification"
    assert "房价" in resp.summary


# ---------- 数据 + 推理 + 表达（T5：最大风险 → issues → 定性结论） ----------

def test_handle_advisor_biggest_risk(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_call("get_wealth_issues")]},
        {"content": None, "tool_calls": []},
    ], script=['{"summary": "你目前最大的风险是负债率偏高", "finding": "房贷月供占收入比例过高"}'])
    resp = handle("帮我看最大的风险", _user(family), llm=fake)
    assert resp.intent == "CHECK_ISSUES"
    assert resp.status == "ok"
    assert _no_digits(resp.summary)
    assert any(m.source for m in resp.metrics)


# ---------- 表达：不甩 RFR/issue_id（T2：养老解释） ----------

def test_handle_advisor_retirement_no_internal_ids(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_call("get_retirement")]},
        {"content": None, "tool_calls": []},
    ], script=['{"summary": "你的养老压力主要来自房产占比偏高、可投资资产偏少"}'])
    resp = handle("为什么我的养老有问题", _user(family), llm=fake)
    assert resp.status == "ok"
    assert "RFR" not in resp.summary and "issue_id" not in resp.summary
    assert _no_digits(resp.summary)


# ---------- 数据（用户#2：压力大钱不够 → cashflow） ----------

def test_handle_advisor_cashflow_pressure(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_call("get_cashflow")]},
        {"content": None, "tool_calls": []},
    ], script=['{"summary": "你每月还有结余，但应急储备偏薄"}'])
    resp = handle("我最近压力很大，感觉钱不够用", _user(family), llm=fake)
    assert resp.status == "ok"
    assert any(m.key == "cashflow_surplus" and m.source for m in resp.metrics)


# ---------- 沙盘（scenario 工具链 + 行动建议） ----------

def test_handle_advisor_scenario_income_change(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_call("run_scenario",
                                               {"name": "income_change",
                                                "params": {"pct_change": -0.3}})]},
        {"content": None, "tool_calls": []},
    ], script=['{"summary": "收入下降会明显压缩你的应急资金", "recommendations": ["先补应急"]}'])
    resp = handle("收入下降 30% 会怎样", _user(family, "vip"), llm=fake)
    assert resp.status == "ok"
    assert any(m.source.startswith("comparison.") for m in resp.metrics)
    assert resp.recommendations == ["先补应急"]


# ---------- 理解边界（T10：无关问题，不调工具不算数字） ----------

def test_handle_advisor_chitchat_no_tools(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": []},
    ], script=['{"summary": "我主要专注家庭财富，你也可以聊聊理财相关的话题"}'])
    resp = handle("今天天气怎么样", _user(family), llm=fake)
    assert resp.status == "ok"
    assert resp.metrics == []
    assert _no_digits(resp.summary)


# ---------- 意图消歧（#12：纯金融计算 → refused，不假装算出来） ----------

def test_handle_advisor_pure_calc_refused(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": []},
    ], script=['{"refuse": true, "summary": "这是独立的金融计算，我不能自行测算"}'])
    resp = handle("帮我算 100 万复利 10 年", _user(family), llm=fake)
    assert resp.status == "refused"


# ---------- 目标（#16：教育金 → goals） ----------

def test_handle_advisor_education_goal(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_call("get_goals")]},
        {"content": None, "tool_calls": []},
    ], script=['{"summary": "你的教育金目标还有缺口，需要提前规划"}'])
    resp = handle("孩子 5 年后上大学教育金够吗", _user(family), llm=fake)
    assert resp.intent == "CHECK_GOALS"
    assert resp.status == "ok"
    assert _no_digits(resp.summary)
