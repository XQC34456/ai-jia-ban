"""冷启动 Humanization：典型值构造器 + preview 接口（不落库）。"""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.services.onboarding import typical_family


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def _register(c, username="coldstart", password="secret123"):
    r = c.post("/api/register", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


# ---------- Task 1: typical_family 纯函数 ----------

def test_typical_family_high():
    d = typical_family({"assets": "high", "income": "high", "debt": "high", "savings": "high"})
    inc = d["cashflows"][0]["amount"]
    assert inc == 80000
    assert sum(a["value"] for a in d["assets"]) == 5_000_000
    assert d["liabilities"][0]["principal"] == 2_000_000


def test_typical_family_unknown_is_mid():
    d = typical_family({})  # 全 unknown → mid 中性
    assert d["cashflows"][0]["amount"] == 30000
    assert d["assets"][0]["value"] == 2_000_000 * 0.4


def test_typical_family_low_has_no_liability():
    d = typical_family({"debt": "low"})
    assert d["liabilities"] == []


def test_typical_family_builds_overview():
    # 构造器产出的 family_data 必须能被 build_overview 正常实算（不落库、不抛异常）
    from app.services import build_overview
    d = typical_family({"assets": "mid", "income": "mid", "debt": "mid", "savings": "mid"})
    ov = build_overview(d)
    assert ov["wealth_score"] is not None
    assert ov["net_worth"] == 2_000_000 - 500_000
    assert isinstance(ov["issues"], list)


# ---------- Task 2: preview 接口（不落库） ----------

def test_preview_returns_overview_and_issues(client):
    u = _register(client)
    h = {"Authorization": "Bearer " + u["token"]}
    r = client.post("/api/onboarding/preview",
                    json={"interests": ["asset", "safety"],
                          "profile": {"assets": "high", "income": "mid", "debt": "low"}},
                    headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["interests"] == ["asset", "safety"]
    assert body["overview"]["wealth_score"] is not None
    assert isinstance(body["overview"]["issues"], list)


def test_preview_does_not_write_db(client):
    u = _register(client)
    h = {"Authorization": "Bearer " + u["token"]}

    before = client.get("/api/family", headers=h).json()["data"]
    assert before["assets"] == [] and before["persons"] == []

    r = client.post("/api/onboarding/preview",
                    json={"interests": [], "profile": {}}, headers=h)
    assert r.status_code == 200

    after = client.get("/api/family", headers=h).json()["data"]
    assert after["assets"] == [] and after["persons"] == [], "preview 绝不写库"


def test_preview_requires_auth(client):
    assert client.post("/api/onboarding/preview", json={"interests": []}).status_code == 401
