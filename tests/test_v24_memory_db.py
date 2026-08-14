"""V2.4 Task 0：Memory 存储 Schema（3 张新表 + CRUD）契约测试。

铁律：
- 3 张表幂等创建（conversation_message / memory_fact / advisor_judgment）。
- 版本化：memory_fact 同 key 新值 → version +1，旧版本 superseded_by 指向新 id。
- 判断：save_judgment 写入新 active 时，旧 active 置 stale。
- JSON 字段（tool_calls/priorities/evidence/validity_conditions）序列化往返不丢类型。
"""
import pytest

from app import db


@pytest.fixture
def memory_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db


@pytest.fixture
def family(memory_db):
    return memory_db.create_family("测试家庭")


def _table_names():
    rows = db._rows("SELECT name FROM sqlite_master WHERE type='table'")
    return {r["name"] for r in rows}


def test_memory_tables_exist(memory_db):
    names = _table_names()
    assert {"conversation_message", "memory_fact", "advisor_judgment"} <= names


def test_append_and_recent_conversation(family):
    db.append_conversation(family, "user", "我45岁", intent=None, tool_calls=None)
    db.append_conversation(family, "assistant", "你的养老需要关注", intent="CHECK_RETIREMENT",
                           tool_calls=["get_retirement"])
    recent = db.recent_conversations(family, 10)
    assert len(recent) == 2
    # 倒序返回：最新在前
    assert recent[0]["role"] == "assistant"
    assert recent[0]["tool_calls"] == ["get_retirement"]
    assert recent[1]["role"] == "user"
    assert recent[1]["message"] == "我45岁"


def test_recent_conversations_limited(family):
    for i in range(5):
        db.append_conversation(family, "user", f"第{i}句")
    recent = db.recent_conversations(family, 3)
    assert len(recent) == 3
    # 只保留最近 3 条（序号最大的 3 条）
    assert recent[0]["message"] == "第4句"
    assert recent[2]["message"] == "第2句"


def test_upsert_fact_versioning(family):
    first = db.upsert_fact(family, "retirement_age", "45", source="chat_confirmed",
                           confidence="confirmed")
    second = db.upsert_fact(family, "retirement_age", "55", source="chat_confirmed",
                            confidence="confirmed")
    assert first != second
    rows = db._rows("SELECT * FROM memory_fact WHERE family_id=? ORDER BY version", (family,))
    assert [r["version"] for r in rows] == [1, 2]
    assert rows[0]["superseded_by"] == second   # 旧版本指向新版本
    assert rows[1]["superseded_by"] is None     # 新版本当前有效


def test_upsert_fact_idempotent_same_value(family):
    first = db.upsert_fact(family, "retirement_age", "45", source="chat_confirmed",
                           confidence="confirmed")
    again = db.upsert_fact(family, "retirement_age", "45", source="chat_confirmed",
                           confidence="confirmed")
    assert first == again                       # 相同值+来源 → 不写新版本
    rows = db._rows("SELECT * FROM memory_fact WHERE family_id=?", (family,))
    assert len(rows) == 1


def test_current_facts_only_active(family):
    db.upsert_fact(family, "retirement_age", "45", source="chat_confirmed",
                   confidence="confirmed")
    db.upsert_fact(family, "retirement_age", "55", source="chat_confirmed",
                   confidence="confirmed")
    db.upsert_fact(family, "risk_preference", "保守", source="inferred", confidence="inferred")
    facts = db.current_facts(family)
    by_key = {f["key"]: f for f in facts}
    assert by_key["retirement_age"]["value"] == "55"   # 只返回当前有效版本
    assert by_key["risk_preference"]["confidence"] == "inferred"


def test_save_judgment_invalidates_previous(family):
    j1 = db.save_judgment(family, priorities=[{"issue_id": "a", "severity": "P0"}],
                          evidence=[], recommendation="关注现金流",
                          validity_conditions={"monthly_income": 30000})
    j2 = db.save_judgment(family, priorities=[{"issue_id": "b", "severity": "P1"}],
                          evidence=[], recommendation="关注负债",
                          validity_conditions={"monthly_income": 50000})
    assert j1 != j2
    rows = db._rows("SELECT * FROM advisor_judgment WHERE family_id=?", (family,))
    assert {r["id"]: r["status"] for r in rows} == {j1: "stale", j2: "active"}


def test_latest_judgment_roundtrip(family):
    db.save_judgment(family, priorities=[{"issue_id": "x", "severity": "P0", "title": "现金流",
                                          "finding": "结余为负"}],
                     evidence=[{"claim": "月度结余为负", "metric": {"key": "cashflow_surplus",
                                                                  "value": -10000}}],
                     recommendation="先解决现金流",
                     validity_conditions={"monthly_income": 10000, "dti": 0.4})
    j = db.latest_judgment(family)
    assert j is not None
    assert j["priorities"][0]["issue_id"] == "x"
    assert j["evidence"][0]["metric"]["value"] == -10000
    assert j["validity_conditions"]["monthly_income"] == 10000
    assert j["status"] == "active"


def test_latest_judgment_empty(family):
    assert db.latest_judgment(family) is None
