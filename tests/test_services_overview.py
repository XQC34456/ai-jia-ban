"""编排层测试：build_overview 聚合 + Goal Engine 统一。"""
from app.services import build_goals, build_overview


def _fd(**overrides):
    base = {
        "family": {"id": 1, "name": "测试家庭"},
        "persons": [{"name": "本人", "relation": "本人", "birth_year": 1976}],
        "assets": [{"type": "存款", "value": 100000}],
        "liabilities": [],
        "cashflows": [
            {"flow_type": "income", "amount": 30000, "period": "月"},
            {"flow_type": "expense", "amount": 20000, "period": "月"},
        ],
        "goals": [], "insurance": [], "reminders": [],
        "family_profile": {"risk_profile": "balanced", "investment_horizon": 10},
    }
    base.update(overrides)
    return base


def test_overview_has_core_keys():
    o = build_overview(_fd())
    for k in ("wealth_score", "wealth_level", "net_worth", "total_assets", "total_liabilities",
              "liquid_assets", "asset_allocation", "allocation_fitness", "allocation_target",
              "cashflow", "liquidity", "debt", "protection", "goals", "retirement",
              "issues", "alerts", "priorities", "recommendations"):
        assert k in o, f"缺少键 {k}"
    assert 0 <= o["wealth_score"] <= 100


def test_overview_exposes_health_dimensions():
    """overview 暴露 Engine 已算好的 7 维健康评分（含保障 protection），供前端雷达图。"""
    o = build_overview(_fd())
    dims = o["dimensions"]
    names = [d["name"] for d in dims]
    assert set(names) == {"cashflow", "liquidity", "debt", "protection",
                          "allocation", "goals", "retirement"}
    for d in dims:
        assert 0 <= d["score"] <= 100
        assert isinstance(d["reasons"], list)
        assert isinstance(d["weight"], (int, float))


def test_overview_net_worth_consistency():
    o = build_overview(_fd(assets=[{"type": "房产", "value": 3000000}, {"type": "存款", "value": 500000}],
                           liabilities=[{"type": "房贷", "principal": 800000, "monthly_payment": 5000,
                                         "interest_rate": 0.035, "remaining_months": 240}]))
    assert o["total_assets"] == 3500000
    assert o["total_liabilities"] == 800000
    assert o["net_worth"] == 2700000


def test_overview_house_rich_cash_poor_quadrant():
    o = build_overview(_fd(assets=[{"type": "房产", "value": 8000000}, {"type": "存款", "value": 100000}],
                           cashflows=[
                               {"flow_type": "income", "amount": 30000, "period": "月"},
                               {"flow_type": "expense", "amount": 28000, "period": "月"},
                           ]))
    r = o["retirement"]
    assert r is not None
    assert r["quadrant"] == "资产充足但流动性不足"
    assert r["rfr"] < 1 and r["nwc"] >= 1
    assert "retirement_debt_service_not_included" in r["known_limitations"]
    # issue 也被正确识别
    assert any(i["type"] == "retirement" and i["severity"] == "P0" for i in o["issues"])


def test_overview_no_age_retirement_none():
    o = build_overview(_fd(persons=[]))
    assert o["retirement"] is None


def test_build_goals_unifies_kinds():
    fd = _fd(goals=[
        {"id": 1, "type": "教育", "name": "孩子大学", "target_amount": 500000,
         "target_date": "2030-08-01", "current_saved": 100000},
        {"id": 2, "type": "养老", "name": "养老补充", "goal_kind": "cashflow",
         "annual_amount": 100000, "duration_years": 20, "start_year": 5, "current_saved": 200000},
    ])
    goals = build_goals(fd)
    assert len(goals) == 2
    by_id = {g["goal_id"]: g for g in goals}
    assert by_id[1]["goal_kind"] == "lump_sum"
    assert by_id[1]["coverage"] == 0.2
    assert by_id[2]["goal_kind"] == "cashflow"
    assert by_id[2]["target_amount"] > 0
    assert by_id[2]["gap"] > 0


def test_build_goals_empty():
    assert build_goals(_fd()) == []
