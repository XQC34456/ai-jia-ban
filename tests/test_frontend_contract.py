"""前端契约测试（API v1 Contract Freeze 守门）。

模拟前端：只消费 API 响应 JSON，用 Schema 校验，绝不 import app/engine，
绝不自行计算任何财富逻辑。若 API 返回结构改变导致前端契约断裂，本文件首先报警。

约束：本文件只 import app.schemas（契约层），不 import app.engine / app.decision / app.services。
"""
from app.schemas import Overview
from app.schemas.scenario import SCENARIO_NAMES


def test_error_contract_unauthorized(client):
    """错误契约：未登录返回 401 + {"detail": "..."}，前端直接消费。"""
    r = client.get("/api/wealth/overview", headers={"Authorization": "Bearer invalid"})
    assert r.status_code == 401
    assert "detail" in r.json()


def test_overview_contract_complete_for_dashboard(client, auth_headers):
    """无数据家庭也能拿到完整、可直接渲染的驾驶舱对象（前端无需二次计算）。"""
    r = client.get("/api/wealth/overview", headers=auth_headers)
    assert r.status_code == 200
    o = Overview.model_validate(r.json())  # 契约校验：前端只依赖这个模型

    assert o.currency == "CNY"                 # 货币单位显式声明
    assert 0 <= o.wealth_score <= 100
    assert isinstance(o.net_worth, (int, float))
    # 各区块直接可渲染，无需前端聚合
    assert o.cashflow is not None
    assert o.liquidity is not None
    assert o.debt is not None
    assert o.protection is not None
    assert isinstance(o.issues, list)
    # 配置目标（Σ=100% 点目标）与六大类占比已由后端给出
    assert "classes" in o.asset_allocation
    assert isinstance(o.allocation_target, dict)


def test_decision_recommendation_scenario_chain(client, auth_headers):
    """Decision → Recommendation → Scenario 链：有场景的建议必须引用已实现情景名。"""
    client.post("/api/family/entity/cashflow", headers=auth_headers,
                json={"flow_type": "income", "amount": 10000, "period": "月"})
    client.post("/api/family/entity/cashflow", headers=auth_headers,
                json={"flow_type": "expense", "amount": 20000, "period": "月"})

    o = client.get("/api/wealth/overview", headers=auth_headers).json()
    assert o["issues"], "负现金流家庭应触发 issue"

    for issue in o["issues"]:
        for rec in issue["recommendations"]:
            # recommendation_id 继承 issue，priority 继承 issue
            assert rec["recommendation_id"].startswith(issue["issue_id"])
            assert rec["priority"] == issue["severity"]
            # 有场景 → 一定可触发，且场景名已实现
            if rec["scenario"] is not None:
                assert rec["scenario"] in SCENARIO_NAMES
                assert rec["actionable"] is True
            # 目标为数值 dict（供场景参数化）
            assert isinstance(rec["target"], dict)
