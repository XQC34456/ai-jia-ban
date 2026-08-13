"""确保 `from app import ...` 在测试中可用，并提供共享测试 fixture。"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(__file__))

from app import db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    """每个测试用独立的临时 SQLite 数据库。"""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    """注册一个用户并返回其 Authorization headers（free tier）。"""
    r = client.post("/api/register", json={"username": "tester", "password": "secret123"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


@pytest.fixture
def family_id(client):
    """创建一个空家庭并返回其 family_id（直接走 db 层，独立于鉴权）。"""
    return db.create_family("测试家庭")
