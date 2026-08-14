"""V2.4 Task 3：顾问判断记忆（主要矛盾 + 依据 + 有效条件快照）契约测试。

铁律：
- advisor 产出 priorities 后，save_judgment 写入 priorities + evidence + validity_conditions。
- validity_conditions = 判断时的当前 overview 关键值快照（主动 build，不依赖 LLM 调了啥）。
- 新判断写入 → 旧 active 置 stale。
- refuse / need_clarification 不是完整判断，不写判断记忆。
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
                          "fields": {"category": "工资", "amount": 10000, "period": "月"}})
    db.apply_action(fid, {"kind": "expense",
                          "fields": {"category": "日常", "amount": 20000, "period": "月"}})
    return fid


def _user(fid):
    return {"family_id": fid, "tier": "free"}


def _c(name, args=None):
    return {"id": "c1", "name": name, "arguments": args or {}}


def _advise(fid, message, summary="现金流是主要矛盾"):
    fake = FakeLLMProvider(chat_script=[
        {"content": None, "tool_calls": [_c("get_wealth_issues")]},
        {"content": '{"summary":"' + summary + '"}', "tool_calls": []},
    ])
    return advise(_user(fid), message, fake, intent="CHECK_ISSUES")


def test_advise_writes_judgment(family):
    resp = _advise(family, "帮我看看最大风险")
    assert resp.status == "ok"
    j = db.latest_judgment(family)
    assert j is not None
    assert j["status"] == "active"
    assert j["priorities"][0]["severity"] == "P0"
    assert j["recommendation"] == "现金流是主要矛盾"


def test_judgment_saves_validity_conditions(family):
    _advise(family, "帮我看看最大风险")
    j = db.latest_judgment(family)
    conds = j["validity_conditions"]
    assert "cashflow_surplus" in conds
    assert conds["cashflow_surplus"] == -10000   # income 10000 - expense 20000


def test_new_judgment_invalidates_previous(family):
    _advise(family, "帮我看看最大风险", summary="第一次判断")
    _advise(family, "再看看", summary="第二次判断")
    rows = db._rows("SELECT * FROM advisor_judgment WHERE family_id=? ORDER BY id", (family,))
    assert {r["status"] for r in rows} == {"stale", "active"}
    assert db.latest_judgment(family)["recommendation"] == "第二次判断"


def test_refused_not_recorded(family):
    fake = FakeLLMProvider(chat_script=[
        {"content": '{"refuse": true, "summary": "独立计算我拒绝"}', "tool_calls": []},
    ])
    resp = advise(_user(family), "帮我算100万复利", fake, intent="VIEW_OVERVIEW")
    assert resp.status == "refused"
    assert db.latest_judgment(family) is None
