"""V2.4 Task 1：短期对话记忆（converse 写入 + 摘要 builder）契约测试。

铁律：
- converse 每轮写入 user 原文 + assistant 结论摘要（非全文）。
- build_conversation_summary 生成结构化摘要，每轮一行。
- 限量：n 轮截断，不全文堆塞。
"""
import pytest

from app import db
from app.agent import FakeLLMProvider, converse
from app.agent.memory import build_conversation_summary


@pytest.fixture
def family(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    fid = db.create_family("测试家庭")
    db.apply_action(fid, {"kind": "person",
                          "fields": {"name": "本人", "relation": "本人", "birth_year": 1990}})
    db.apply_action(fid, {"kind": "income",
                          "fields": {"category": "工资", "amount": 10000, "period": "月"}})
    db.apply_action(fid, {"kind": "expense",
                          "fields": {"category": "日常", "amount": 20000, "period": "月"}})
    return fid


def _user(fid):
    return {"family_id": fid, "tier": "free"}


def _ask(fid, message, summary="结论"):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [{"id": "c1", "name": "get_wealth_issues",
                                          "arguments": {}}]},
        {"content": None, "tool_calls": []},
    ], script=['{"summary": "' + summary + '"}'])
    return converse(message, _user(fid), llm=fake)


def test_converse_writes_user_and_assistant(family):
    _ask(family, "帮我看看最大风险", summary="现金流是主要矛盾")
    rows = db.recent_conversations(family, 10)
    assert len(rows) == 2
    # 倒序：assistant 最新在前，user 在前一条
    assert rows[0]["role"] == "assistant"
    assert rows[0]["intent"] == "CHECK_ISSUES"
    assert rows[0]["message"] == "现金流是主要矛盾"
    assert rows[1]["role"] == "user"
    assert rows[1]["message"] == "帮我看看最大风险"


def test_build_conversation_summary_content(family):
    _ask(family, "帮我看看最大风险", summary="现金流是主要矛盾")
    s = build_conversation_summary(family, 5)
    assert "帮我看看最大风险" in s
    assert "现金流是主要矛盾" in s
    assert "CHECK_ISSUES" in s


def test_build_conversation_summary_limited(family):
    labels = ["甲", "乙", "丙"]
    for i in range(3):
        _ask(family, f"问题{i}", summary=f"结论{labels[i]}")
    s = build_conversation_summary(family, 2)   # 最近 2 轮 = 4 条消息
    assert "问题0" not in s                      # 超出限量的旧轮被截断
    assert "问题2" in s
    assert "结论丙" in s


def test_build_conversation_summary_empty(family):
    assert build_conversation_summary(family, 5) == ""
