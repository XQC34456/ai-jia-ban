"""V2.4 Task 2：家庭事实记忆（source/confidence/version + 数字防编造）契约测试。

铁律：
- 确认建档（goal=目标，顾问知识类）→ upsert_fact(source=chat_confirmed, confidence=confirmed)。
- 净值事实（income/expense/asset/liability）是 db 主表真相源，绝不进 memory_fact。
- 同 key 新事实 → version +1，旧版本 superseded_by 指向新 id。
- 数字防编造：inferred 事实的 value 含数字 → 拒写（推断不产生财富数字，须溯源）。
"""
import pytest

from app import db
from app.agent.memory import record_fact
from app.agent.profile import apply_confirmation, create_confirm, extract_actions


@pytest.fixture
def family(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db.create_family("测试家庭")


def _confirm(family, message):
    """走完整建档确认链路：抽取 → 卡片 → 确认。"""
    actions = extract_actions(message)
    assert actions, f"应抽取到建档动作：{message}"
    card = create_confirm(family, actions)
    return apply_confirmation(family, card.pending_id, confirmed=True)


def test_confirm_goal_writes_confirmed_fact(family):
    resp = _confirm(family, "给孩子准备教育金，目标50万")
    assert resp.type == "applied"
    facts = db.current_facts(family)
    goals = [f for f in facts if f["key"] == "goal:教育"]
    assert len(goals) == 1
    assert goals[0]["source"] == "chat_confirmed"
    assert goals[0]["confidence"] == "confirmed"
    assert "500" in goals[0]["value"]


def test_goal_change_version_bumps(family):
    _confirm(family, "给孩子准备教育金，目标50万")
    _confirm(family, "给孩子准备教育金，目标30万")
    facts = db.current_facts(family)
    goals = [f for f in facts if f["key"] == "goal:教育"]
    assert len(goals) == 1                     # 只返回当前有效版本
    assert "300" in goals[0]["value"]          # 新目标覆盖旧目标
    rows = db._rows("SELECT * FROM memory_fact WHERE family_id=? ORDER BY version", (family,))
    assert [r["version"] for r in rows] == [1, 2]
    assert rows[0]["superseded_by"] == rows[1]["id"]   # 旧版本指向新版本


def test_income_not_in_memory_fact(family):
    _confirm(family, "我月薪3万")
    facts = db.current_facts(family)
    assert not any(f["key"].startswith("income") for f in facts)  # 净值事实不进记忆层
    # 但确实写进了 db 主表（当前真相源：收入入 cashflow）
    rows = db._rows("SELECT * FROM cashflow WHERE family_id=?", (family,))
    assert rows


def test_inferred_fact_with_digits_rejected(family):
    rid = record_fact(family, "retirement_age", "55岁", source="inferred",
                      confidence="inferred")
    assert rid is None                       # 含数字的 inferred 事实拒写
    assert db.current_facts(family) == []


def test_confirmed_fact_with_digits_allowed(family):
    rid = record_fact(family, "retirement_age", "55", source="chat_confirmed",
                      confidence="confirmed")
    assert rid is not None                   # 确认来源的数字可写（来自确定性抽取）
    facts = db.current_facts(family)
    assert facts[0]["key"] == "retirement_age"
