"""V2.3 意图路由升级测试：EXPLAIN_RESULT 单轮内走 advisor_path + 反例意图回归。

铁律：
- EXPLAIN_RESULT（「为什么/解释」）有 LLM 时走 advisor_path 调工具解释，不再死分支。
- 反例消息（质疑/情绪/绝对答案）能进入 advisor_path，不落 VIEW_OVERVIEW 死兜底。
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


def _user(fid):
    return {"family_id": fid, "tier": "free"}


def test_explain_result_goes_advisor_path(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [{"id": "c1", "name": "get_wealth_issues", "arguments": {}}]},
        {"content": '{"summary": "我解释一下你当前的主要风险"}', "tool_calls": []},
    ])
    resp = handle("解释一下", _user(family), llm=fake)
    assert resp.status == "ok"          # 不再是 need_clarification 死分支


def test_counter_challenge_goes_advisor_path(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [{"id": "c1", "name": "get_wealth_issues", "arguments": {}}]},
        {"content": '{"summary": "我重新核对了数据，之前的判断需要修正"}', "tool_calls": []},
    ])
    resp = handle("你说的不对", _user(family), llm=fake)
    assert resp.status == "ok"


def test_emotion_goes_advisor_path(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [{"id": "c1", "name": "get_cashflow", "arguments": {}}]},
        {"content": '{"summary": "先别急，我帮你看一下现金流"}', "tool_calls": []},
    ])
    resp = handle("我这辈子都攒不下钱", _user(family), llm=fake)
    assert resp.status == "ok"


def test_absolute_answer_goes_advisor_path(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [{"id": "c1", "name": "get_wealth_overview", "arguments": {}}]},
        {"content": '{"summary": "这不是简单的二选一",'
                    '"tradeoffs":[{"option":"现在买","gain":"住房确定性","loss":"流动性"}]}',
         "tool_calls": []},
    ])
    resp = handle("你就告诉我买不买", _user(family), llm=fake)
    assert resp.status == "ok"
    assert resp.tradeoffs
