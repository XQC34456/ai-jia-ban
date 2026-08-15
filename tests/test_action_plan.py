"""行动计划 API 集成测试：采纳 / 去重 / 状态流转 / 白名单 / 鉴权。"""
from app import db  # noqa: F401  (确保 app 包可导入，与 conftest 一致)


def test_create_and_list(client, auth_headers):
    r1 = client.post("/api/wealth/action-plan", headers=auth_headers,
                     json={"issue_id": "DEBT_HIGH_001", "action": "降低负债", "detail": "优先还高息贷"})
    assert r1.status_code == 200, r1.text
    assert r1.json()["id"] is not None
    r2 = client.post("/api/wealth/action-plan", headers=auth_headers,
                     json={"issue_id": "CASHFLOW_NEGATIVE_001", "action": "减少不必要开支", "detail": None})
    assert r2.status_code == 200, r2.text
    plans = client.get("/api/wealth/action-plan", headers=auth_headers).json()["plans"]
    assert len(plans) == 2
    assert {p["action"] for p in plans} == {"降低负债", "减少不必要开支"}


def test_dedup(client, auth_headers):
    payload = {"issue_id": "DEBT_HIGH_001", "action": "降低负债", "detail": "x"}
    r1 = client.post("/api/wealth/action-plan", headers=auth_headers, json=payload)
    r2 = client.post("/api/wealth/action-plan", headers=auth_headers, json=payload)
    assert r1.json()["id"] is not None
    assert r2.json()["id"] is None          # 重复采纳 → 不新增
    plans = client.get("/api/wealth/action-plan", headers=auth_headers).json()["plans"]
    assert len(plans) == 1


def test_update_status(client, auth_headers):
    pid = client.post("/api/wealth/action-plan", headers=auth_headers,
                      json={"issue_id": "X", "action": "A"}).json()["id"]
    r = client.put(f"/api/wealth/action-plan/{pid}", headers=auth_headers, json={"status": "done"})
    assert r.status_code == 200, r.text
    plans = client.get("/api/wealth/action-plan", headers=auth_headers).json()["plans"]
    assert plans[0]["status"] == "done"


def test_status_whitelist(client, auth_headers):
    pid = client.post("/api/wealth/action-plan", headers=auth_headers,
                      json={"issue_id": "X", "action": "A"}).json()["id"]
    r = client.put(f"/api/wealth/action-plan/{pid}", headers=auth_headers, json={"status": "bogus"})
    assert r.status_code == 400
    # 非法状态不落库
    plans = client.get("/api/wealth/action-plan", headers=auth_headers).json()["plans"]
    assert plans[0]["status"] == "todo"


def test_empty_action_rejected(client, auth_headers):
    r = client.post("/api/wealth/action-plan", headers=auth_headers, json={"action": "   "})
    assert r.status_code == 400


def test_requires_auth(client):
    assert client.get("/api/wealth/action-plan").status_code == 401
    assert client.post("/api/wealth/action-plan", json={"action": "A"}).status_code == 401
