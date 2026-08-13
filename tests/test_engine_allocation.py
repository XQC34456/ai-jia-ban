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
    # 金融资产口径：现金占金融资产 100%（房产不计入金融分母）→ 超配
    assets = [{"type": "房产", "value": 9000000}, {"type": "存款", "value": 1000000}]
    r = al.analyze(assets, profile={"risk_profile": "balanced", "investment_horizon": 10})
    assert r["deviation"]["cash"] == "above"
    assert r["concentration"]["real_estate_pct"] > 0.7
    assert any(a["action"] == "减配" for a in r["adjustments"])
    assert abs(sum(r["target"].values()) - 1.0) < 0.001  # 点目标 Σ=100%


def test_policy_target_sums_to_one():
    # 三个风险画像 + 期限修正后，点目标必须 Σ=100% 且落在区间内
    for risk in ("conservative", "balanced", "aggressive"):
        for horizon in (2, 5, 10, 20):
            rng = al.allocation_policy(risk, horizon)
            target = al._normalize_target(rng)
            assert abs(sum(target.values()) - 1.0) < 0.001, f"{risk}/{horizon} Σ={sum(target.values())}"
            for cls in ("cash", "fixed_income", "equity"):
                lo, hi = rng[cls]
                assert lo - 1e-6 <= target[cls] <= hi + 1e-6, f"{risk}/{horizon}/{cls} 越界"


def test_allocation_fitness_rewards_diversified():
    # 金融资产口径（现金14.3/固收42.9/股票42.9）接近 balanced 点目标，房产 30% 不超限
    assets = [{"type": "存款", "value": 100000}, {"type": "基金", "value": 300000},
              {"type": "股票", "value": 300000}, {"type": "房产", "value": 300000}]
    fit = al.allocation_fitness(assets)
    assert fit["score"] > 80  # 轻微偏离 + 单股 30% 集中度惩罚，仍高分


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
    # 3 年内用款目标 → 提高现金、压降权益（点目标比较）
    goals = [{"goal_kind": "cashflow", "annual_amount": 500000, "duration_years": 2, "start_year": 2}]
    pol = al.personalized_policy(None, goals)
    base_point = al._normalize_target(al.allocation_policy("balanced", 10))
    assert pol["target"]["cash"] > base_point["cash"]
    assert pol["target"]["equity"] < base_point["equity"]
    assert abs(sum(pol["target"].values()) - 1.0) < 0.001


def test_personalized_policy_high_debt():
    liab = [{"type": "房贷", "monthly_payment": 30000}]
    cf = [{"flow_type": "income", "amount": 50000, "period": "月"}]
    pol = al.personalized_policy(None, None, liab, cf)
    base_point = al._normalize_target(al.allocation_policy("balanced", 10))
    assert pol["target"]["equity"] < base_point["equity"]  # DTI=0.6 > 0.5 压降权益上限
    assert abs(sum(pol["target"].values()) - 1.0) < 0.001
