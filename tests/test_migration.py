"""V2 数据迁移测试：幂等 + 版本化 + 字段回填。"""
import sqlite3

from app import db


def _table_names(conn):
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _cols(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


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
    """模拟老库（无 asset_class 列）升级：加列 + 回填资产大类。"""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    conn = sqlite3.connect(str(tmp_path / "t.db"))
    conn.executescript("""
        CREATE TABLE family (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE asset (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL,
            person_id INTEGER,
            type TEXT, name TEXT,
            value REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    conn.execute("INSERT INTO family (name, created_at) VALUES ('测试家庭', '2026-08-13')")
    for t, n, v in [("房产", "自住房", 3000000), ("存款", "活期", 500000), ("股票", "某股", 100000)]:
        conn.execute("INSERT INTO asset (family_id, type, name, value) VALUES (1, ?, ?, ?)", (t, n, v))
    conn.commit()
    conn.close()

    db.migrate()

    conn = db.get_conn()
    assert "asset_class" in _cols(conn, "asset")
    assert "liquidity" in _cols(conn, "asset")
    rows = conn.execute("SELECT type, asset_class FROM asset ORDER BY id").fetchall()
    got = {r[0]: r[1] for r in rows}
    assert got == {"房产": "real_estate", "存款": "cash", "股票": "equity"}
    conn.close()
