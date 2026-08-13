"""统一 Scenario API 集成测试（VIP）。"""


def _add(client, h, table, payload):
    r = client.post(f"/api/family/entity/{table}", headers=h, json=payload)
    assert r.status_code == 200, r.text


def test_scenario_requires_auth(client):
    assert client.post("/api/wealth/scenario/invest", json={"params": {}}).status_code == 401


def test_scenario_requires_vip(client, auth_headers):
    r = client.post("/api/wealth/scenario/invest", headers=auth_headers, json={"params": {}})
    assert r.status_code == 403


def test_scenario_vip_invest(client, auth_headers):
    _add(client, auth_headers, "asset", {"type": "存款", "value": 1000000})
    client.post("/api/upgrade", headers=auth_headers)
    r = client.post("/api/wealth/scenario/invest", headers=auth_headers,
                    json={"params": {"amount": 300000, "to_class": "equity"}})
    assert r.status_code == 200
    body = r.json()
    assert body["scenario"] == "invest"
    assert "impacts" in body


def test_scenario_unknown(client, auth_headers):
    client.post("/api/upgrade", headers=auth_headers)
    r = client.post("/api/wealth/scenario/nope", headers=auth_headers, json={"params": {}})
    assert r.status_code == 400
