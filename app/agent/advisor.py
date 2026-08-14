"""V2.2 AI Advisor 核心：tool_loop 多轮 function calling 循环。

铁律：
- LLM 只做「理解 + 选择工具 + 第二轮推理」，财富数字由系统从工具结果确定性取（Task 3）。
- 工具 = 顾问的眼睛和手（execute_tool → Engine/Decision/Sandbox），LLM 绝不替代。
- LLM 失败 / 超轮数 → 返回 None → 上层确定性兜底。
- 工具异常（ToolError）→ 不崩，error 回传给 LLM 继续循环。
"""
from __future__ import annotations

import json

from .provider import LLMProvider
from .tool_schemas import TOOL_SCHEMAS, execute_tool
from .tools import ToolError

__all__ = ["run_advisor"]

MAX_ROUNDS = 6

_ADVISOR_SYSTEM = (
    "你是家庭财富顾问。你的能力是调用工具获取真实家庭数据，再基于数据给出顾问式判断。\n"
    "规则：\n"
    "1. 涉及家庭资产/负债/现金流/退休/配置/目标等，必须调用工具获取真实数据，"
    "绝不编造、绝不心算。\n"
    "2. 信息不足时不要猜，在输出里用 missing 字段列出还缺什么（中文字段名）。\n"
    "3. 最终回答必须是 JSON，禁止输出 JSON 之外的文字；禁止在文字里出现任何财富数字"
    "（金额/百分比/评分/比率等具体数值由系统从工具结果注入，你只写定性判断）。\n"
    "4. 工具返回结果后，读真实数据做第二轮推理，把结论写成人话，不甩内部标识。\n"
    "JSON 结构：{\"summary\":\"结论\",\"finding\":\"为什么\","
    "\"recommendations\":[\"建议\"],\"next_actions\":[\"下一步\"],\"missing\":[\"缺的字段\"]}。\n"
    "missing 仅在信息不足时出现。"
)


def _messages_with_context(message: str, wealth_context: str | None) -> list[dict]:
    system = _ADVISOR_SYSTEM
    if wealth_context:
        system = f"{system}\n\n【家庭背景】\n{wealth_context}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": message},
    ]


def run_advisor(user: dict, message: str, llm: LLMProvider,
                wealth_context: str | None = None) -> dict | None:
    """tool_loop 多轮循环：LLM 选工具 → execute_tool → 结果回传 → 第二轮推理。

    返回 {"tool_results": [{"name", "result"}], "content": str | None} 或 None（降级）。
    tool_results 按调用顺序记录（同名工具多次调用各自保留）。
    """
    messages = _messages_with_context(message, wealth_context)
    tool_results: list[dict] = []

    for _ in range(MAX_ROUNDS):
        resp = llm.chat(messages, tools=TOOL_SCHEMAS)
        if resp is None:
            return None
        tool_calls = resp.get("tool_calls") or []
        if not tool_calls:
            return {"tool_results": tool_results, "content": resp.get("content")}

        # 回传 assistant tool_calls（OpenAI 格式：id/type/function.arguments 字符串）
        assistant_calls = [{
            "id": tc.get("id"),
            "type": "function",
            "function": {
                "name": tc["name"],
                "arguments": json.dumps(tc.get("arguments") or {}, ensure_ascii=False),
            },
        } for tc in tool_calls]
        messages.append({"role": "assistant", "content": resp.get("content"),
                         "tool_calls": assistant_calls})

        # 执行每个工具，回传结果 / 结构化错误
        for tc in tool_calls:
            try:
                result = execute_tool(tc["name"], tc.get("arguments") or {}, user)
                tool_results.append({"name": tc["name"], "result": result})
                content = json.dumps(result, ensure_ascii=False, default=str)
            except ToolError as e:
                tool_results.append({"name": tc["name"], "result": None})
                content = json.dumps({"error": e.kind, "detail": e.detail},
                                     ensure_ascii=False, default=str)
            messages.append({"role": "tool", "tool_call_id": tc.get("id"),
                             "name": tc["name"], "content": content})

    return None
