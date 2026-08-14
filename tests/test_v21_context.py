"""V2.1 Context Engine 测试：组装器纯函数 + 数字带 source + 与 Engine 输出一致。

铁律：组装器零计算，只「搬运」build_overview 已算好的数字；每个带 value 的数字必带 source。
"""
from app.agent.context import build_wealth_context, context_to_text
from app.services import build_overview


def _fd(**overrides):
    base = {
        "family": {"id": 1, "name": "测试家庭"},
        "persons": [{"name": "本人", "relation": "本人", "birth_year": 1976}],
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


def _rich_fd():
    return _fd(
        assets=[{"type": "房产", "value": 3000000}, {"type": "存款", "value": 500000}],
        liabilities=[{"type": "房贷", "principal": 800000, "monthly_payment": 5000,
                      "interest_rate": 0.035, "remaining_months": 240}],
    )


# ---------- 空家庭 ----------

def test_empty_family_returns_empty_blocks():
    ctx = build_wealth_context({"family": {}, "persons": [], "assets": [],
                                "liabilities": [], "cashflows": [], "goals": [],
                                "reminders": [], "insurance": [], "family_profile": None})
    assert ctx["family"]["members"] == []
    assert ctx["financial"]["rfr"]["value"] is None  # 无年龄 → 无养老测算
    assert ctx["decision"]["issues"] == []
    assert ctx["goals"] == []


# ---------- 数字正确性（搬运不重算） ----------

def test_financial_numbers_match_overview():
    data = _rich_fd()
    ctx = build_wealth_context(data)
    ov = build_overview(data)
    assert ctx["financial"]["wealth_score"]["value"] == ov["wealth_score"]
    assert ctx["financial"]["net_worth"]["value"] == ov["net_worth"]
    assert ctx["financial"]["total_assets"]["value"] == ov["total_assets"]
    assert ctx["financial"]["total_liabilities"]["value"] == ov["total_liabilities"]
    assert ctx["financial"]["monthly_income"]["value"] == ov["cashflow"]["income"]
    assert ctx["financial"]["dti"]["value"] == ov["debt"]["dti"]
    assert ctx["financial"]["emergency_months"]["value"] == ov["liquidity"]["emergency_months"]


# ---------- 防编造硬闸 ----------

def test_every_financial_number_carries_source():
    ctx = build_wealth_context(_rich_fd())
    for key, item in ctx["financial"].items():
        if isinstance(item, dict) and item.get("value") is not None:
            assert item.get("source"), f"financial.{key} 带数值却无 source"


def test_financial_source_paths_are_overview_scoped():
    ctx = build_wealth_context(_rich_fd())
    assert ctx["financial"]["net_worth"]["source"] == "overview.net_worth"
    assert ctx["financial"]["wealth_score"]["source"] == "overview.wealth_score"
    assert ctx["financial"]["monthly_surplus"]["source"] == "overview.cashflow.surplus"


# ---------- Family / Decision / Goal 块 ----------

def test_family_members_carry_raw_fields():
    ctx = build_wealth_context(_fd())
    m = ctx["family"]["members"][0]
    assert m["relation"] == "本人"
    assert m["birth_year"] == 1976


def test_decision_issues_and_goals_populated():
    data = _fd(goals=[{"id": 1, "type": "教育", "name": "孩子大学", "target_amount": 500000,
                       "target_date": "2030-08-01", "current_saved": 100000}])
    ctx = build_wealth_context(data)
    ov = build_overview(data)
    assert [g["name"] for g in ctx["goals"]] == [g["name"] for g in ov["goals"]]
    assert [i["title"] for i in ctx["decision"]["issues"]] == [i["title"] for i in ov["issues"]]


# ---------- 序列化 ----------

def test_context_to_text_contains_key_number_and_source():
    ctx = build_wealth_context(_rich_fd())
    text = context_to_text(ctx)
    assert text
    assert "overview.net_worth" in text  # source 标注出现在文本里


def test_context_to_text_empty_family():
    ctx = build_wealth_context({"family": {}, "persons": [], "assets": [],
                                "liabilities": [], "cashflows": [], "goals": [],
                                "reminders": [], "insurance": [], "family_profile": None})
    assert context_to_text(ctx)  # 空家庭也返回非空占位文本
