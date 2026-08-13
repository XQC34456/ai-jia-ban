"""V2 数据迁移测试：幂等 + 版本化 + 字段回填。"""
import sqlite3

from app import db


def _table_names(conn):
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _cols(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


# V1 完整老 schema（无 meta 表、无 V2 列），用于模拟真实的老库升级场景。
_V1_SCHEMA = """
CREATE TABLE family (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'free',
    vip_expires_at TEXT,
    token TEXT,
    family_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(family_id) REFERENCES family(id)
);
CREATE TABLE person (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    relation TEXT,
    birth_year INTEGER,
    monthly_income REAL,
    job TEXT,
    FOREIGN KEY(family_id) REFERENCES family(id)
);
CREATE TABLE asset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    person_id INTEGER,
    type TEXT,
    name TEXT,
    value REAL NOT NULL DEFAULT 0,
    FOREIGN KEY(family_id) REFERENCES family(id)
);
CREATE TABLE liability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    person_id INTEGER,
    type TEXT,
    name TEXT,
    principal REAL,
    monthly_payment REAL,
    interest_rate REAL,
    remaining_months INTEGER,
    FOREIGN KEY(family_id) REFERENCES family(id)
);
CREATE TABLE cashflow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    person_id INTEGER,
    flow_type TEXT NOT NULL,
    category TEXT,
    amount REAL NOT NULL,
    period TEXT DEFAULT '月',
    FOREIGN KEY(family_id) REFERENCES family(id)
);
CREATE TABLE goal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    type TEXT,
    name TEXT,
    target_amount REAL,
    target_date TEXT,
    current_saved REAL DEFAULT 0,
    monthly_contribution REAL DEFAULT 0,
    FOREIGN KEY(family_id) REFERENCES family(id)
);
CREATE TABLE reminder (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    rtype TEXT,
    title TEXT NOT NULL,
    due_date TEXT,
    status TEXT DEFAULT '待处理',
    FOREIGN KEY(family_id) REFERENCES family(id)
);
"""


def _init_v1_db(tmp_path, monkeypatch):
    """建一个完整 V1 老库（无 V2 列），插入一条家庭 + 示例资产/目标。"""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    conn = sqlite3.connect(str(tmp_path / "t.db"))
    conn.executescript(_V1_SCHEMA)
    conn.execute("INSERT INTO family (name, created_at) VALUES ('测试家庭', '2026-08-13')")
    for t, n, v in [("房产", "自住房", 3000000), ("存款", "活期", 500000), ("股票", "某股", 100000)]:
        conn.execute("INSERT INTO asset (family_id, type, name, value) VALUES (1, ?, ?, ?)", (t, n, v))
    conn.execute("INSERT INTO goal (family_id, type, name, target_amount) VALUES (1, '教育', '教育金', 1000000)")
    conn.commit()
    conn.close()


def test_migration_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.init_db()
    db.migrate()  # 第二次执行不得报错
    conn = db.get_conn()
    assert "meta" in _table_names(conn)
    conn.close()


def test_schema_version_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.init_db()
    conn = db.get_conn()
    row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    assert row is not None
    conn.close()


def test_migrate_asset_class_backfill(tmp_path, monkeypatch):
    """V1 老库升级：asset 加列 + 按 type 回填资产大类。"""
    _init_v1_db(tmp_path, monkeypatch)
    db.migrate()
    conn = db.get_conn()
    assert "asset_class" in _cols(conn, "asset")
    assert "liquidity" in _cols(conn, "asset")
    rows = conn.execute("SELECT type, asset_class FROM asset ORDER BY id").fetchall()
    got = {r[0]: r[1] for r in rows}
    assert got == {"房产": "real_estate", "存款": "cash", "股票": "equity"}
    conn.close()


def test_migrate_goal_kind_backfill(tmp_path, monkeypatch):
    """V1 老库升级：goal 加列 + 回填默认目标类型/优先级/风险容忍。"""
    _init_v1_db(tmp_path, monkeypatch)
    db.migrate()
    conn = db.get_conn()
    assert "goal_kind" in _cols(conn, "goal")
    r = conn.execute("SELECT goal_kind, priority, risk_tolerance FROM goal WHERE name='教育金'").fetchone()
    assert r["goal_kind"] == "lump_sum"
    assert r["priority"] == 2
    assert r["risk_tolerance"] == "balanced"
    conn.close()


def test_migrate_new_tables(tmp_path, monkeypatch):
    """V1 老库升级：新建 insurance / family_profile / scenario_snapshot 三张表。"""
    _init_v1_db(tmp_path, monkeypatch)
    db.migrate()
    conn = db.get_conn()
    names = _table_names(conn)
    assert {"insurance", "family_profile", "scenario_snapshot"} <= names
    conn.execute("INSERT INTO insurance (family_id, type, name, annual_premium, coverage) "
                 "VALUES (1, '重疾', '重疾险', 8000, 500000)")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM insurance").fetchone()[0] == 1
    conn.close()


def test_dump_family_includes_insurance(tmp_path, monkeypatch):
    """dump_family 应包含保险（保障/风险转移是独立模型，不算投资资产）。"""
    _init_v1_db(tmp_path, monkeypatch)
    db.migrate()
    conn = db.get_conn()
    conn.execute("INSERT INTO insurance (family_id, type, name, annual_premium, coverage) "
                 "VALUES (1, '重疾', '重疾险', 8000, 500000)")
    conn.commit()
    conn.close()
    data = db.dump_family(1)
    assert "insurance" in data
    assert "family_profile" in data
    assert len(data["insurance"]) == 1
    assert data["insurance"][0]["coverage"] == 500000
