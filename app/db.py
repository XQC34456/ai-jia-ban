"""数据层：SQLite + 轻量 CRUD。

MVP 用内置 sqlite3，零外部依赖；生产可平滑迁移到 SQLAlchemy + PostgreSQL。
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

DB_PATH = os.environ.get("AIJIABAN_DB", os.path.join(os.path.dirname(__file__), "..", "data.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS family (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'free',  -- free / vip
    vip_expires_at TEXT,                -- NULL=永久；预留「注册送试用」的到期时间
    token TEXT,
    family_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(family_id) REFERENCES family(id)
);

CREATE TABLE IF NOT EXISTS person (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    relation TEXT,               -- 本人/配偶/子女/老人/其他
    birth_year INTEGER,
    monthly_income REAL,
    job TEXT,
    FOREIGN KEY(family_id) REFERENCES family(id)
);

CREATE TABLE IF NOT EXISTS asset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    person_id INTEGER,
    type TEXT,                   -- 房产/存款/基金/股票/理财/保险现金价值/其他
    name TEXT,
    value REAL NOT NULL DEFAULT 0,
    FOREIGN KEY(family_id) REFERENCES family(id)
);

CREATE TABLE IF NOT EXISTS liability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    person_id INTEGER,
    type TEXT,                   -- 房贷/车贷/消费贷/信用卡/其他
    name TEXT,
    principal REAL,              -- 剩余本金
    monthly_payment REAL,        -- 月供
    interest_rate REAL,
    remaining_months INTEGER,
    FOREIGN KEY(family_id) REFERENCES family(id)
);

CREATE TABLE IF NOT EXISTS cashflow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    person_id INTEGER,
    flow_type TEXT NOT NULL,     -- income / expense
    category TEXT,
    amount REAL NOT NULL,
    period TEXT DEFAULT '月',     -- 月 / 年
    FOREIGN KEY(family_id) REFERENCES family(id)
);

CREATE TABLE IF NOT EXISTS goal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    type TEXT,                   -- 教育/养老/买房/创业/其他
    name TEXT,
    target_amount REAL,
    target_date TEXT,
    current_saved REAL DEFAULT 0,
    monthly_contribution REAL DEFAULT 0,
    FOREIGN KEY(family_id) REFERENCES family(id)
);

CREATE TABLE IF NOT EXISTS reminder (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    rtype TEXT,                  -- 时间/财务/风险/目标/决策
    title TEXT NOT NULL,
    due_date TEXT,
    status TEXT DEFAULT '待处理',
    FOREIGN KEY(family_id) REFERENCES family(id)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def create_family(name: str = "我的家庭") -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO family (name, created_at) VALUES (?, ?)", (name, _now())
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def _insert(table: str, data: dict[str, Any]) -> int:
    conn = get_conn()
    try:
        cols = ", ".join(data.keys())
        marks = ", ".join("?" for _ in data)
        cur = conn.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(data.values())
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def _rows(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ---------- 领域对象查询 ----------

def get_family(family_id: int) -> Optional[dict[str, Any]]:
    rows = _rows("SELECT * FROM family WHERE id = ?", (family_id,))
    return rows[0] if rows else None


def get_persons(family_id: int) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM person WHERE family_id = ?", (family_id,))


def get_assets(family_id: int) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM asset WHERE family_id = ?", (family_id,))


def get_liabilities(family_id: int) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM liability WHERE family_id = ?", (family_id,))


def get_cashflows(family_id: int) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM cashflow WHERE family_id = ?", (family_id,))


def get_goals(family_id: int) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM goal WHERE family_id = ?", (family_id,))


def get_reminders(family_id: int) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM reminder WHERE family_id = ?", (family_id,))


def find_person_by_name(family_id: int, name: str) -> Optional[dict[str, Any]]:
    rows = _rows("SELECT * FROM person WHERE family_id = ? AND name = ?", (family_id, name))
    return rows[0] if rows else None


def dump_family(family_id: int) -> dict[str, Any]:
    """导出家庭完整数据（快照用）。"""
    return {
        "family": get_family(family_id),
        "persons": get_persons(family_id),
        "assets": get_assets(family_id),
        "liabilities": get_liabilities(family_id),
        "cashflows": get_cashflows(family_id),
        "goals": get_goals(family_id),
        "reminders": get_reminders(family_id),
    }


# ---------- 对话抽取动作的落地 ----------

def apply_action(family_id: int, action: dict[str, Any]) -> None:
    """把一个建档动作写入数据库。action 由 extraction 层产出。"""
    kind = action["kind"]
    f = action["fields"]
    person_id = None
    if "person_name" in f and f["person_name"]:
        p = find_person_by_name(family_id, f["person_name"])
        person_id = p["id"] if p else None

    if kind == "person":
        _insert("person", {
            "family_id": family_id,
            "name": f.get("name", ""),
            "relation": f.get("relation"),
            "birth_year": f.get("birth_year"),
            "monthly_income": f.get("monthly_income"),
            "job": f.get("job"),
        })
    elif kind == "income":
        _insert("cashflow", {
            "family_id": family_id,
            "person_id": person_id,
            "flow_type": "income",
            "category": f.get("category", "工资"),
            "amount": f.get("amount", 0),
            "period": f.get("period", "月"),
        })
    elif kind == "expense":
        _insert("cashflow", {
            "family_id": family_id,
            "person_id": person_id,
            "flow_type": "expense",
            "category": f.get("category", "其他"),
            "amount": f.get("amount", 0),
            "period": f.get("period", "月"),
        })
    elif kind == "asset":
        _insert("asset", {
            "family_id": family_id,
            "person_id": person_id,
            "type": f.get("type", "其他"),
            "name": f.get("name", ""),
            "value": f.get("value", 0),
        })
    elif kind == "liability":
        _insert("liability", {
            "family_id": family_id,
            "person_id": person_id,
            "type": f.get("type", "其他"),
            "name": f.get("name", ""),
            "principal": f.get("principal"),
            "monthly_payment": f.get("monthly_payment"),
            "interest_rate": f.get("interest_rate"),
            "remaining_months": f.get("remaining_months"),
        })
    elif kind == "goal":
        _insert("goal", {
            "family_id": family_id,
            "type": f.get("type", "其他"),
            "name": f.get("name", ""),
            "target_amount": f.get("target_amount"),
            "target_date": f.get("target_date"),
            "current_saved": f.get("current_saved", 0),
            "monthly_contribution": f.get("monthly_contribution", 0),
        })
    else:
        raise ValueError(f"未知动作类型: {kind}")


# ---------- 看板直接编辑的通用 CRUD ----------

# 每个实体允许写入的列白名单（同时防 SQL 注入）；值为类型，用于把 JSON 值强转。
ENTITY_COLS: dict[str, dict[str, type]] = {
    "person": {"name": str, "relation": str, "birth_year": int, "monthly_income": float, "job": str},
    "asset": {"type": str, "name": str, "value": float},
    "liability": {"type": str, "name": str, "principal": float, "monthly_payment": float,
                  "interest_rate": float, "remaining_months": int},
    "cashflow": {"flow_type": str, "category": str, "amount": float, "period": str},
    "goal": {"type": str, "name": str, "target_amount": float, "target_date": str,
             "current_saved": float, "monthly_contribution": float},
}


def _coerce_entity(table: str, data: dict[str, Any]) -> dict[str, Any]:
    """只保留白名单列，并把值强转成列声明的类型；空串/None 记为 None。"""
    spec = ENTITY_COLS[table]
    out: dict[str, Any] = {}
    for k, v in data.items():
        if k not in spec:
            continue
        if v is None or v == "":
            out[k] = None
            continue
        try:
            out[k] = spec[k](v)
        except (ValueError, TypeError):
            out[k] = None
    return out


def create_entity(table: str, family_id: int, data: dict[str, Any]) -> int:
    """新增一条实体记录（看板手动录入）。跳过 None 字段，交给数据库默认值。"""
    coerced = _coerce_entity(table, data)
    row = {k: v for k, v in coerced.items() if v is not None}
    row["family_id"] = family_id
    return _insert(table, row)


def update_entity(table: str, entity_id: int, data: dict[str, Any]) -> None:
    """按 id 更新实体（只更新传入的非空字段）。"""
    coerced = _coerce_entity(table, data)
    cols = [k for k in coerced if coerced[k] is not None]
    if not cols:
        return
    set_clause = ", ".join(f"{c} = ?" for c in cols)
    vals = [coerced[c] for c in cols] + [entity_id]
    conn = get_conn()
    try:
        conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", tuple(vals))
        conn.commit()
    finally:
        conn.close()


def delete_entity(table: str, entity_id: int) -> None:
    conn = get_conn()
    try:
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (entity_id,))
        conn.commit()
    finally:
        conn.close()


def get_entity_owner(table: str, entity_id: int) -> Optional[int]:
    """返回实体所属的 family_id（用于数据隔离校验）。"""
    rows = _rows(f"SELECT family_id FROM {table} WHERE id = ?", (entity_id,))
    return rows[0]["family_id"] if rows else None


# ---------- 用户与鉴权 ----------

def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()


def create_user(username: str, password: str) -> dict[str, Any]:
    """注册：自动创建一个家庭并绑定，返回用户记录。"""
    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    family_id = create_family("我的家庭")
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, salt, tier, family_id, created_at) "
            "VALUES (?, ?, ?, 'free', ?, ?)",
            (username, password_hash, salt, family_id, _now()),
        )
        conn.commit()
        return get_user(int(cur.lastrowid))
    finally:
        conn.close()


def get_user(user_id: int) -> Optional[dict[str, Any]]:
    rows = _rows("SELECT * FROM users WHERE id = ?", (user_id,))
    return rows[0] if rows else None


def get_user_by_username(username: str) -> Optional[dict[str, Any]]:
    rows = _rows("SELECT * FROM users WHERE username = ?", (username,))
    return rows[0] if rows else None


def verify_user(username: str, password: str) -> Optional[dict[str, Any]]:
    user = get_user_by_username(username)
    if user is None or _hash_password(password, user["salt"]) != user["password_hash"]:
        return None
    return user


def set_token(user_id: int, token: str) -> None:
    conn = get_conn()
    try:
        conn.execute("UPDATE users SET token = ? WHERE id = ?", (token, user_id))
        conn.commit()
    finally:
        conn.close()


def get_user_by_token(token: str) -> Optional[dict[str, Any]]:
    if not token:
        return None
    rows = _rows("SELECT * FROM users WHERE token = ?", (token,))
    return rows[0] if rows else None


def set_tier(user_id: int, tier: str) -> None:
    """设置权益等级；清空试用到期时间（手动开通 = 永久 VIP）。"""
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE users SET tier = ?, vip_expires_at = NULL WHERE id = ?",
            (tier, user_id),
        )
        conn.commit()
    finally:
        conn.close()
