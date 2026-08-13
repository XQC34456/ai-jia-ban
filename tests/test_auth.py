"""鉴权与 VIP 分层集成测试。"""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def _register(c, username="alice", password="secret123"):
    r = c.post("/api/register", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def test_register_login_flow(client):
    u = _register(client)
    assert u["username"] == "alice"
    assert u["tier"] == "free"
    assert u["token"]

    # 重复注册 → 409
    r = client.post("/api/register", json={"username": "alice", "password": "secret123"})
    assert r.status_code == 409

    # 正确登录
    r = client.post("/api/login", json={"username": "alice", "password": "secret123"})
    assert r.status_code == 200
    assert r.json()["tier"] == "free"

    # 错误密码 → 401
    r = client.post("/api/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401

    # 密码太短 → 400
    r = client.post("/api/register", json={"username": "bob", "password": "123"})
    assert r.status_code == 400


def test_free_user_blocked_from_vip_features(client):
    u = _register(client)
    h = {"Authorization": "Bearer " + u["token"]}

    assert client.get("/api/report", headers=h).status_code == 403
    assert client.post("/api/decision", headers=h,
                       json={"scenario": "buy_house", "params": {"price": 1000000}}).status_code == 403

    # 免费功能可用
    assert client.get("/api/family", headers=h).status_code == 200
    assert client.post("/api/agent/chat", headers=h,
                       json={"message": "我月薪2万"}).status_code == 200


def test_upgrade_unlocks_vip(client):
    u = _register(client)
    h = {"Authorization": "Bearer " + u["token"]}

    r = client.post("/api/upgrade", headers=h)
    assert r.status_code == 200
    assert r.json()["tier"] == "vip"

    # 升级后报告可访问
    assert client.get("/api/report", headers=h).status_code == 200
    # /api/me 反映新 tier
    assert client.get("/api/me", headers=h).json()["tier"] == "vip"


def test_data_isolation(client):
    a = _register(client, "alice", "secret123")
    b = _register(client, "bob", "secret456")
    ha = {"Authorization": "Bearer " + a["token"]}
    hb = {"Authorization": "Bearer " + b["token"]}

    client.post("/api/family/entity/asset", headers=ha,
                json={"name": "存款", "type": "存款", "value": 100000})

    fa = client.get("/api/family", headers=ha).json()
    fb = client.get("/api/family", headers=hb).json()
    assert len(fa["data"]["assets"]) == 1
    assert len(fb["data"]["assets"]) == 0

    # b 不能改 a 的实体
    asset_id = fa["data"]["assets"][0]["id"]
    r = client.delete(f"/api/entity/asset/{asset_id}", headers=hb)
    assert r.status_code == 403


def test_unauthorized(client):
    assert client.get("/api/family").status_code == 401
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/report").status_code == 401
