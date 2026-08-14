"""V2.2 tool_loop 多轮循环测试：LLM 选工具 → execute_tool → 结果回传 → 第二轮推理。

铁律：
- LLM 失败（chat 返回 None）→ run_advisor 返回 None → 上层确定性兜底。
- 超轮数（一直 tool_calls）→ 返回 None（防死循环）。
- 工具异常（ToolError）→ 不崩，error 回传给 LLM 继续循环。
- 数字不在此层产生：run_advisor 只编排，数字由 Task 3 从 tool_results 取。
"""
import json

import pytest

from app import db
from app.agent import FakeLLMProvider
from app.agent.advisor import run_advisor


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


# ---------- 单工具（T5：最大风险 → get_wealth_issues） ----------

def test_single_tool_round_trip(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_call("get_wealth_issues")]},
        {"content": '{"summary": "你最大的风险是负债偏高"}', "tool_calls": []},
    ])
    out = run_advisor(_user(family), "帮我看看最大的风险", fake)
    assert out is not None
    assert out["tool_results"][0]["name"] == "get_wealth_issues"
    assert out["tool_results"][0]["result"]["data_origin"] == "real"
    assert json.loads(out["content"])["summary"] == "你最大的风险是负债偏高"


# ---------- 多工具串联（T1：买房 → overview + issues + cashflow） ----------

def test_multi_tool_chain(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [
            _call("get_wealth_overview"), _call("get_wealth_issues"),
        ]},
        {"content": None, "tool_calls": [_call("get_cashflow")]},
        {"content": '{"summary": "现在买房压力偏大", "missing": ["房价"]}', "tool_calls": []},
    ])
    out = run_advisor(_user(family), "现在适合买房吗", fake)
    assert [t["name"] for t in out["tool_results"]] == [
        "get_wealth_overview", "get_wealth_issues", "get_cashflow",
    ]
    assert "missing" in json.loads(out["content"])


# ---------- 无工具（T9：闲聊，不调工具） ----------

def test_no_tool_direct_answer(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": '{"summary": "复利是把利息再投资"}', "tool_calls": []},
    ])
    out = run_advisor(_user(family), "什么是复利", fake)
    assert out["tool_results"] == []
    assert json.loads(out["content"])["summary"] == "复利是把利息再投资"


# ---------- 工具异常不崩（T：run_scenario free tier → forbidden 回传） ----------

def test_tool_error_does_not_crash(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_call("run_scenario",
                                               {"name": "income_change",
                                                "params": {"pct_change": -0.3}})]},
        {"content": '{"summary": "需要 VIP"}', "tool_calls": []},
    ])
    out = run_advisor(_user(family, "free"), "收入下降会怎样", fake)
    assert out is not None
    assert out["tool_results"][0]["result"] is None
    second_messages = fake.chat_messages[1]
    tool_msg = [m for m in second_messages if m["role"] == "tool"][0]
    assert "forbidden" in tool_msg["content"]


# ---------- LLM 失败 / 超轮数降级 ----------

def test_llm_none_returns_none(family):
    fake = FakeLLMProvider(chat_script=[])
    assert run_advisor(_user(family), "hi", fake) is None


def test_max_rounds_returns_none(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_call("get_wealth_overview")]}
        for _ in range(10)
    ])
    assert run_advisor(_user(family), "hi", fake) is None


# ---------- wealth_context 注入 system ----------

def test_wealth_context_injected_into_system(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": '{"summary": "ok"}', "tool_calls": []},
    ])
    run_advisor(_user(family), "hi", fake, wealth_context="【财务指标】净资产=100")
    system = fake.chat_messages[0][0]["content"]
    assert "【财务指标】净资产=100" in system
