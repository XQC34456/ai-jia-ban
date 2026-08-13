"""Wealth Overview API 集成测试。"""
from app import db


def _add(client, h, table, payload):
    r = client.post(f"/api/family/entity/{table}", headers=h, json=payload)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_overview_requires_auth(client):
    assert client.get("/api/wealth/overview").status_code == 401
    assert client.get("/api/wealth/issues").status_code == 401


def test_overview_free_tier_accessible(client, auth_headers):
    r = client.get("/api/wealth/overview", headers=auth_headers)
    assert r.status_code == 200
    o = r.json()
    for k in ("wealth_score", "wealth_level", "net_worth", "asset_allocation",
              "cashflow", "liquidity", "debt", "protection", "goals", "retirement",
              "issues", "alerts", "priorities", "recommendations"):
        assert k in o, f"缺少键 {k}"
    assert 0 <= o["wealth_score"] <= 100


def test_overview_retirement_quadrant(client, auth_headers):
    _add(client, auth_headers, "person", {"name": "本人", "relation": "本人", "birth_year": 1976})
    _add(client, auth_headers, "asset", {"type": "房产", "value": 8000000})
    _add(client, auth_headers, "asset", {"type": "存款", "value": 100000})
    _add(client, auth_headers, "cashflow", {"flow_type": "income", "amount": 30000, "period": "月"})
    _add(client, auth_headers, "cashflow", {"flow_type": "expense", "amount": 28000, "period": "月"})

    o = client.get("/api/wealth/overview", headers=auth_headers).json()
    r = o["retirement"]
    assert r is not None
    assert r["quadrant"] == "资产充足但流动性不足"
    assert r["rfr"] < 1 and r["nwc"] >= 1
    # Decision Layer 同步识别出养老流动性问题
    assert any(i["type"] == "retirement" and i["severity"] == "P0" for i in o["issues"])


def test_issues_endpoint(client, auth_headers):
    r = client.get("/api/wealth/issues", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"issues", "alerts", "priorities", "recommendations"}


def test_overview_data_isolated(client):
    # 两个用户各自的数据互不影响
    r1 = client.post("/api/register", json={"username": "a", "password": "secret123"}).json()
    r2 = client.post("/api/register", json={"username": "b", "password": "secret123"}).json()
    h1 = {"Authorization": "Bearer " + r1["token"]}
    h2 = {"Authorization": "Bearer " + r2["token"]}
    _add(client, h1, "asset", {"type": "存款", "value": 999999})
    o1 = client.get("/api/wealth/overview", headers=h1).json()
    o2 = client.get("/api/wealth/overview", headers=h2).json()
    assert o1["total_assets"] == 999999
    assert o2["total_assets"] == 0
