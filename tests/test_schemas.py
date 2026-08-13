"""Schema 层测试：统一 I/O 契约的构造与校验。"""
from app.schemas import (
    FamilyData, Issue, Recommendation, GoalOut, ScenarioRequest,
    Overview, RetirementBlock,
)


def test_family_data_from_dict_fills_missing_keys():
    fd = FamilyData.from_dict({"assets": [{"type": "存款", "value": 100}]})
    assert fd.assets == [{"type": "存款", "value": 100}]
    assert fd.liabilities == []
    assert fd.family_profile is None


def test_family_data_ignores_unknown_keys():
    fd = FamilyData.from_dict({"assets": [], "unknown_field": 123})
    assert not hasattr(fd, "unknown_field")


def test_issue_constructs_with_defaults():
    issue = Issue(issue_id="RETIREMENT_LIQUIDITY_001", type="retirement", severity="P0",
                  title="退休流动资金不足", reason=["房产占比过高"],
                  metric={"rfr": 0.48, "nwc": 2.49}, target={"rfr": 1.0},
                  recommendations=[Recommendation(action="增加金融资产", detail="...")])
    assert issue.reason == ["房产占比过高"]
    assert issue.metric["rfr"] == 0.48
    assert issue.recommendations[0].action == "增加金融资产"
    assert issue.finding == ""  # 默认空
    assert issue.scenarios == []


def test_goal_out_defaults():
    g = GoalOut(type="教育", name="孩子大学", goal_kind="cashflow")
    assert g.target_amount == 0.0
    assert g.coverage == 0.0
    assert g.monthly_needed is None


def test_scenario_request_default_params():
    req = ScenarioRequest()
    assert req.params == {}


def test_overview_constructs_with_defaults():
    o = Overview(wealth_score=81, wealth_level="稳健", net_worth=5000000,
                 retirement=RetirementBlock(rfr=2.21, nwc=2.61, quadrant="养老健康"))
    assert o.wealth_score == 81
    assert o.retirement.quadrant == "养老健康"
    assert o.retirement.known_limitations == []
    assert o.issues == []
