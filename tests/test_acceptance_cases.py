"""Plan B 验收：8 组家庭案例跑通 build_overview，验证关键信号被正确识别。

重点验收「高净资产但低退休流动资金」能被 Decision Layer 识别，
以及房产(明确资产) vs 其他(不透明资产) 的配置差异。
"""
from app.services import build_overview


def _fd(**overrides):
    base = {
        "family": {"id": 1, "name": "验收家庭"},
        "persons": [{"name": "本人", "relation": "本人", "birth_year": 1976}],
        "assets": [],
        "liabilities": [],
        "cashflows": [
            {"flow_type": "income", "amount": 30000, "period": "月"},
            {"flow_type": "expense", "amount": 15000, "period": "月"},
        ],
        "goals": [], "insurance": [], "reminders": [],
        "family_profile": {"risk_profile": "balanced", "investment_horizon": 10},
    }
    base.update(overrides)
    return base


def _overview(fd):
    return build_overview(fd)


def test_c1_house_rich_cash_poor():
    o = _overview(_fd(assets=[{"type": "房产", "value": 8000000}, {"type": "存款", "value": 100000}],
                      cashflows=[{"flow_type": "income", "amount": 30000, "period": "月"},
                                 {"flow_type": "expense", "amount": 28000, "period": "月"}]))
    assert o["retirement"]["quadrant"] == "资产充足但流动性不足"
    assert o["retirement"]["rfr"] < 1 and o["retirement"]["nwc"] >= 1
    ret_issues = [i for i in o["issues"] if i["type"] == "retirement"]
    assert ret_issues and ret_issues[0]["severity"] == "P0"
    assert ret_issues[0]["title"] == "退休流动资金不足"


def test_c2_negative_net_worth():
    o = _overview(_fd(assets=[{"type": "存款", "value": 50000}],
                      liabilities=[{"type": "房贷", "principal": 2000000, "monthly_payment": 15000,
                                    "interest_rate": 0.045, "remaining_months": 300}],
                      cashflows=[{"flow_type": "income", "amount": 20000, "period": "月"},
                                 {"flow_type": "expense", "amount": 18000, "period": "月"}]))
    assert o["net_worth"] < 0
    assert any(i["type"] == "debt" and i["severity"] == "P0" for i in o["issues"])


def test_c3_high_cash_healthy():
    o = _overview(_fd(assets=[{"type": "存款", "value": 3000000}, {"type": "基金", "value": 2000000},
                              {"type": "股票", "value": 1000000}],
                      cashflows=[{"flow_type": "income", "amount": 50000, "period": "月"},
                                 {"flow_type": "expense", "amount": 15000, "period": "月"}]))
    assert o["retirement"]["quadrant"] == "养老健康"
    assert o["retirement"]["rfr"] >= 1


def test_c4_high_debt():
    o = _overview(_fd(assets=[{"type": "房产", "value": 3000000}, {"type": "存款", "value": 100000}],
                      liabilities=[{"type": "房贷", "principal": 2500000, "monthly_payment": 20000,
                                    "interest_rate": 0.045, "remaining_months": 300}],
                      cashflows=[{"flow_type": "income", "amount": 30000, "period": "月"},
                                 {"flow_type": "expense", "amount": 8000, "period": "月"}]))
    debt = next(i for i in o["issues"] if i["type"] == "debt")
    assert debt["severity"] == "P0"
    assert debt["metric"]["dti"] > 0.5


def test_c5_near_retirement_underfunded():
    o = _overview(_fd(persons=[{"name": "本人", "relation": "本人", "birth_year": 1968}],
                      assets=[{"type": "存款", "value": 300000}],
                      cashflows=[{"flow_type": "income", "amount": 30000, "period": "月"},
                                 {"flow_type": "expense", "amount": 25000, "period": "月"}]))
    assert o["retirement"]["rfr"] < 1


def test_c6_cashflow_retirement_goal():
    o = _overview(_fd(assets=[{"type": "存款", "value": 500000}],
                      cashflows=[{"flow_type": "income", "amount": 40000, "period": "月"},
                                 {"flow_type": "expense", "amount": 15000, "period": "月"}],
                      goals=[{"id": 1, "type": "养老", "name": "养老现金流", "goal_kind": "cashflow",
                              "annual_amount": 200000, "duration_years": 20, "start_year": 10,
                              "current_saved": 100000}]))
    assert any(g["goal_kind"] == "cashflow" for g in o["goals"])


def test_c7_real_estate_vs_other():
    a = _fd(assets=[{"type": "存款", "value": 200000}, {"type": "基金", "value": 300000},
                    {"type": "股票", "value": 200000}, {"type": "房产", "value": 300000}])
    b = _fd(assets=[{"type": "存款", "value": 200000}, {"type": "基金", "value": 300000},
                    {"type": "股票", "value": 200000}, {"type": "其他", "value": 300000}])
    fa = _overview(a)["allocation_fitness"]
    fb = _overview(b)["allocation_fitness"]
    assert fa > fb  # 房产(明确资产) 优于 其他(不透明资产)


def test_c8_uhnw_diversified():
    o = _overview(_fd(persons=[{"name": "本人", "relation": "本人", "birth_year": 1971}],
                      assets=[{"type": "存款", "value": 3000000}, {"type": "基金", "value": 5000000},
                              {"type": "股票", "value": 4000000}, {"type": "房产", "value": 8000000}],
                      liabilities=[{"type": "房贷", "principal": 1000000, "monthly_payment": 8000,
                                    "interest_rate": 0.035, "remaining_months": 240}],
                      insurance=[{"type": "终身寿险", "coverage": 10000000, "annual_premium": 100000}],
                      cashflows=[{"flow_type": "income", "amount": 200000, "period": "月"},
                                 {"flow_type": "expense", "amount": 50000, "period": "月"}]))
    assert o["wealth_score"] >= 80
    assert o["retirement"]["quadrant"] == "养老健康"
