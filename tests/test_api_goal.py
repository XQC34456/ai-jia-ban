"""Goal Engine API 集成测试。"""


def test_goals_requires_auth(client):
    assert client.get("/api/wealth/goals").status_code == 401


def test_goals_unified(client, auth_headers):
    r = client.post("/api/family/entity/goal", headers=auth_headers, json={
        "type": "教育", "name": "孩子大学", "target_amount": 500000,
        "target_date": "2030-08-01", "current_saved": 100000,
    })
    assert r.status_code == 200

    body = client.get("/api/wealth/goals", headers=auth_headers).json()
    assert len(body["goals"]) == 1
    g = body["goals"][0]
    assert g["goal_kind"] == "lump_sum"
    assert g["target_amount"] == 500000
    assert g["gap"] == 400000
    assert g["coverage"] == 0.2


def test_goals_empty(client, auth_headers):
    body = client.get("/api/wealth/goals", headers=auth_headers).json()
    assert body["goals"] == []
