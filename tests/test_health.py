"""体检规则引擎测试。"""
from app.health import health_check


def test_empty_family_no_problems():
    assert health_check({"assets": [], "liabilities": [], "cashflows": [], "goals": []}) == []


def test_fragile_family_has_problems():
    data = {
        "assets": [{"type": "存款", "value": 10000}],
        "liabilities": [{"type": "房贷", "monthly_payment": 15000}],
        "cashflows": [
            {"flow_type": "income", "amount": 20000, "period": "月"},
            {"flow_type": "expense", "amount": 25000, "period": "月"},
        ],
        "goals": [],
    }
    problems = health_check(data)
    assert len(problems) >= 1 and len(problems) <= 3
    titles = [p["title"] for p in problems]
    assert any("现金流" in t or "应急" in t or "负债" in t for t in titles)


def test_house_concentration_problem():
    data = {
        "assets": [
            {"type": "房产", "value": 9000000},
            {"type": "存款", "value": 100000},
        ],
        "liabilities": [],
        "cashflows": [{"flow_type": "income", "amount": 30000, "period": "月"}],
        "goals": [],
    }
    problems = health_check(data)
    assert any("房产" in p["title"] for p in problems)
