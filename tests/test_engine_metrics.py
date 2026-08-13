"""Wealth Engine · 基础指标模块单元测试（与旧 calc_engine 行为一致）。"""
import pytest

from app.engine import metrics as ce


def _family(assets=None, liabilities=None, cashflows=None, goals=None):
    return {
        "assets": assets or [],
        "liabilities": liabilities or [],
        "cashflows": cashflows or [],
        "goals": goals or [],
        "persons": [],
    }


def test_net_worth():
    data = _family(
        assets=[{"type": "存款", "value": 500000}, {"type": "房产", "value": 3000000}],
        liabilities=[{"type": "房贷", "principal": 1000000}],
    )
    assert ce.total_assets(data["assets"]) == 3500000
    assert ce.total_liabilities(data["liabilities"]) == 1000000
    assert ce.net_worth(data["assets"], data["liabilities"]) == 2500000


def test_monthly_cashflow_and_savings_rate():
    cashflows = [
        {"flow_type": "income", "amount": 20000, "period": "月"},
        {"flow_type": "income", "amount": 15000, "period": "月"},
        {"flow_type": "expense", "amount": 12000, "period": "月"},
    ]
    assert ce.monthly_income(cashflows) == 35000
    assert ce.monthly_expense(cashflows) == 12000
    assert ce.monthly_surplus(cashflows) == 23000
    assert abs(ce.savings_rate(cashflows) - 23000 / 35000) < 1e-9


def test_annual_income_normalized():
    cashflows = [{"flow_type": "income", "amount": 120000, "period": "年"}]
    assert ce.monthly_income(cashflows) == 10000


def test_emergency_months():
    data = _family(
        assets=[{"type": "存款", "value": 120000}],
        cashflows=[{"flow_type": "expense", "amount": 20000, "period": "月"}],
    )
    assert ce.emergency_months(data["assets"], data["cashflows"]) == 6


def test_debt_payment_counts_as_expense():
    cashflows = [{"flow_type": "income", "amount": 35000, "period": "月"}]
    liabilities = [{"type": "房贷", "monthly_payment": 8000}]
    assert ce.monthly_expense(cashflows, liabilities) == 8000
    assert ce.monthly_surplus(cashflows, liabilities) == 27000
    assert abs(ce.savings_rate(cashflows, liabilities) - 27000 / 35000) < 1e-9


def test_debt_to_income():
    data = _family(
        liabilities=[{"type": "房贷", "monthly_payment": 8000}],
        cashflows=[{"flow_type": "income", "amount": 20000, "period": "月"}],
    )
    assert abs(ce.debt_to_income(data["liabilities"], data["cashflows"]) - 0.4) < 1e-9


def test_goal_gap():
    gap = ce.goal_gap({"name": "教育", "target_amount": 1000000, "current_saved": 300000})
    assert gap["gap"] == 700000
    assert abs(gap["progress"] - 0.3) < 1e-9
    assert gap["monthly_needed"] is None


def test_goal_monthly_needed_with_date():
    from datetime import date
    today = date(2026, 8, 13)
    goal = {"name": "教育", "target_amount": 1000000, "current_saved": 0,
            "target_date": "2035-01-01"}
    gap = ce.goal_gap(goal, today=today)
    assert gap["months_remaining"] == 101
    assert gap["monthly_needed"] == 9900.99


def test_goals_funding_feasible():
    from datetime import date
    today = date(2026, 8, 13)
    goals = [{"name": "教育", "target_amount": 1000000, "current_saved": 0,
              "target_date": "2035-01-01"}]
    funding = ce.goals_funding(goals, monthly_surplus_value=20000, today=today)
    assert funding["feasible"] is True
    assert funding["total_monthly_needed"] > 0
    assert funding["shortfall"] == 0


def test_goals_funding_shortfall():
    from datetime import date
    today = date(2026, 8, 13)
    goals = [
        {"name": "教育", "target_amount": 1000000, "current_saved": 0, "target_date": "2030-01-01"},
        {"name": "买房", "target_amount": 3000000, "current_saved": 0, "target_date": "2030-01-01"},
    ]
    funding = ce.goals_funding(goals, monthly_surplus_value=5000, today=today)
    assert funding["feasible"] is False
    assert funding["shortfall"] > 0


def test_safety_margin_healthy():
    data = _family(
        assets=[{"type": "存款", "value": 300000}],
        cashflows=[
            {"flow_type": "income", "amount": 50000, "period": "月"},
            {"flow_type": "expense", "amount": 20000, "period": "月"},
        ],
    )
    sm = ce.safety_margin(data["assets"], data["liabilities"], data["cashflows"])
    assert sm["level"] == "稳健"
    assert sm["score"] >= 75


def test_safety_margin_fragile():
    data = _family(
        assets=[{"type": "存款", "value": 10000}],
        liabilities=[{"type": "房贷", "monthly_payment": 15000}],
        cashflows=[
            {"flow_type": "income", "amount": 20000, "period": "月"},
            {"flow_type": "expense", "amount": 25000, "period": "月"},
        ],
    )
    sm = ce.safety_margin(data["assets"], data["liabilities"], data["cashflows"])
    assert sm["score"] < 50
    assert sm["level"] == "脆弱"


def test_calc_engine_is_compat_shim():
    """旧 import 路径（app.calc_engine）与新引擎输出一致。"""
    from app import calc_engine as legacy
    data = _family(assets=[{"type": "存款", "value": 500000}])
    assert legacy.snapshot(data) == ce.snapshot(data)
    assert legacy.total_assets(data["assets"]) == ce.total_assets(data["assets"])
