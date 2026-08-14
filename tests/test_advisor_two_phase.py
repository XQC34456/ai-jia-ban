"""两阶段结构输出回归测试（顾问实战验收 2026-08-14）。

背景：V2.1~V2.4 全部用 FakeLLMProvider 脚本返回合法 JSON，掩盖了真实模型
（deepseek-v4-flash）最终回答是散文而非 JSON 的事实——advise() 的 _parse_json
解析失败 → 返回 None → 回退确定性兜底，顾问的散文根本没送到用户面前。

修复：工具循环（chat，模型自由思考产散文）与结构化输出（complete_json，强制
json_object 保证合法 JSON）拆两步。数字仍从 tool_results 确定性取，不破铁律。
"""
import pytest

import app.agent.advisor as advisor_mod
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
                          "fields": {"category": "工资", "amount": 10000, "period": "月"}})
    db.apply_action(fid, {"kind": "expense",
                          "fields": {"category": "日常", "amount": 20000, "period": "月"}})
    return fid


def _user(fid):
    return {"family_id": fid, "tier": "free"}


def test_prose_final_answer_is_structured(family):
    """真实模型行为：chat 最终输出散文（非 JSON），complete_json 压成结构 → ok，不回退。"""
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [{"id": "c1", "name": "get_cashflow",
                                          "arguments": {}}]},
        {"content": "你的现金流是负的，月支出超过月收入，这是当前最紧急的问题。",
         "tool_calls": []},
    ], script=[
        '{"summary": "现金流是当前主要矛盾",'
        '"evidence": [{"claim": "月度结余为负", "metric_key": "cashflow_surplus"}]}',
    ])
    resp = advise(_user(family), "帮我看看最大风险", fake, intent="CHECK_ISSUES")
    assert resp is not None
    assert resp.status == "ok"
    assert resp.summary == "现金流是当前主要矛盾"
    assert resp.evidence and resp.evidence[0].metric.value == -10000


def test_prose_no_tools_structured(family):
    """无工具轮：chat 直接产散文 → 结构化，metrics 为空但 status ok。"""
    fake = FakeLLMProvider(chat_script=[
        {"content": "我主要专注家庭财富规划，也可以聊理财话题。", "tool_calls": []},
    ], script=['{"summary": "我主要专注家庭财富规划"}'])
    resp = advise(_user(family), "今天天气怎么样", fake, intent="VIEW_OVERVIEW")
    assert resp is not None
    assert resp.status == "ok"
    assert resp.metrics == []


def test_structure_fail_prose_falls_back(family, monkeypatch):
    """structure 阶段失败但有散文 → 散文兜底（回答可用性），不整体降级。"""
    monkeypatch.setattr(advisor_mod, "_structure_advisor_answer", lambda *a, **k: None)
    fake = FakeLLMProvider(chat_script=[
        {"content": "这是一段没有结构化的散文。", "tool_calls": []},
    ])
    resp = advise(_user(family), "hi", fake)
    assert resp is not None
    assert resp.summary == "这是一段没有结构化的散文。"


def test_structure_fail_prose_digits_stripped(family, monkeypatch):
    """structure 失败 + prose 含数字 → 数字不泄露（铁律：数字绝不进定性文字）。"""
    monkeypatch.setattr(advisor_mod, "_structure_advisor_answer", lambda *a, **k: None)
    fake = FakeLLMProvider(chat_script=[
        {"content": "建议留出 20 万作为备用金。", "tool_calls": []},
    ])
    resp = advise(_user(family), "帮我看看", fake)
    assert resp is not None
    assert not any(ch.isdigit() for ch in resp.summary)


def test_structure_fail_prose_digits_keeps_deterministic_metrics(family, monkeypatch):
    """structure 失败 + prose 含数字 → summary 可空，但确定性 metrics 仍在，response 非空回答。"""
    monkeypatch.setattr(advisor_mod, "_structure_advisor_answer", lambda *a, **k: None)
    fake = FakeLLMProvider(chat_script=[
        {"content": None,
         "tool_calls": [{"id": "c1", "name": "get_cashflow", "arguments": {}}]},
        {"content": "建议留出 20 万作为备用金。", "tool_calls": []},
    ])
    resp = advise(_user(family), "帮我看看", fake)
    assert resp is not None
    assert not any(ch.isdigit() for ch in resp.summary)  # 数字 strip
    assert resp.metrics  # 确定性兜底：metrics 非空，response 不是空回答


def test_structure_fail_no_prose_returns_none(family, monkeypatch):
    """structure 失败 + chat 彻底无产出（content None）→ 仍返回 None，保留降级。"""
    monkeypatch.setattr(advisor_mod, "_structure_advisor_answer", lambda *a, **k: None)
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": []},
    ])
    assert advise(_user(family), "hi", fake) is None
