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
    monthly_income REAL,         -- ⚠️ 遗留双口径：收入真相源是 cashflow(flow_type=income)；Engine 只读 cashflow，V2.1 Context 统一从 build_overview.cashflow.income 取，勿读此列
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

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
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
    migrate()


def migrate() -> None:
    """幂等迁移：按 schema_version 递增执行。后续 V2 迁移在此按版本追加。"""
    conn = get_conn()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        cur = conn.execute("SELECT value FROM meta WHERE key='schema_version'")
        row = cur.fetchone()
        version = int(row[0]) if row else 0
        if version < 1:
            _migrate_v1(conn)
            version = 1
        if version < 2:
            _migrate_v2(conn)
            version = 2
        if version < 3:
            _migrate_v3(conn)
            version = 3
        if version < 4:
            _migrate_v4(conn)
            version = 4
        if version < 5:
            _migrate_v5(conn)
            version = 5
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(version),),
        )
        conn.commit()
    finally:
        conn.close()


def _add_column_if_missing(conn: sqlite3.Connection, table: str, col: str, ddl: str) -> None:
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if col not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


_ASSET_CLASS_MAP = {
    "房产": "real_estate", "存款": "cash", "理财": "fixed_income",
    "基金": "fixed_income", "股票": "equity", "保险现金价值": "other", "其他": "other",
}


def _migrate_v1(conn: sqlite3.Connection) -> None:
    """V2.0：asset 表新增资产大类/流动性/成本/收益/风险/子类 6 列，并按 type 回填大类。"""
    for col, ddl in [
        ("asset_class", "TEXT"),
        ("liquidity", "TEXT"),
        ("cost_basis", "REAL"),
        ("expected_return", "REAL"),
        ("risk_level", "TEXT"),
        ("sub_type", "TEXT"),
    ]:
        _add_column_if_missing(conn, "asset", col, ddl)
    for old_type, new_class in _ASSET_CLASS_MAP.items():
        conn.execute(
            "UPDATE asset SET asset_class = ? WHERE type = ? AND asset_class IS NULL",
            (new_class, old_type),
        )


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """V2.0：goal 表新增现金流型目标字段（kind/年度金额/年限/起始年/优先级/风险容忍）。"""
    for col, ddl in [
        ("goal_kind", "TEXT"),
        ("annual_amount", "REAL"),
        ("duration_years", "INTEGER"),
        ("start_year", "INTEGER"),
        ("priority", "INTEGER"),
        ("risk_tolerance", "TEXT"),
    ]:
        _add_column_if_missing(conn, "goal", col, ddl)
    conn.execute("UPDATE goal SET goal_kind = 'lump_sum' WHERE goal_kind IS NULL")
    conn.execute("UPDATE goal SET priority = 2 WHERE priority IS NULL")
    conn.execute("UPDATE goal SET risk_tolerance = 'balanced' WHERE risk_tolerance IS NULL")


def _migrate_v3(conn: sqlite3.Connection) -> None:
    """V2.0：新建保险/家庭画像/情景快照三张表。

    保险作为「保障/风险转移」独立建模，不进入权益/固收/现金占比。
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS insurance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL,
            person_id INTEGER,
            type TEXT,
            name TEXT,
            annual_premium REAL,
            coverage REAL,
            cash_value REAL,
            start_date TEXT,
            maturity_date TEXT,
            FOREIGN KEY(family_id) REFERENCES family(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS family_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL UNIQUE,
            risk_profile TEXT DEFAULT 'balanced',
            investment_horizon INTEGER DEFAULT 10,
            risk_answers TEXT,
            FOREIGN KEY(family_id) REFERENCES family(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scenario_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL,
            scenario TEXT NOT NULL,
            params_json TEXT,
            result_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(family_id) REFERENCES family(id)
        )
    """)


