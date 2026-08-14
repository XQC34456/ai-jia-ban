"""V2.3 主要矛盾提取测试：priorities 从 Decision build_issues 确定性提取，LLM 不判断。

铁律：
- 主要矛盾 = Decision 的 priorities（已按 P0→P2 排序），本层只读不改序。
- finding 逐字来自 issue.finding，不增删改。
"""
from app.agent.response import _build_priorities


def _issues_result():
    return {
        "data_origin": "real",
        "issues": [
            {"issue_id": "emergency", "type": "liquidity", "severity": "P0",
             "title": "应急金不足", "finding": "应急金不足3个月"},
            {"issue_id": "low_savings", "type": "savings", "severity": "P1",
             "title": "储蓄率偏低", "finding": "月储蓄率低于20%"},
        ],
        "alerts": ["应急金不足", "储蓄率偏低"],
        "priorities": [
            {"issue_id": "emergency", "type": "liquidity", "severity": "P0", "title": "应急金不足"},
            {"issue_id": "low_savings", "type": "savings", "severity": "P1", "title": "储蓄率偏低"},
        ],
        "recommendations": [],
    }


def test_priorities_extracted_with_finding():
    ps = _build_priorities([{"name": "get_wealth_issues", "result": _issues_result()}])
    assert len(ps) == 2
    assert ps[0].issue_id == "emergency"
    assert ps[0].severity == "P0"
    assert ps[0].title == "应急金不足"
    assert ps[0].finding == "应急金不足3个月"
    assert ps[1].severity == "P1"


def test_priorities_preserve_decision_order():
    # priorities 已按 P0→P2 排序（Decision rank），本层不改序
    ps = _build_priorities([{"name": "get_wealth_issues", "result": _issues_result()}])
    assert [p.severity for p in ps] == ["P0", "P1"]


def test_priorities_empty_when_no_issues():
    result = {"data_origin": "real", "issues": [], "alerts": [],
              "priorities": [], "recommendations": []}
    assert _build_priorities([{"name": "get_wealth_issues", "result": result}]) == []


def test_priorities_empty_when_no_issues_tool():
    tool_results = [{"name": "get_wealth_overview",
                     "result": {"data_origin": "real", "overview": {"net_worth": 100}}}]
    assert _build_priorities(tool_results) == []
