"""Wealth Engine · 资产配置分析测试。"""
from app.engine import allocation as al


def test_classify_asset():
    assert al.classify_asset("房产") == "real_estate"
    assert al.classify_asset("股票") == "equity"
    assert al.classify_asset("存款") == "cash"
    assert al.classify_asset("黄金") == "other"


def test_breakdown_pct():
    assets = [{"type": "存款", "value": 500000}, {"type": "房产", "value": 4500000}]
    b = al.asset_class_breakdown(assets)
    assert b["cash"]["pct"] == 0.1
    assert b["real_estate"]["pct"] == 0.9


def test_breakdown_uses_asset_class_field():
    # 记录上显式 asset_class 优先于 type 映射
    assets = [{"type": "存款", "asset_class": "equity", "value": 1000000}]
    b = al.asset_class_breakdown(assets)
    assert b["equity"]["pct"] == 1.0
    assert b["cash"]["pct"] == 0.0


def test_concentration_high_property():
    assets = [{"type": "房产", "value": 9000000}, {"type": "存款", "value": 100000}]
    c = al.concentration(assets)
    assert c["real_estate_pct"] > 0.9


def test_policy_conservative_lower_equity():
    cons = al.allocation_policy("conservative", 10)
    aggr = al.allocation_policy("aggressive", 10)
    assert cons["equity"][1] < aggr["equity"][1]


def test_policy_time_horizon_adjusts():
    near = al.allocation_policy("balanced", 3)
    far = al.allocation_policy("balanced", 10)
    assert near["equity"][1] < far["equity"][1]


def test_policy_custom_injectable():
    # B 端可注入自定义 Policy，期限 5 年（不触发期限修正）
    custom = {"balanced": {"cash": [0.3, 0.4], "equity": [0.1, 0.2]}}
    r = al.allocation_policy("balanced", 5, policy=custom)
    assert r["cash"] == [0.3, 0.4]
    assert r["equity"] == [0.1, 0.2]


def test_analyze_deviation_and_concentration():
    assets = [{"type": "房产", "value": 9000000}, {"type": "存款", "value": 1000000}]
    r = al.analyze(assets, profile={"risk_profile": "balanced", "investment_horizon": 10})
    assert r["deviation"]["cash"] == "below"
    assert r["concentration"]["real_estate_pct"] > 0.7
    assert any(a["action"] == "增配" for a in r["adjustments"])


def test_allocation_fitness_rewards_diversified():
    # 现金10/固收30/股票30/房产30 → 金融资产在 balanced 区间内，房产不超 50%
    assets = [{"type": "存款", "value": 100000}, {"type": "基金", "value": 300000},
              {"type": "股票", "value": 300000}, {"type": "房产", "value": 300000}]
    fit = al.allocation_fitness(assets)
    assert fit["score"] > 80  # 唯一扣分来自单股 30% 的轻微集中度惩罚(5分)


def test_allocation_fitness_penalizes_concentration():
    assets = [{"type": "房产", "value": 8000000}, {"type": "存款", "value": 2000000}]
    fit = al.allocation_fitness(assets)
    assert fit["score"] < 60
    assert fit["penalties"]["concentration"] > 0


def test_allocation_fitness_penalizes_other():
    # 同样 30% 占比：房产（明确资产）不扣，其他（配置不透明）应被扣分
    a = [{"type": "存款", "value": 100000}, {"type": "基金", "value": 300000},
         {"type": "股票", "value": 300000}, {"type": "房产", "value": 300000}]
    b = [{"type": "存款", "value": 100000}, {"type": "基金", "value": 300000},
         {"type": "股票", "value": 300000}, {"type": "其他", "value": 300000}]
    fa = al.allocation_fitness(a)
    fb = al.allocation_fitness(b)
    assert fa["score"] > fb["score"]
    assert fb["penalties"]["concentration"] > 0


def test_personalized_policy_short_term_goal():
    # 3 年内用款目标 → 提高现金下限、压降权益上限
    goals = [{"goal_kind": "cashflow", "annual_amount": 500000, "duration_years": 2, "start_year": 2}]
    pol = al.personalized_policy(None, goals)["target"]
    base = al.allocation_policy("balanced", 10)
    assert pol["cash"][0] > base["cash"][0]
    assert pol["equity"][1] < base["equity"][1]


def test_personalized_policy_high_debt():
    liab = [{"type": "房贷", "monthly_payment": 30000}]
    cf = [{"flow_type": "income", "amount": 50000, "period": "月"}]
    pol = al.personalized_policy(None, None, liab, cf)["target"]
    base = al.allocation_policy("balanced", 10)
    assert pol["equity"][1] < base["equity"][1]  # DTI=0.6 > 0.5 压降权益上限
