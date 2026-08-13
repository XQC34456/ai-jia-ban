"""决策模拟入口回归测试。

背景：app/decision.py（含 simulate 的兼容模块）曾与 app/decision/（判断层包）同名，
Python 解析时包遮蔽模块，导致 decision.simulate 丢失 → /api/decision 抛 500。
本文件守两条：① simulate 在包上；② /api/decision 端点端到端可通。
"""
import app.decision as decision


def test_decision_simulate_is_on_package():
    # 回归：simulate 必须挂在 app.decision 包上（而非被遮蔽的 .py 模块）。
    assert hasattr(decision, "simulate")


def test_decision_requires_auth(client):
    r = client.post("/api/decision", json={"scenario": "buy_house", "params": {}})
    assert r.status_code == 401


def test_decision_requires_vip(client, auth_headers):
    r = client.post("/api/decision", headers=auth_headers,
                    json={"scenario": "buy_house", "params": {}})
    assert r.status_code == 403


def test_decision_endpoint_buy_house(client, auth_headers):
    # 回归：/api/decision 曾因 decision.simulate 被遮蔽 → 500「Internal Server Error」。
    client.post("/api/family/entity/asset", headers=auth_headers,
                json={"type": "存款", "value": 1000000})
    client.post("/api/upgrade", headers=auth_headers)
    r = client.post("/api/decision", headers=auth_headers,
                    json={"scenario": "buy_house", "params": {"price": 2000000}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scenario"] == "buy_house"
    assert "impacts" in body and "conclusion" in body
