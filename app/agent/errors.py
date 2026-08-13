"""A3 错误映射：ToolError.kind → (status, summary, next_actions)，确定性。

四种 kind 封闭（与 A2 ToolError 一一对应）：
- forbidden          → refused + 结构化 next_action ["upgrade"]
- unknown_scenario   → need_clarification
- invalid_params     → need_clarification
- unexecutable       → refused（summary 逐字透传引擎 ValueError 的 message，非本层编造）
"""
from __future__ import annotations

__all__ = ["map_tool_error"]

_ERROR_MAP = {
    "forbidden": ("refused", "深度报告和决策模拟是 VIP 专属功能，升级后即可使用", ["upgrade"]),
    "unknown_scenario": ("need_clarification", "我暂时只支持四种情景：买房、提前还贷、投资、收入变化", []),
    "invalid_params": ("need_clarification", "需要补充或修正以下参数", []),
    "unexecutable": ("refused", "当前家庭数据无法执行该方案", []),
}


def map_tool_error(kind: str, detail: dict | None = None) -> tuple[str, str, list[str]]:
    """返回 (status, summary, next_actions)。未知 kind → ("error", 通用, [])。"""
    status, summary, actions = _ERROR_MAP.get(kind, ("error", "处理失败，请稍后再试", []))
    if kind == "unexecutable" and detail and detail.get("message"):
        summary = summary + "：" + detail["message"]
    return status, summary, list(actions)
