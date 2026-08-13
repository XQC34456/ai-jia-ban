"""Wealth Engine · Family Wealth Score 测试。"""
from app.engine import score


def _data(**overrides):
    base = {
        "assets": [{"type": "存款", "value": 300000}],
        "liabilities": [],
        "cashflows": [
            {"flow_type": "income", "amount": 50000, "period": "月"},
            {"flow_type": "expense", "amount": 20000, "period": "月"},
        ],
        "goals": [], "persons": [], "insurance": [],
    }
    base.update(overrides)
    return base


def test_wealth_score_healthy_range():
    s = score.wealth_score(_data())
    assert 0 <= s["score"] <= 100
    assert len(s["dimensions"]) == 7
    assert sum(d["weight"] for d in s["dimensions"]) == 1.0


def test_wealth_score_no_insurance_penalized():
    dims = {d["name"]: d for d in score.wealth_score(_data())["dimensions"]}
    assert dims["protection"]["score"] < 50


def test_wealth_score_insurance_improves():
    s_no = {d["name"]: d for d in score.wealth_score(_data())["dimensions"]}
    s_yes = {d["name"]: d for d in
             score.wealth_score(_data(insurance=[{"type": "重疾", "coverage": 500000,
                                                  "annual_premium": 8000}]))["dimensions"]}
    assert s_yes["protection"]["score"] > s_no["protection"]["score"]


def test_every_dimension_has_reasons():
    s = score.wealth_score(_data())
    for d in s["dimensions"]:
        assert d["reasons"], f"{d['name']} 维度缺少可解释理由"


def test_wealth_score_no_debt_full_marks():
    dims = {d["name"]: d for d in score.wealth_score(_data())["dimensions"]}
    assert dims["debt"]["score"] == 100


def test_wealth_score_heavy_debt_penalized():
    data = _data(liabilities=[{"type": "房贷", "monthly_payment": 30000}])
    dims = {d["name"]: d for d in score.wealth_score(data)["dimensions"]}
    assert dims["debt"]["score"] < 60  # DTI = 30000/50000 = 0.6 > 0.5
