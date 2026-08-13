"""Wealth Engine · apply_scenario 原语测试（C3）。

铁律验证：
1. apply_scenario 纯函数：不修改入参 data，返回深拷贝副本。
2. 每个场景只做「数据补丁」，不计算 Wealth Score / RFR / NWC。
3. 非法参数抛 ValueError。
"""
import copy

import pytest

from app.engine import scenario as sc


def _family():
    return {
        "persons": [{"relation": "本人", "birth_year": 1990}],
        "assets": [
            {"type": "存款", "name": "现金", "value": 1500000},
            {"type": "股票", "name": "股票", "value": 1500000},
        ],
        "liabilities": [
            {"type": "房贷", "name": "房贷", "principal": 2000000, "monthly_payment": 12000,
             "interest_rate": 0.035, "remaining_months": 240},
        ],
        "cashflows": [
            {"flow_type": "income", "amount": 50000, "period": "月"},
            {"flow_type": "expense", "amount": 20000, "period": "月"},
        ],
        "goals": [],
        "insurance": [],
        "family_profile": {"risk_profile": "balanced", "investment_horizon": 10},
    }


# ---------- 纯函数 / 不可变 ----------

def test_apply_does_not_mutate_input():
    data = _family()
    before = copy.deepcopy(data)
    modified = sc.apply_scenario(data, "invest", {"amount": 300000, "to_class": "equity"})
    assert data == before
    assert modified is not data
    assert modified["assets"] is not data["assets"]


def test_apply_returns_family_data_not_metrics():
    modified = sc.apply_scenario(_family(), "income_change", {"pct_change": 0.1})
    assert "wealth_score" not in modified
    assert "rfr" not in modified
    assert "overview" not in modified


# ---------- 四场景数据补丁 ----------

def test_apply_buy_house():
    modified = sc.apply_scenario(_family(), "buy_house",
                                 {"price": 3000000, "down_payment_ratio": 0.3,
                                  "loan_rate": 3.5, "loan_years": 30})
    deposit = next(a for a in modified["assets"] if a["type"] == "存款")
    assert deposit["value"] == pytest.approx(600000, abs=0.01)          # 150万 - 首付90万
    house = next(a for a in modified["assets"] if a["type"] == "房产")
    assert house["value"] == pytest.approx(3000000, abs=0.01)
    new_mort = next(l for l in modified["liabilities"] if l["name"] == "情景房贷")
    assert new_mort["principal"] == pytest.approx(2100000, abs=0.01)    # 300万 - 90万
    assert new_mort["remaining_months"] == 360


def test_apply_invest():
    modified = sc.apply_scenario(_family(), "invest", {"amount": 300000, "to_class": "equity"})
    deposit = next(a for a in modified["assets"] if a["type"] == "存款")
    assert deposit["value"] == pytest.approx(1200000, abs=0.01)
    invest = next(a for a in modified["assets"] if a.get("name") == "情景投资")
    assert invest["asset_class"] == "equity"
    assert invest["value"] == pytest.approx(300000, abs=0.01)


def test_apply_prepay_shorten():
    modified = sc.apply_scenario(_family(), "prepay", {"prepay_amount": 500000, "method": "shorten"})
    deposit = next(a for a in modified["assets"] if a["type"] == "存款")
    assert deposit["value"] == pytest.approx(1000000, abs=0.01)
    mort = next(l for l in modified["liabilities"] if l["type"] == "房贷")
    assert mort["principal"] == pytest.approx(1500000, abs=0.01)
    assert mort["remaining_months"] < 240


def test_apply_income_change():
    modified = sc.apply_scenario(_family(), "income_change", {"pct_change": 0.1})
    inc = next(c for c in modified["cashflows"] if c["flow_type"] == "income")
    assert inc["amount"] == pytest.approx(55000, abs=0.01)


# ---------- 非法参数 ----------

def test_apply_validation_errors():
    with pytest.raises(ValueError):
        sc.apply_scenario(_family(), "buy_house", {"price": 0})
    with pytest.raises(ValueError):
        sc.apply_scenario(_family(), "buy_house", {"price": 100000000})   # 首付 3000 万 > 现金
    with pytest.raises(ValueError):
        sc.apply_scenario(_family(), "invest", {"amount": 100000000})
    with pytest.raises(ValueError):
        sc.apply_scenario(_family(), "invest", {"amount": 1000, "to_class": "nope"})
    with pytest.raises(ValueError):
        sc.apply_scenario({**_family(), "liabilities": []}, "prepay", {"prepay_amount": 100000})
    with pytest.raises(ValueError):
        sc.apply_scenario(_family(), "nope", {})
