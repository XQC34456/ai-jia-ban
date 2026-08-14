"""V2.4 Task 4：判断失效检测（新事实 → 旧判断 stale）契约测试。

铁律：
- 确定性：当前 overview 关键值 vs validity_conditions 逐 key 对比，变化 → stale。
- 失效检测由确定性代码完成，绝不由 LLM 判断「可能过时了」。
- 收入变化 → 标记 stale + 返回变化清单；无变化 → 保持 active，不提示。
"""
import pytest

from app import db
from app.agent import FakeLLMProvider
from app.agent.advisor import advise
from app.agent.memory import detect_invalidation


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


def _advise(fid, message):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [{"id": "c1", "name": "get_wealth_issues",
                                          "arguments": {}}]},
        {"content": '{"summary":"现金流是主要矛盾"}', "tool_calls": []},
    ])
    return advise(_user(fid), message, fake, intent="CHECK_ISSUES")


def _set_income(fid, amount):
    """把家庭月收入改为指定值（覆盖，而非新增）。"""
    rows = db._rows("SELECT id FROM cashflow WHERE family_id=? AND flow_type='income'",
                    (fid,))
    assert rows
    db.update_entity("cashflow", rows[0]["id"], {"amount": amount})


def test_income_change_invalidates(family):
    _advise(family, "帮我看看最大风险")           # 判断：cashflow_surplus = -10000
    _set_income(family, 50000)                     # 收入 10000 → 50000，surplus 变 +30000
    changed = detect_invalidation(family)
    assert changed
    assert any(c["key"] == "cashflow_surplus" for c in changed)
    c = next(c for c in changed if c["key"] == "cashflow_surplus")
    assert c["before"] == -10000
    assert c["after"] == 30000
    assert db.latest_judgment(family)["status"] == "stale"


def test_no_change_keeps_active(family):
    _advise(family, "帮我看看最大风险")
    assert detect_invalidation(family) == []
    assert db.latest_judgment(family)["status"] == "active"


def test_no_active_judgment_returns_empty(family):
    assert detect_invalidation(family) == []       # 无判断 → 无失效可检测
