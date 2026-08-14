"""V2.3 AgentResponse 扩展 Schema 契约测试。

铁律（A1 只扩不减）：
- 新增 PriorityRef/EvidenceRef/TradeoffRef/UncertaintyRef 全部 optional、default 空。
- EvidenceRef.metric 复用 MetricRef 硬闸（value 非空 → source 必填）。
- 旧 AgentResponse 构造不传新字段 → 新字段默认空，旧行为不破坏。
"""
import pytest
from pydantic import ValidationError

from app.schemas.agent import (
    AgentResponse,
    EvidenceRef,
    MetricRef,
    PriorityRef,
    TradeoffRef,
    UncertaintyRef,
)


def test_new_refs_instantiate():
    p = PriorityRef(issue_id="cashflow", severity="P0", title="现金流紧张", finding="月结余为负")
    assert p.severity == "P0"
    t = TradeoffRef(option="现在买房", gain="住房确定性", loss="流动性下降")
    assert t.gain == "住房确定性"
    u = UncertaintyRef(confidence="low", missing=["房价"], alternatives=["收入结构问题"])
    assert u.confidence == "low"
    m = MetricRef(key="rfr", label="RFR", unit="ratio", value=0.43,
                  source="overview.retirement.rfr")
    e = EvidenceRef(claim="养老覆盖不足", metric=m)
    assert e.metric.value == 0.43


def test_evidence_metric_value_needs_source():
    # MetricRef 硬闸：带 value 无 source 的 MetricRef 根本无法构造，
    # 因此 EvidenceRef.metric 不可能携带「无出处数字」。
    with pytest.raises(ValidationError):
        MetricRef(key="rfr", label="RFR", unit="ratio", value=0.43)  # 无 source


def test_agent_response_defaults_empty():
    r = AgentResponse(intent="VIEW_OVERVIEW", status="ok", summary="x")
    assert r.priorities == []
    assert r.evidence == []
    assert r.tradeoffs == []
    assert r.uncertainty is None


def test_agent_response_new_fields_roundtrip():
    m = MetricRef(key="rfr", label="RFR", unit="ratio", value=0.43, source="s")
    r = AgentResponse(
        intent="CHECK_ISSUES", status="ok", summary="s",
        priorities=[PriorityRef(issue_id="i", severity="P0", title="t", finding="f")],
        evidence=[EvidenceRef(claim="c", metric=m)],
        tradeoffs=[TradeoffRef(option="o", gain="g", loss="l")],
        uncertainty=UncertaintyRef(confidence="low"),
    )
    d = r.model_dump()
    assert d["priorities"][0]["issue_id"] == "i"
    assert d["evidence"][0]["metric"]["value"] == 0.43
    assert d["uncertainty"]["confidence"] == "low"
