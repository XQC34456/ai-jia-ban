"""V2.2 advise 编排 + 意图消歧测试：refuse/missing → 正确 status；LLM 失败 → 兜底 None。

铁律：
- missing（信息不足）→ need_clarification 追问，不胡猜。
- refuse（纯金融计算）→ refused，不假装算出来。
- LLM 失败 / content 无法解析 → 返回 None → 上层确定性兜底。
"""
import pytest

from app import db
from app.agent import FakeLLMProvider
from app.agent.advisor import advise


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


def test_advise_missing_returns_clarification(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None,
         "tool_calls": [{"id": "c1", "name": "get_wealth_overview", "arguments": {}}]},
        {"content": '{"summary": "需要更多信息", "missing": ["房价", "贷款金额"]}',
         "tool_calls": []},
    ])
    resp = advise(_user(family), "现在适合买房吗", fake)
    assert resp.status == "need_clarification"
    assert "房价" in resp.summary and "贷款金额" in resp.summary


def test_advise_refuse_returns_refused(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": '{"refuse": true, "summary": "这是独立的金融计算，我不能自行测算"}',
         "tool_calls": []},
    ])
    resp = advise(_user(family), "帮我算 100 万复利 10 年", fake)
    assert resp.status == "refused"


def test_advise_ok_returns_ok_with_metrics(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": None,
         "tool_calls": [{"id": "c1", "name": "get_wealth_issues", "arguments": {}}]},
        {"content": '{"summary": "你最大的风险是负债偏高"}', "tool_calls": []},
    ])
    resp = advise(_user(family), "帮我看最大的风险", fake)
    assert resp.status == "ok"
    assert any(m.source for m in resp.metrics)


def test_advise_llm_none_returns_none(family):
    fake = FakeLLMProvider(chat_script=[])
    assert advise(_user(family), "hi", fake) is None


def test_advise_unparseable_returns_none(family):
    fake = FakeLLMProvider(chat_script=[{"content": "not json", "tool_calls": []}])
    assert advise(_user(family), "hi", fake) is None
