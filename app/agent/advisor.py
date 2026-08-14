"""V2.2 AI Advisor 核心：tool_loop 多轮 function calling 循环。

铁律：
- LLM 只做「理解 + 选择工具 + 第二轮推理」，财富数字由系统从工具结果确定性取（Task 3）。
- 工具 = 顾问的眼睛和手（execute_tool → Engine/Decision/Sandbox），LLM 绝不替代。
- LLM 失败 / 超轮数 → 返回 None → 上层确定性兜底。
- 工具异常（ToolError）→ 不崩，error 回传给 LLM 继续循环。
"""
from __future__ import annotations

import json

from ..schemas.agent import AgentResponse
from .memory import record_judgment
from .provider import LLMProvider
from .response import assemble_advisor_response
from .tool_schemas import TOOL_SCHEMAS, execute_tool
from .tools import ToolError

__all__ = ["run_advisor", "advise"]

MAX_ROUNDS = 6

_ADVISOR_SYSTEM = (
    "你是家庭财富顾问。你的价值不是「回答财富问题」，而是「站在这个家庭的位置，"
    "帮它做一个更好的决策」。\n"
    "你有一个决策循环（每次重要对话都走，内化思考，不必逐字输出）：\n"
    "UNDERSTAND  先理解用户真正的问题（表层之下他到底要做什么决策），判断是否信息不足需要追问。\n"
    "DIAGNOSE    涉及家庭数据必须调工具：get_wealth_issues 拿 priorities，按需 overview/cashflow/"
    "allocation/retirement/goals。\n"
    "PRIORITIZE  读 get_wealth_issues 返回的 priorities[0]，确定「当前主要矛盾」，回答围绕它组织，"
    "不把问题平铺罗列。\n"
    "VERIFY      决策类问题（买房/还贷/投资/收入变化）必须调 run_scenario / compare_scenarios 验证，"
    "不空口给方向。\n"
    "REASON      组织「证据→判断→权衡」：每条重要判断配 evidence（claim 定性 + metric_key 引用数字），"
    "多方案给 tradeoffs。\n"
    "RECOMMEND   给建议。绝不制造「最优/最佳方案」——只帮用户看清每个选项「得到什么 / 失去什么」。\n"
    "ACT         给 next_actions：带动词、指向具体工具/下一步，主动带用户往下走。\n"
    "行为规则：\n"
    "1. 数字：你绝不计算、绝不编造财富数字。需要数字时用 evidence 的 metric_key 引用"
    "（合法 key：wealth_score/net_worth/dti/cashflow_surplus/savings_rate/liquidity_months/"
    "rfr/nwc/real_estate_pct），数值由系统从工具结果注入。summary/finding/claim 一律写定性判断，不写数字。\n"
    "2. 主要矛盾：用 Decision 给的 priorities[0]，不要自己判断谁最严重。\n"
    "3. 不确定：信息不足或判断依据不够时，输出 uncertainty（confidence/missing/alternatives），"
    "敢说「我现在还不能判断」，并说明缺什么。\n"
    "4. 反例行为：\n"
    "   - 用户质疑你「说得不对」→ 重新审视证据，承认可能的信息差，不甩锅、不嘴硬。\n"
    "   - 用户情绪化（「我这辈子攒不下钱」）→ 先共情承接，再诊断，不甩理财知识。\n"
    "   - 用户要绝对答案（「就告诉我买不买」）→ 拒绝简单二选一，给 tradeoffs 并解释为什么不能二选一。\n"
    "   - 用户补充新事实 → 重新理解、重新调工具，不坚持旧结论。\n"
    "5. 纯金融计算（复利/年化收益率，不涉及具体家庭数据）→ 拒绝："
    "{\"refuse\": true, \"summary\": \"这是独立的金融计算，我不能自行测算，需要结合你的家庭数据才有意义\"}。\n"
    "最终回答必须是 JSON（禁止 JSON 之外的文字），结构：\n"
    "{\"summary\":\"结论(定性)\",\"finding\":\"为什么\","
    "\"evidence\":[{\"claim\":\"定性判断\",\"metric_key\":\"合法key\"}],"
    "\"tradeoffs\":[{\"option\":\"方案\",\"gain\":\"得到什么\",\"loss\":\"失去什么\"}],"
    "\"uncertainty\":{\"confidence\":\"high|medium|low\",\"missing\":[\"缺什么\"],"
    "\"alternatives\":[\"备选解释\"]},\"recommendations\":[\"建议\"],"
    "\"next_actions\":[\"下一步\"],\"missing\":[\"信息缺口\"],\"refuse\":false}。\n"
    "missing 仅在信息不足时出现；refuse 仅在拒绝独立计算时为 true。"
)


def _messages_with_context(message: str, wealth_context: str | None,
                           memory_context: str | None = None) -> list[dict]:
    system = _ADVISOR_SYSTEM
    if wealth_context:
        system = f"{system}\n\n【家庭背景】\n{wealth_context}"
    if memory_context:
        system = f"{system}\n\n【记忆】\n{memory_context}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": message},
    ]


def run_advisor(user: dict, message: str, llm: LLMProvider,
                wealth_context: str | None = None,
                memory_context: str | None = None) -> dict | None:
    """tool_loop 多轮循环：LLM 选工具 → execute_tool → 结果回传 → 第二轮推理。

    返回 {"tool_results": [{"name", "result"}], "content": str | None} 或 None（降级）。
    tool_results 按调用顺序记录（同名工具多次调用各自保留）。
    """
    messages = _messages_with_context(message, wealth_context, memory_context)
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


_CLARIFY_PREFIX = "需要补充以下信息："


def _parse_json(content: str | None) -> dict | None:
    if not content:
        return None
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def advise(user: dict, message: str, llm: LLMProvider,
           wealth_context: str | None = None,
           memory_context: str | None = None,
           intent: str = "VIEW_OVERVIEW") -> AgentResponse | None:
    """编排 advisor 完整流程：run_advisor → 解析 → refuse/missing → 组装。

    返回 AgentResponse，或 None（LLM 失败 / content 无法解析 → 上层确定性兜底）。
    """
    raw = run_advisor(user, message, llm, wealth_context=wealth_context,
                      memory_context=memory_context)
    if raw is None:
        return None
    llm_json = _parse_json(raw.get("content"))
    if llm_json is None:
        return None
    tool_results = raw.get("tool_results") or []

    if llm_json.get("refuse"):
        return assemble_advisor_response(tool_results, llm_json, intent, status="refused")

    missing = llm_json.get("missing")
    if missing and isinstance(missing, list) and missing:
        clarify = _CLARIFY_PREFIX + "、".join(str(m) for m in missing)
        resp = assemble_advisor_response(tool_results, llm_json, intent,
                                         status="need_clarification")
        return resp.model_copy(update={"summary": clarify})

    resp = assemble_advisor_response(tool_results, llm_json, intent, status="ok")
    record_judgment(user, resp)
    return resp
