"""Wealth Engine · 情景引擎测试。"""
from app.engine import metrics, scenario as sc


def _data():
    return {
        "assets": [{"type": "存款", "value": 1000000}],
        "liabilities": [{"type": "房贷", "principal": 2000000, "monthly_payment": 12000,
                         "interest_rate": 0.035, "remaining_months": 240}],
        "cashflows": [{"flow_type": "income", "amount": 40000, "period": "月"}],
        "goals": [], "persons": [],
    }


def _snap(data):
    return metrics.snapshot(data)


def test_simulate_invest_reduces_liquid():
    r = sc.run_scenario(_data(), _snap(_data()), "invest", {"amount": 500000, "to_class": "equity"})
    assert r["scenario"] == "invest"
    assert r["params_snapshot"]["amount"] == 500000
    assert r["params_snapshot"]["to_class"] == "equity"
    # 新增：三情景终值 + 10 项 impacts
    assert "return_rate" in r["params_snapshot"]
    keys = {i["key"] for i in r["impacts"]}
    assert {"amount", "source", "asset_class", "return_rate", "volatility", "horizon",
            "final_asset", "cashflow", "goal_completion", "liquidity"} <= keys


def test_simulate_unknown_scenario():
    r = sc.run_scenario(_data(), {}, "nope", {})
    assert r["error"].startswith("未知场景")


def test_buy_house_has_params_snapshot():
    r = sc.run_scenario(_data(), _snap(_data()), "buy_house", {"price": 3000000})
    assert "params_snapshot" in r
    assert r["params_snapshot"]["price"] == 3000000


def test_income_change_updates_surplus():
    r = sc.run_scenario(_data(), _snap(_data()), "income_change", {"pct_change": 0.1})
    # 收入 40000 → 44000，月支出 = 月供 12000，结余 28000 → 32000
    assert r["rows"][1]["b"] == 32000.0


def test_prepay_requires_mortgage():
    data = _data()
    data["liabilities"] = []
    r = sc.run_scenario(data, _snap(data), "prepay", {"prepay_amount": 100000})
    assert "error" in r


def test_invest_amount_exceeds_liquid_returns_error():
    # 现金仅 100 万，投入 200 万应报错
    r = sc.run_scenario(_data(), _snap(_data()), "invest", {"amount": 2000000, "to_class": "equity"})
    assert "error" in r


def test_buy_house_down_payment_exceeds_liquid_returns_error():
    # 房价 1000 万 → 首付 300 万 > 现金 100 万，应报错
    r = sc.run_scenario(_data(), _snap(_data()), "buy_house", {"price": 10000000})
    assert "error" in r


def test_buy_house_has_seven_impacts():
    r = sc.run_scenario(_data(), _snap(_data()), "buy_house", {"price": 3000000})
    keys = {i["key"] for i in r["impacts"]}
    assert {"net_worth", "financial_assets", "liquidity", "monthly_cashflow",
            "debt_ratio", "real_estate_pct", "goal_funding"} <= keys
    net = next(i for i in r["impacts"] if i["key"] == "net_worth")
    assert "delta" in net and "money" in net


def test_invest_three_scenarios_monotonic():
    # 中性应介于悲观与乐观之间
    r = sc.run_scenario(_data(), _snap(_data()), "invest",
                        {"amount": 300000, "to_class": "equity", "return_rate": 0.08,
                         "volatility": 0.2, "horizon_years": 10})
    fa = next(i for i in r["impacts"] if i["key"] == "final_asset")
    assert fa["pessimistic"] < fa["neutral"] < fa["optimistic"]
