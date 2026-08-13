"""P1 修复契约测试：CHECK_ISSUES / CHECK_GOALS / EXPLAIN_RESULT 不再空壳。"""
from app.agent.response import build_metrics, build_response
from app.decision import build_issues
from app.services.goals import build_goals

_FAMILY = {
    "persons": [], "assets": [{"type": "房产", "name": "房", "value": 3000000}],
    "liabilities": [{"type": "房贷", "principal": 1000000, "monthly_payment": 12000,
                     "interest_rate": 3.5, "remaining_months": 240}],
    "cashflows": [{"flow_type": "income", "amount": 20000, "period": "月"},
                  {"flow_type": "expense", "amount": 15000, "period": "月"}],
    "goals": [{"type": "教育", "name": "教育金", "target_amount": 1000000,
               "target_date": "2036", "current_saved": 100000}],
    "reminders": [], "insurance": [], "family_profile": None,
}


def test_check_issues_metrics_nonempty():
    r = build_issues(_FAMILY)
    ms = build_metrics("CHECK_ISSUES", r)
    assert ms                                  # 不再空
    for m in ms:
        assert m.value is not None and m.source.startswith("issues.")


def test_check_issues_response_has_substance():
    r = build_issues(_FAMILY)
    resp = build_response("CHECK_ISSUES", "ok", r, summary="已梳理")
    assert resp.finding                        # 非空
    assert resp.recommendations                # 非空
    assert resp.metrics                        # 非空


def test_check_goals_response_has_substance():
    r = {"goals": build_goals(_FAMILY)}
    resp = build_response("CHECK_GOALS", "ok", r, summary="已汇总")
    assert resp.finding and resp.recommendations
