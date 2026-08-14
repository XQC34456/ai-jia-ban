"""V2.4 Task 5：Memory 注入 advisor（结构化摘要进 system prompt）契约测试。

铁律：
- build_memory_context 合成三层摘要（L1 近期对话 + L2 家庭事实 + L3 最近判断）。
- 纯函数、零 LLM、零计算；限量：L1 固定 N 轮、L2 只当前有效、L3 只最近 1 次。
- stale 判断附「已失效」提示（由 detect_invalidation 确定性标记）。
- 注入 system prompt：wealth_context 在前，memory_context 在后。
"""
import pytest

from app import db
from app.agent.advisor import _messages_with_context
from app.agent.memory import build_memory_context, detect_invalidation


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


def test_build_memory_context_empty(family):
    assert build_memory_context(family) == ""


def test_build_memory_context_three_layers(family):
    # L1 对话
    db.append_conversation(family, "user", "为什么养老有问题")
    db.append_conversation(family, "assistant", "你的养老需要关注", intent="CHECK_RETIREMENT")
    # L2 事实
    db.upsert_fact(family, "retirement_age", "55", source="chat_confirmed",
                   confidence="confirmed")
    # L3 判断
    db.save_judgment(family, priorities=[{"issue_id": "x", "severity": "P0",
                                          "title": "现金流", "finding": "结余为负"}],
                     evidence=[], recommendation="先解决现金流",
                     validity_conditions={"cashflow_surplus": -10000})
    ctx = build_memory_context(family)
    assert "近期对话" in ctx and "为什么养老有问题" in ctx
    assert "已确认的家庭事实" in ctx and "retirement_age" in ctx
    assert "上次判断" in ctx and "现金流" in ctx


def test_build_memory_context_stale_hint(family):
    db.save_judgment(family, priorities=[{"issue_id": "x", "severity": "P0",
                                          "title": "现金流"}],
                     evidence=[], recommendation="先解决现金流",
                     validity_conditions={"cashflow_surplus": -10000})
    # 收入变化 → 确定性失效
    rows = db._rows("SELECT id FROM cashflow WHERE family_id=? AND flow_type='income'",
                    (family,))
    db.update_entity("cashflow", rows[0]["id"], {"amount": 50000})
    detect_invalidation(family)
    ctx = build_memory_context(family)
    assert "已失效" in ctx


def test_injected_into_system_prompt(family):
    db.append_conversation(family, "user", "我45岁")
    ctx = build_memory_context(family)
    messages = _messages_with_context("再帮我看看", wealth_context="家庭背景内容",
                                      memory_context=ctx)
    system = messages[0]["content"]
    assert "家庭背景内容" in system
    assert "近期对话" in system
    assert system.index("家庭背景内容") < system.index("近期对话")   # wealth 在前，memory 在后
