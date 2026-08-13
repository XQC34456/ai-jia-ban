"""Decision Layer 测试：四象限、7 类检测器、优先级排序、issue 组装。"""
from app.decision import build_issues, retirement_quadrant
from app.decision.priority import rank


def _fd(**overrides):
    base = {
        "family": {"id": 1, "name": "测试家庭"},
        "persons": [{"name": "本人", "relation": "本人", "birth_year": 1976}],  # 50 岁
        "assets": [{"type": "存款", "value": 100000}],
        "liabilities": [],
        "cashflows": [
            {"flow_type": "income", "amount": 30000, "period": "月"},
            {"flow_type": "expense", "amount": 20000, "period": "月"},
        ],
        "goals": [], "insurance": [], "reminders": [],
        "family_profile": {"risk_profile": "balanced", "investment_horizon": 10},
    }
    base.update(overrides)
    return base


def test_quadrant_four_cases():
    assert retirement_quadrant(2.0, 2.5) == "养老健康"
    assert retirement_quadrant(0.48, 2.49) == "资产充足但流动性不足"
    assert retirement_quadrant(0.5, 0.6) == "养老资金不足"
    assert retirement_quadrant(1.2, 0.8) == "高杠杆/资产结构问题"
    assert retirement_quadrant(None, 1.0) == "未知"


def test_rank_orders_p0_first():
    issues = [
        {"issue_id": "a", "severity": "P2"},
        {"issue_id": "b", "severity": "P0"},
        {"issue_id": "c", "severity": "P1"},
    ]
    assert [i["issue_id"] for i in rank(issues)] == ["b", "c", "a"]


def test_empty_family_no_issues():
    out = build_issues({})
    assert out["issues"] == []
    assert set(out.keys()) == {"issues", "alerts", "priorities", "recommendations"}


def test_negative_cashflow_detected_p0():
    fd = _fd(cashflows=[
        {"flow_type": "income", "amount": 10000, "period": "月"},
        {"flow_type": "expense", "amount": 20000, "period": "月"},
    ])
    issues = {i["type"]: i for i in build_issues(fd)["issues"]}
    assert issues["cashflow"]["severity"] == "P0"
    assert issues["cashflow"]["title"] == "家庭现金流为负"


def test_house_rich_cash_poor_retirement_issue():
    # 高房产 + 低现金 + 低结余 → 应识别「净资产充足但可投资资产不足」
    fd = _fd(assets=[{"type": "房产", "value": 8000000}, {"type": "存款", "value": 100000}],
             cashflows=[
                 {"flow_type": "income", "amount": 30000, "period": "月"},
                 {"flow_type": "expense", "amount": 28000, "period": "月"},
             ])
    issues = {i["type"]: i for i in build_issues(fd)["issues"]}
    assert "retirement" in issues
    r = issues["retirement"]
    assert r["severity"] == "P0"
    assert r["title"] == "退休流动资金不足"
    assert r["metric"]["rfr"] < 1
    assert r["metric"]["nwc"] >= 1
    assert any("金融资产" in rec["action"] or "现金" in rec["action"] for rec in r["recommendations"])


def test_low_liquidity_detected():
    # 高支出低现金 → 应急月数不足
    fd = _fd(assets=[{"type": "存款", "value": 10000}],
             cashflows=[
                 {"flow_type": "income", "amount": 30000, "period": "月"},
                 {"flow_type": "expense", "amount": 20000, "period": "月"},
             ])
    issues = {i["type"]: i for i in build_issues(fd)["issues"]}
    assert "liquidity" in issues
    assert issues["liquidity"]["severity"] in ("P0", "P1")


def test_high_debt_detected():
    fd = _fd(liabilities=[{"type": "房贷", "principal": 2000000, "monthly_payment": 20000,
                           "interest_rate": 0.035, "remaining_months": 240}])
    issues = {i["type"]: i for i in build_issues(fd)["issues"]}
    assert "debt" in issues
    assert issues["debt"]["severity"] in ("P0", "P1")
    assert issues["debt"]["metric"]["dti"] > 0.3


def test_idle_cash_detected_p2():
    # 大量现金、无短期目标 → 现金闲置决策
    fd = _fd(assets=[{"type": "存款", "value": 3000000}],
             cashflows=[
                 {"flow_type": "income", "amount": 30000, "period": "月"},
                 {"flow_type": "expense", "amount": 10000, "period": "月"},
             ])
    issues = {i["type"]: i for i in build_issues(fd)["issues"]}
    assert "decision" in issues
    assert issues["decision"]["severity"] == "P2"
