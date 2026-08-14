"""V2.3 数字引用机制测试：evidence metric_key → MetricRef 注入（白名单 + 找不到丢弃）。

铁律：
- metric_key 白名单：只能引用 build_metrics 会产出的稳定 key，自由造 key 一律丢弃。
- claim 必须定性（含数字即丢弃），数字由系统注入 value+source。
- 找不到数字 → 丢弃（宁可丢弃，不可编造）。
"""
from app.agent.response import _build_evidence


def test_evidence_rfr_from_retirement():
    tool_results = [{"name": "get_retirement",
                     "result": {"data_origin": "real", "retirement": {"rfr": 0.43, "nwc": 0.9}}}]
    raw = [{"claim": "养老可投资覆盖不足", "metric_key": "rfr"}]
    ev = _build_evidence(tool_results, raw)
    assert len(ev) == 1
    assert ev[0].claim == "养老可投资覆盖不足"
    assert ev[0].metric.value == 0.43
    assert ev[0].metric.source == "overview.retirement.rfr"


def test_evidence_savings_rate_from_cashflow():
    tool_results = [{"name": "get_cashflow",
                     "result": {"data_origin": "real", "cashflow": {"savings_rate": 0.15}}}]
    raw = [{"claim": "储蓄率偏低", "metric_key": "savings_rate"}]
    ev = _build_evidence(tool_results, raw)
    assert len(ev) == 1
    assert ev[0].metric.value == 0.15
    assert ev[0].metric.source == "overview.cashflow.savings_rate"


def test_evidence_unknown_key_dropped():
    tool_results = [{"name": "get_retirement",
                     "result": {"data_origin": "real", "retirement": {"rfr": 0.43}}}]
    raw = [{"claim": "假引用", "metric_key": "不存在的key"}]
    assert _build_evidence(tool_results, raw) == []


def test_evidence_claim_with_digit_dropped():
    tool_results = [{"name": "get_retirement",
                     "result": {"data_origin": "real", "retirement": {"rfr": 0.43}}}]
    raw = [{"claim": "RFR 是 0.43", "metric_key": "rfr"}]
    assert _build_evidence(tool_results, raw) == []


def test_evidence_all_values_have_source():
    tool_results = [{"name": "get_retirement",
                     "result": {"data_origin": "real", "retirement": {"rfr": 0.43}}}]
    raw = [{"claim": "覆盖不足", "metric_key": "rfr"}]
    ev = _build_evidence(tool_results, raw)
    assert ev and all(e.metric.source for e in ev)
