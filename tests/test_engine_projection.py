"""Wealth Engine · 长期财富投影测试。"""
from app.engine import projection as pr


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


def test_project_wealth_accumulates():
    seq = pr.project_wealth(net_worth=1000000, annual_income=240000, annual_expense=180000,
                            current_age=35, assumptions={"return_rate": 0.05, "income_growth": 0.0,
                                                         "expense_growth": 0.0, "inflation": 0.0,
                                                         "retirement_age": 60, "retirement_expense_ratio": 1.0,
                                                         "pension_income": 0})
    # 第 0 年净资产=100万；第 1 年 = 100万*1.05 + (24-18)万 = 111万
    assert seq[0]["net_worth"] == 1000000
    assert abs(seq[1]["net_worth"] - 1110000) < 1e-6


def test_project_wealth_income_stops_at_retirement():
    seq = pr.project_wealth(net_worth=0, annual_income=120000, annual_expense=60000,
                            current_age=59, assumptions={"retirement_age": 60, "income_growth": 0.0,
                                                         "expense_growth": 0.0, "inflation": 0.0,
                                                         "return_rate": 0.0, "retirement_expense_ratio": 1.0,
                                                         "pension_income": 1000})
    assert seq[1]["age"] == 60
    assert seq[1]["income"] == 0          # 退休后工资收入停止
    assert seq[1]["pension"] == 12000     # 养老金 1000/月 × 12
    assert seq[1]["surplus"] == -48000    # 12000 - 60000


def test_retirement_funding_ratio_full():
    r = pr.retirement_funding_ratio(net_worth=5000000, annual_income=240000, annual_expense=120000,
                                    current_age=40, assumptions={"retirement_age": 60,
                                                                 "retirement_expense_ratio": 0.7,
                                                                 "pension_income": 0, "inflation": 0.0,
                                                                 "return_rate": 0.0, "income_growth": 0.0,
                                                                 "expense_growth": 0.0})
    # 退休净资产 = 500万 + 20×12万 = 740万；需求现值 = 30×8.4万 = 252万 → RFR≈2.9
    assert r["funding_ratio"] > 1
    assert r["score"] == 100


def test_retirement_funding_ratio_underfunded():
    r = pr.retirement_funding_ratio(net_worth=100000, annual_income=120000, annual_expense=120000,
                                    current_age=58, assumptions={"retirement_age": 60,
                                                                 "retirement_expense_ratio": 0.7,
                                                                 "pension_income": 0, "inflation": 0.0,
                                                                 "return_rate": 0.0, "income_growth": 0.0,
                                                                 "expense_growth": 0.0})
    assert r["funding_ratio"] < 0.5
    assert r["score"] < 50


def test_retirement_funding_ratio_negative_net_worth_clamped():
    # 负净资产 → 覆盖比为负，评分必须 clamp 到 0，不能出现负分
    r = pr.retirement_funding_ratio(net_worth=-2000000, annual_income=40000, annual_expense=50000,
                                    current_age=45)
    assert r["funding_ratio"] < 0
    assert r["score"] == 0
