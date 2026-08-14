"""内测三件套护栏测试：rate limit 配额 + 账号删除（个保法删除权）。

铁律：
- 配额按用户每日计数，超限拒绝（防 LLM 费用失控），跨天归零。
- 删除账号必须清空该家庭全部数据（含 V2.4 记忆表），且 token 立即失效。
"""
from __future__ import annotations

import pytest

from app import db


@pytest.fixture
def db_tmp(tmp_path, monkeypatch):
    """每个 db 层测试用独立临时 SQLite 库（不碰真实 data.db）。"""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db


def _count(table: str, fid: int) -> int:
    return db._rows(f"SELECT COUNT(*) AS c FROM {table} WHERE family_id = ?", (fid,))[0]["c"]


# ---------- rate limit 配额 ----------

def test_consume_daily_quota_increments(db_tmp):
    uid = db.create_user("quota_inc", "secret123")["id"]
    assert db.consume_daily_quota(uid, 50) == (False, 1)
    assert db.consume_daily_quota(uid, 50) == (False, 2)
    assert db.consume_daily_quota(uid, 50) == (False, 3)


def test_consume_daily_quota_enforces_limit(db_tmp):
    uid = db.create_user("quota_limit", "secret123")["id"]
    # limit=2：前 2 次允许，第 3 次超限
    assert db.consume_daily_quota(uid, 2) == (False, 1)
    assert db.consume_daily_quota(uid, 2) == (False, 2)
    assert db.consume_daily_quota(uid, 2) == (True, 3)


def test_consume_daily_quota_resets_new_day(db_tmp):
    uid = db.create_user("quota_reset", "secret123")["id"]
    db.consume_daily_quota(uid, 50)  # 今天计 1
    # 手动把日期改成过去，模拟跨天：计数应归零重来
    conn = db.get_conn()
    conn.execute(
        "UPDATE usage_quota SET date = '2000-01-01', count = 99 WHERE user_id = ?", (uid,)
    )
    conn.commit()
    conn.close()
    assert db.consume_daily_quota(uid, 50) == (False, 1)


# ---------- 账号删除 ----------

def _seed_family(fid: int) -> None:
    db.apply_action(fid, {"kind": "person",
                          "fields": {"name": "本人", "relation": "本人", "birth_year": 1990}})
    db.apply_action(fid, {"kind": "income",
                          "fields": {"category": "工资", "amount": 10000, "period": "月"}})
    db.apply_action(fid, {"kind": "expense",
                          "fields": {"category": "日常", "amount": 5000, "period": "月"}})
    db._insert("insurance", {"family_id": fid, "type": "医疗险", "name": "百万医疗",
                             "coverage": 300000, "annual_premium": 5000})
    db.save_judgment(fid, priorities=[{"issue_id": "cashflow", "severity": "P0",
                                       "title": "现金流"}],
                     evidence=[], recommendation="先解决现金流",
                     validity_conditions={"cashflow_surplus": 5000.0})


def test_delete_user_removes_all_data(db_tmp):
    user = db.create_user("delete_me", "secret123")
    uid, fid = user["id"], user["family_id"]
    _seed_family(fid)
    assert _count("person", fid) == 1
    assert _count("insurance", fid) == 1
    assert _count("advisor_judgment", fid) == 1

    db.delete_user(uid)

    # 用户与家庭都没了
    assert db.get_user(uid) is None
    assert db.get_user_by_token(user["token"]) is None
    # 所有 family 关联表清空
    for table in ("person", "cashflow", "insurance", "advisor_judgment"):
        assert _count(table, fid) == 0, f"{table} 应清空"
    # family 行删除
    assert db._rows("SELECT COUNT(*) AS c FROM family WHERE id = ?", (fid,))[0]["c"] == 0


def test_delete_user_missing_is_noop(db_tmp):
    db.delete_user(999999)  # 不存在用户 → 静默返回，不抛异常


# ---------- API 层 ----------

def test_delete_account_api(client, auth_headers):
    token = auth_headers["Authorization"].split(" ", 1)[1]
    user = db.get_user_by_token(token)
    fid = user["family_id"]
    client.post("/api/family/entity/person", headers=auth_headers,
                json={"name": "本人", "relation": "本人", "birth_year": 1990})
    assert _count("person", fid) == 1

    r = client.delete("/api/account", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "deleted": True}

    assert db.get_user(user["id"]) is None
    assert _count("person", fid) == 0
    # 旧 token 立即失效
    assert client.get("/api/me", headers=auth_headers).status_code == 401


def test_agent_chat_rate_limited(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.api.agent._DAILY_LIMIT", 1)
    r1 = client.post("/api/agent/chat", json={"message": "看看我的家庭财富"},
                     headers=auth_headers)
    assert r1.status_code == 200                       # 第 1 次允许
    r2 = client.post("/api/agent/chat", json={"message": "再看看"},
                     headers=auth_headers)
    assert r2.status_code == 429                       # 第 2 次超限
