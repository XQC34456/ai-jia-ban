"""V2 数据迁移测试：幂等 + 版本化 + 字段回填。"""
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
