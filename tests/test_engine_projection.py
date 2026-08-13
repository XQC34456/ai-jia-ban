"""Wealth Engine · 长期财富投影测试（资产层确定性模型）。"""
from app.engine import projection as pr


def _no_inflation():
    return {"inflation": 0.0, "income_growth": 0.0, "expense_growth": 0.0,
            "retirement_expense_ratio": 1.0, "discount_rate": 0.0}


def test_future_value():
    assert abs(pr.future_value(100000, 0.03, 1) - 103000) < 1e-6
    assert abs(pr.future_value(100000, 0.05, 2) - 110250) < 1e-6


def test_project_net_worth_zero_surplus():
    seq = pr.project_net_worth(500000, 0, 0.0, 3)
    assert seq == [500000, 500000, 500000, 500000]


def test_project_net_worth_grows():
    seq = pr.project_net_worth(0, 12000, 0.0, 2)
    assert seq[1] == 144000
    assert seq[2] == 288000


def test_project_net_worth_with_return():
    # 100万，月结余 1万，年化 6%，1 年后 = 100万*1.06 + 12万 = 118万
    seq = pr.project_net_worth(1000000, 10000, 0.06, 1)
    assert seq[1] == 1180000.0


def test_project_family_applies_class_returns():
    # 各资产大类按各自收益率复利（cash 1.5% / equity 8%），房产另算
    assets = {"cash": 100000, "fixed_income": 0, "equity": 100000,
              "real_estate": 0, "alternative": 0, "other": 0}
    seq = pr.project_family(assets, [], 0, 0, 40, assumptions={"life_expectancy": 41})
    assert seq[0]["net_worth"] == 200000
    assert abs(seq[1]["assets"]["cash"] - 101500.0) < 0.01   # 100000 × 1.015
    assert abs(seq[1]["assets"]["equity"] - 108000.0) < 0.01  # 100000 × 1.08
    assert abs(seq[1]["net_worth"] - 209500.0) < 0.01


def test_project_family_debt_amortizes():
    # 12 个月零息负债在 1 年内还清，本金从现金扣减
    assets = {"cash": 200000, "fixed_income": 0, "equity": 0,
              "real_estate": 0, "alternative": 0, "other": 0}
    debts = [{"principal": 120000, "annual_rate": 0.0, "remaining_months": 12}]
    seq = pr.project_family(assets, debts, 0, 0, 40,
                            assumptions={"life_expectancy": 41, "cash_return": 0.0})
    assert seq[1]["total_debt"] == 0.0
    assert abs(seq[1]["assets"]["cash"] - 80000.0) < 0.01
    assert abs(seq[1]["net_worth"] - 80000.0) < 0.01


def test_project_family_snapshot_net_worth_and_investable():
    # t=0 现状快照：净资产 = 总资产 - 总负债；可投资资产默认不含房产
    assets = {"cash": 300000, "real_estate": 700000,
              "fixed_income": 0, "equity": 0, "alternative": 0, "other": 0}
    debts = [{"principal": 400000, "annual_rate": 0.03, "remaining_months": 300}]
    seq = pr.project_family(assets, debts, 100000, 60000, 40,
                            assumptions={"life_expectancy": 42})
    assert seq[0]["total_assets"] == 1000000.0
    assert seq[0]["total_debt"] == 400000.0
    assert seq[0]["net_worth"] == 600000.0
    assert seq[0]["investable"] == 300000.0  # 仅现金，房产默认不计入


def test_retirement_funding_ratio_full():
    a = {"cash": 5000000, "fixed_income": 0, "equity": 0,
         "real_estate": 0, "alternative": 0, "other": 0}
    r = pr.retirement_funding_ratio(a, [], 120000, 120000, 40,
                                    assumptions={**_no_inflation(), "cash_return": 0.0})
    assert r["funding_ratio"] >= 1.0
    assert r["score"] == 100


def test_retirement_funding_ratio_underfunded():
    a = {"cash": 100000, "fixed_income": 0, "equity": 0,
         "real_estate": 0, "alternative": 0, "other": 0}
    r = pr.retirement_funding_ratio(a, [], 120000, 120000, 58,
                                    assumptions={**_no_inflation(), "cash_return": 0.0})
    assert r["funding_ratio"] < 0.5
    assert r["score"] < 50


def test_retirement_house_rich_cash_poor():
    # 净资产充足（NWC≥1）但可投资资产不足（RFR<1）：房产重、流动资金少的家庭
    a = {"cash": 200000, "real_estate": 5000000,
         "fixed_income": 0, "equity": 0, "alternative": 0, "other": 0}
    r = pr.retirement_funding_ratio(a, [], 100000, 100000, 55,
                                    assumptions={**_no_inflation(), "cash_return": 0.0,
                                                 "real_estate_return": 0.0,
                                                 "retirement_expense_ratio": 0.7})
    assert r["net_worth_coverage"] >= 1.0
    assert r["funding_ratio"] < 0.2
    assert r["net_worth_coverage"] > r["funding_ratio"]


def test_retirement_funding_ratio_negative_clamped():
    # 无资产、高负债 → 覆盖比为负，评分必须 clamp 到 0，不能出现负分
    a = {"cash": 0, "fixed_income": 0, "equity": 0,
         "real_estate": 0, "alternative": 0, "other": 0}
    debts = [{"principal": 2000000, "annual_rate": 0.03, "remaining_months": 300}]
    r = pr.retirement_funding_ratio(a, debts, 40000, 50000, 45)
    assert r["funding_ratio"] < 0
    assert r["score"] == 0
