"""Wealth Service · compare_scenarios 编排测试（C3）。

验证：baseline 不变、每个 option 独立 apply、与单独执行逐项一致、
comparison 为纯展示差值、新旧接口在相同指标上一致。
"""
import pytest

from app.engine import metrics, scenario as sc
from app.services.overview import build_overview
from app.services.scenario import compare_scenarios


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
        "goals": [], "insurance": [],
        "family_profile": {"risk_profile": "balanced", "investment_horizon": 10},
    }


def test_baseline_equals_build_overview():
    data = _family()
    c = compare_scenarios(data, "invest", [{"id": "A", "params": {"amount": 300000, "to_class": "equity"}}])
    assert c["baseline"] == build_overview(data)


def test_options_independent_not_chained():
    data = _family()
    base = build_overview(data)
    c = compare_scenarios(data, "invest", [
        {"id": "A", "params": {"amount": 300000, "to_class": "equity"}},
        {"id": "B", "params": {"amount": 100000, "to_class": "equity"}},
    ])
    # B 只反映「投资 10 万」，不是「先投 30 万再投 10 万」
    assert c["options"][0]["overview"]["liquid_assets"] == pytest.approx(base["liquid_assets"] - 300000)
    assert c["options"][1]["overview"]["liquid_assets"] == pytest.approx(base["liquid_assets"] - 100000)


def test_option_matches_standalone():
    data = _family()
    solo = compare_scenarios(data, "invest", [{"id": "A", "params": {"amount": 300000, "to_class": "equity"}}])
    multi = compare_scenarios(data, "invest", [
        {"id": "A", "params": {"amount": 300000, "to_class": "equity"}},
        {"id": "B", "params": {"amount": 100000, "to_class": "equity"}},
    ])
    assert multi["options"][0]["overview"] == solo["options"][0]["overview"]


def test_comparison_has_nine_metrics():
    c = compare_scenarios(_family(), "invest", [{"id": "A", "params": {"amount": 300000, "to_class": "equity"}}])
    keys = [r["key"] for r in c["comparison"]["A"]]
    assert keys == ["net_worth", "wealth_score", "rfr", "nwc", "cashflow",
                    "liquidity", "dti", "real_estate_pct", "goal_completion"]


def test_comparison_delta_is_display_subtraction():
    data = _family()
    base = build_overview(data)
    c = compare_scenarios(data, "income_change", [{"id": "A", "params": {"pct_change": 0.1}}])
    row = next(r for r in c["comparison"]["A"] if r["key"] == "cashflow")
    ov = c["options"][0]["overview"]
    assert row["baseline"] == base["cashflow"]["surplus"]
    assert row["option"] == ov["cashflow"]["surplus"]
    assert row["delta"] == pytest.approx(ov["cashflow"]["surplus"] - base["cashflow"]["surplus"])
    assert row["delta"] == pytest.approx(5000)   # 收入 +10% → 结余 +5000


def test_buy_house_dti_consistent_with_legacy():
    """新旧接口在相同指标（DTI / 房产占比）上必须一致，杜绝「沙盘一个数、AI 另一个数」。"""
    data = _family()
    params = {"price": 3000000, "down_payment_ratio": 0.3, "loan_rate": 3.5, "loan_years": 30}
    legacy = sc.run_scenario(data, metrics.snapshot(data), "buy_house", params)
    leg_dti = next(i for i in legacy["impacts"] if i["key"] == "debt_ratio")["after"]
    leg_re = next(i for i in legacy["impacts"] if i["key"] == "real_estate_pct")["after"]

    c = compare_scenarios(data, "buy_house", [{"id": "A", "params": params}])
    ov = c["options"][0]["overview"]
    assert ov["debt"]["dti"] == pytest.approx(leg_dti, abs=1e-4)
    assert ov["asset_allocation"]["classes"]["real_estate"]["pct"] == pytest.approx(leg_re, abs=1e-4)
