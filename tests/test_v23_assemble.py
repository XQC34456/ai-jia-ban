"""V2.3 组装升级测试：assemble 接入 evidence/priorities/tradeoffs/uncertainty。

铁律：
- evidence 数字来自 tool_results（带 source）；priorities 来自 Decision。
- tradeoffs/uncertainty 逐字透传；tradeoff 含数字 → 丢弃（定性描述防编造）。
- 旧 JSON（无新字段）→ 新字段空，向后兼容。
"""
from app.agent.response import assemble_advisor_response
from app.schemas.agent import TradeoffRef


def _issues_result():
    return {
        "data_origin": "real",
        "issues": [
            {"issue_id": "emergency", "type": "liquidity", "severity": "P0",
             "title": "应急金不足", "finding": "应急金不足3个月"},
        ],
        "alerts": ["应急金不足"],
        "priorities": [
            {"issue_id": "emergency", "type": "liquidity", "severity": "P0", "title": "应急金不足"},
        ],
        "recommendations": [],
    }


def test_assemble_includes_new_fields():
    tool_results = [
        {"name": "get_wealth_issues", "result": _issues_result()},
        {"name": "get_cashflow",
         "result": {"data_origin": "real", "cashflow": {"savings_rate": 0.15}}},
    ]
    llm_json = {
        "summary": "现金流优先",
        "evidence": [{"claim": "储蓄率偏低", "metric_key": "savings_rate"}],
        "tradeoffs": [{"option": "先还贷", "gain": "省利息", "loss": "流动性降"}],
        "uncertainty": {"confidence": "low", "missing": ["房贷利率"]},
    }
    resp = assemble_advisor_response(tool_results, llm_json, "CHECK_ISSUES")
    assert resp.evidence and resp.evidence[0].metric.source
    assert resp.priorities and resp.priorities[0].severity == "P0"
    assert resp.tradeoffs and resp.tradeoffs[0].option == "先还贷"
    assert resp.uncertainty and resp.uncertainty.confidence == "low"


def test_assemble_empty_new_fields_backward_compatible():
    resp = assemble_advisor_response([], {"summary": "ok"}, "VIEW_OVERVIEW")
    assert resp.priorities == []
    assert resp.evidence == []
    assert resp.tradeoffs == []
    assert resp.uncertainty is None


def test_assemble_tradeoffs_transparent():
    llm_json = {
        "summary": "x",
        "tradeoffs": [{"option": "现在买", "gain": "住房确定性", "loss": "流动性下降"}],
    }
    resp = assemble_advisor_response([], llm_json, "VIEW_OVERVIEW")
    assert resp.tradeoffs == [TradeoffRef(option="现在买", gain="住房确定性", loss="流动性下降")]


def test_assemble_tradeoff_with_digit_dropped():
    llm_json = {"summary": "x",
                "tradeoffs": [{"option": "买500万", "gain": "省5万利息", "loss": "流动性降"}]}
    resp = assemble_advisor_response([], llm_json, "VIEW_OVERVIEW")
    assert resp.tradeoffs == []


def test_assemble_uncertainty_normalizes_invalid_confidence():
    llm_json = {"summary": "x", "uncertainty": {"confidence": "确信", "missing": ["房价"]}}
    resp = assemble_advisor_response([], llm_json, "VIEW_OVERVIEW")
    assert resp.uncertainty is not None
    assert resp.uncertainty.confidence == "medium"