def _migrate_v4(conn: sqlite3.Connection) -> None:
    """V2.4：新建 Advisor Memory 三张表（短期对话 / 家庭事实 / 顾问判断）。

    记忆层只存「历史 + 判断 + 依据」，绝不参与财富计算（Engine 只读主表）。
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL,
            turn INTEGER NOT NULL,
            role TEXT NOT NULL,
            message TEXT,
            intent TEXT,
            tool_calls TEXT,
            corrected INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(family_id) REFERENCES family(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_fact (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            source TEXT NOT NULL,
            confidence TEXT NOT NULL,
            version INTEGER NOT NULL,
            superseded_by INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(family_id) REFERENCES family(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS advisor_judgment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL,
            priorities TEXT NOT NULL,
            evidence TEXT,
            recommendation TEXT,
            validity_conditions TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            invalidated_at TEXT,
            FOREIGN KEY(family_id) REFERENCES family(id)
        )
    """)


def _migrate_v5(conn: sqlite3.Connection) -> None:
    """内测：新增每日对话配额表（rate limit，防 DeepSeek 费用失控）。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_quota (
            user_id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)


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


def get_insurances(family_id: int) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM insurance WHERE family_id = ?", (family_id,))


def get_family_profile(family_id: int) -> Optional[dict[str, Any]]:
    rows = _rows("SELECT * FROM family_profile WHERE family_id = ?", (family_id,))
    return rows[0] if rows else None


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
        "insurance": get_insurances(family_id),
        "family_profile": get_family_profile(family_id),
    }


# ---------- V2.4 Advisor Memory（只存历史+判断，绝不参与财富计算） ----------

def append_conversation(family_id: int, role: str, message: str | None,
                        intent: str | None = None, tool_calls: list[str] | None = None,
                        corrected: bool = False) -> int:
    """追加一条对话消息（turn 自动递增）。assistant 轮存「结论摘要」非全文。"""
    conn = get_conn()
    try:
        turn = conn.execute(
            "SELECT COALESCE(MAX(turn), 0) + 1 FROM conversation_message WHERE family_id = ?",
            (family_id,),
        ).fetchone()[0]
        tc = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None
        cur = conn.execute(
            "INSERT INTO conversation_message "
            "(family_id, turn, role, message, intent, tool_calls, corrected, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (family_id, turn, role, message, intent, tc, int(corrected), _now()),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def recent_conversations(family_id: int, n: int) -> list[dict[str, Any]]:
    """返回最近 n 条对话消息（按 turn 倒序，最新在前）。JSON 字段反序列化。"""
    rows = _rows(
        "SELECT * FROM conversation_message WHERE family_id = ? ORDER BY turn DESC LIMIT ?",
        (family_id, n),
    )
    for r in rows:
        r["tool_calls"] = json.loads(r["tool_calls"]) if r["tool_calls"] else None
        r["corrected"] = bool(r["corrected"])
    return rows


def upsert_fact(family_id: int, key: str, value: str, source: str, confidence: str) -> int:
    """写入/更新一条家庭事实（版本化）。

    相同 value+source → 幂等返回现有 id；否则 version+1，旧版本 superseded_by 指向新 id。
    """
    conn = get_conn()
    try:
        current = conn.execute(
            "SELECT * FROM memory_fact WHERE family_id = ? AND key = ? AND superseded_by IS NULL",
            (family_id, key),
        ).fetchone()
        if current and current["value"] == value and current["source"] == source:
            return int(current["id"])
        version = conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM memory_fact WHERE family_id = ? AND key = ?",
            (family_id, key),
        ).fetchone()[0]
        now = _now()
        cur = conn.execute(
            "INSERT INTO memory_fact "
            "(family_id, key, value, source, confidence, version, superseded_by, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)",
            (family_id, key, value, source, confidence, version, now, now),
        )
        new_id = int(cur.lastrowid)
        if current:
            conn.execute(
                "UPDATE memory_fact SET superseded_by = ? WHERE id = ?",
                (new_id, current["id"]),
            )
        conn.commit()
        return new_id
    finally:
        conn.close()


def current_facts(family_id: int) -> list[dict[str, Any]]:
    """返回当前有效事实（superseded_by IS NULL）。历史版本仅供失效检测，不在此返回。"""
    return _rows(
        "SELECT * FROM memory_fact WHERE family_id = ? AND superseded_by IS NULL",
        (family_id,),
    )


def save_judgment(family_id: int, priorities: list[dict], evidence: list[dict] | None,
                  recommendation: str | None, validity_conditions: dict) -> int:
    """写入一条顾问判断；旧 active 置 stale（每个家庭最多一条 active）。"""
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE advisor_judgment SET status = 'stale', invalidated_at = ? "
            "WHERE family_id = ? AND status = 'active'",
            (_now(), family_id),
        )
        cur = conn.execute(
            "INSERT INTO advisor_judgment "
            "(family_id, priorities, evidence, recommendation, validity_conditions, "
            "status, created_at) VALUES (?, ?, ?, ?, ?, 'active', ?)",
            (family_id,
             json.dumps(priorities, ensure_ascii=False),
             json.dumps(evidence, ensure_ascii=False) if evidence else None,
             recommendation,
             json.dumps(validity_conditions, ensure_ascii=False),
             _now()),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def latest_judgment(family_id: int) -> dict[str, Any] | None:
    """返回最近一条顾问判断（含 stale）。JSON 字段反序列化。"""
    rows = _rows(
        "SELECT * FROM advisor_judgment WHERE family_id = ? ORDER BY id DESC LIMIT 1",
        (family_id,),
    )
    if not rows:
        return None
    r = rows[0]
    r["priorities"] = json.loads(r["priorities"]) if r["priorities"] else []
    r["evidence"] = json.loads(r["evidence"]) if r["evidence"] else []
    r["validity_conditions"] = (json.loads(r["validity_conditions"])
                                if r["validity_conditions"] else {})
    return r


def invalidate_judgment(judgment_id: int) -> None:
    """把指定判断标记为 stale（失效），记录 invalidated_at。"""
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE advisor_judgment SET status = 'stale', invalidated_at = ? WHERE id = ?",
            (_now(), judgment_id),
        )
        conn.commit()
    finally:
        conn.close()


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


# ---------- 内测护栏：每日对话配额 + 账号删除 ----------

def consume_daily_quota(user_id: int, limit: int) -> tuple[bool, int]:
    """内测配额：原子递增用户当日对话计数，返回 (是否超限, 已用次数)。

    日期按服务器本地日翻转；count 每天归零。本次调用后 used > limit 即视为
    超限（即 limit 次内允许，第 limit+1 次拒绝）。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT date, count FROM usage_quota WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO usage_quota (user_id, date, count) VALUES (?, ?, 1)",
                (user_id, today),
            )
            used = 1
        elif row["date"] != today:
            conn.execute(
                "UPDATE usage_quota SET date = ?, count = 1 WHERE user_id = ?",
                (today, user_id),
            )
            used = 1
        else:
            used = row["count"] + 1
            conn.execute(
                "UPDATE usage_quota SET count = ? WHERE user_id = ?", (used, user_id)
            )
        conn.commit()
        return (used > limit, used)
    finally:
        conn.close()


# 所有带 family_id 外键的实体表（账号删除时逐表清理；内部白名单，非用户输入）
_FAMILY_TABLES = [
    "person", "asset", "liability", "cashflow", "goal", "reminder",
    "insurance", "family_profile", "scenario_snapshot",
    "conversation_message", "memory_fact", "advisor_judgment",
]


def delete_user(user_id: int) -> None:
    """删除用户及其家庭全部数据（个保法删除权）。

    先删配额与所有 family 关联实体（含 V2.4 记忆表），再删用户与 family 行。
    """
    user = get_user(user_id)
    if user is None:
        return
    fid = user["family_id"]
    conn = get_conn()
    try:
        conn.execute("DELETE FROM usage_quota WHERE user_id = ?", (user_id,))
        if fid:
            for table in _FAMILY_TABLES:
                conn.execute(f"DELETE FROM {table} WHERE family_id = ?", (fid,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        if fid:
            conn.execute("DELETE FROM family WHERE id = ?", (fid,))
        conn.commit()
    finally:
        conn.close()
