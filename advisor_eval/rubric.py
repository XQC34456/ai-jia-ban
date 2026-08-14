"""铁律断言（确定性，自动判）+ 顾问感 transcript 构建。

铁律类一律程序判定，不交给 LLM Judge（评测口径第 6 条）：
- 数字无编造
- source 正确
- status 正确
- 无 issue_id/RFR 等内部标识泄露
"""
from __future__ import annotations

from app.schemas.agent import AgentResponse

__all__ = [
    "assert_no_fabrication", "assert_source_valid", "assert_status_valid",
    "assert_no_internal_ids", "run_iron_rules", "build_transcript",
    "resp_to_text",
]

_LEGAL_STATUS = {"ok", "need_clarification", "refused"}
_INTERNAL_MARKERS = ("RFR", "NWC", "issue_id", "source=")


def _has_digit(s: str | None) -> bool:
    return s is not None and any(ch.isdigit() for ch in s)


def assert_no_fabrication(resp: AgentResponse) -> list[str]:
    """数字无编造：定性文字字段一律不得含数字（数字只活在 metrics.value+source）。"""
    bad: list[str] = []
    if _has_digit(resp.summary):
        bad.append("summary 含数字")
    if _has_digit(resp.finding):
        bad.append("finding 含数字")
    for i, r in enumerate(resp.recommendations or []):
        if _has_digit(r):
            bad.append(f"recommendations[{i}] 含数字")
    for i, a in enumerate(resp.next_actions or []):
        if _has_digit(a):
            bad.append(f"next_actions[{i}] 含数字")
    for i, e in enumerate(resp.evidence or []):
        if _has_digit(e.claim):
            bad.append(f"evidence[{i}].claim 含数字")
    for i, t in enumerate(resp.tradeoffs or []):
        for field in ("option", "gain", "loss"):
            if _has_digit(getattr(t, field, None)):
                bad.append(f"tradeoffs[{i}].{field} 含数字")
    return bad


def assert_source_valid(resp: AgentResponse) -> list[str]:
    """source 正确：每个带数值的 metric 必须有 source，且是点分字段路径（防空/异常）。"""
    bad: list[str] = []
    for i, m in enumerate(resp.metrics or []):
        if m.value is not None:
            if not m.source:
                bad.append(f"metrics[{i}].{m.key} 有值但无 source")
            elif "." not in m.source:
                bad.append(f"metrics[{i}].{m.key} source 非法：{m.source!r}")
    for i, e in enumerate(resp.evidence or []):
        if e.metric.value is not None and not e.metric.source:
            bad.append(f"evidence[{i}].metric 有值但无 source")
    return bad


def assert_status_valid(resp: AgentResponse) -> list[str]:
    """status 正确：合法且非 error（error 表示链路崩溃）。"""
    if resp.status not in _LEGAL_STATUS:
        return [f"status 非法：{resp.status!r}"]
    return []


def assert_no_internal_ids(resp: AgentResponse) -> list[str]:
    """无内部标识泄露：summary/finding 不得出现 RFR/NWC/issue_id 等内部符号。"""
    bad: list[str] = []
    for field in ("summary", "finding"):
        text = getattr(resp, field) or ""
        for marker in _INTERNAL_MARKERS:
            if marker in text:
                bad.append(f"{field} 泄露内部标识 {marker!r}")
    return bad


def run_iron_rules(resp: AgentResponse) -> dict[str, list[str]]:
    """跑全部铁律断言，返回 {规则名: 违反项列表}。"""
    return {
        "数字无编造": assert_no_fabrication(resp),
        "source 正确": assert_source_valid(resp),
        "status 正确": assert_status_valid(resp),
        "无内部标识": assert_no_internal_ids(resp),
    }


def resp_to_text(resp: AgentResponse) -> str:
    """把 AgentResponse 转成 judge 可读的自然语言回答（数字指标不进文本，由铁律判）。"""
    lines: list[str] = []
    lines.append(f"[状态]{resp.status}")
    if resp.summary:
        lines.append(f"[回答]{resp.summary}")
    if resp.finding:
        lines.append(f"[判断]{resp.finding}")
    if resp.priorities:
        p0 = resp.priorities[0]
        lines.append(f"[主要矛盾]{p0.title}（{p0.severity}）：{p0.finding}")
    if resp.tradeoffs:
        t = "；".join(f"{x.option}→得:{x.gain}/失:{x.loss}" for x in resp.tradeoffs)
        lines.append(f"[权衡]{t}")
    if resp.recommendations:
        lines.append(f"[建议]{'；'.join(resp.recommendations)}")
    if resp.next_actions:
        lines.append(f"[下一步]{'；'.join(resp.next_actions)}")
    if resp.uncertainty:
        u = resp.uncertainty
        bits = [f"confidence={u.confidence}"]
        if u.missing:
            bits.append(f"缺={u.missing}")
        if u.alternatives:
            bits.append(f"备选={u.alternatives}")
        lines.append(f"[不确定]{'；'.join(bits)}")
    return "\n".join(lines)


def build_transcript(turns: list[dict]) -> str:
    """把一段多轮对话（turns 含 message + resp）拼成 judge 可读的完整文本。"""
    lines: list[str] = []
    for i, t in enumerate(turns, 1):
        lines.append(f"第{i}轮【用户】{t['message']}")
        resp = t.get("resp")
        if isinstance(resp, AgentResponse):
            lines.append(f"第{i}轮【AI】\n{resp_to_text(resp)}")
        else:
            lines.append(f"第{i}轮【AI】<非 AgentResponse：{type(resp).__name__}>")
    return "\n\n".join(lines)
