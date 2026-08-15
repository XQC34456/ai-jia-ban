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
from .response import EVIDENCE_METRIC_KEYS, _strip_numeric_text, assemble_advisor_response
from .tool_schemas import TOOL_SCHEMAS, execute_tool
from .tools import ToolError
from .vip import VIP_BOUNDARY

__all__ = ["run_advisor", "advise"]

MAX_ROUNDS = 6

# P1.1：确定性基线 —— 系统保证「意图 → 必需 Engine 数据」，不随 LLM 工具选择漂移。
# 每意图恒带 get_wealth_issues（主要矛盾 priorities[0] 定主次），再配意图主工具。
# 只保证 assemble 取数确定性（不回注 LLM 循环：LLM 已从 wealth_context 文本看到关键数字）。
_BASELINE_TOOLS: dict[str, tuple[str, ...]] = {
    "VIEW_OVERVIEW": ("get_wealth_overview", "get_wealth_issues"),
    "CHECK_ISSUES": ("get_wealth_issues", "get_wealth_overview"),
    "CHECK_RETIREMENT": ("get_retirement", "get_wealth_issues"),
    "CHECK_ALLOCATION": ("get_allocation", "get_wealth_issues"),
    "CHECK_GOALS": ("get_goals", "get_wealth_issues"),
    "SCENARIO_COMPARE": ("get_wealth_overview", "get_wealth_issues"),
    "EXPLAIN_RESULT": ("get_wealth_issues",),
}


def _with_baseline(tool_results: list[dict], intent: str, user: dict) -> list[dict]:
    """把意图必需的确定性基线补进 tool_results，保证 assemble 取数确定。

    LLM 已调过（且非 error）的同名工具不重复补；基线工具异常（ToolError）静默跳过，
    不因单一工具失败丢掉整条基线。返回 baseline 在前、LLM 工具结果在后的新列表。

    基线只在顾问「已进入财富诊断」（至少调了一个工具）时补全：纯聊天/知识问答/拒算
    （零工具）不应注入财富画像（否则「今天天气怎么样」会带出一堆财富指标）。
    """
    if not tool_results:
        return []
    have = {tr.get("name") for tr in tool_results if tr.get("result") is not None}
    baseline: list[dict] = []
    for name in _BASELINE_TOOLS.get(intent, ()):
        if name in have:
            continue
        try:
            result = execute_tool(name, {}, user)
        except ToolError:
            continue
        baseline.append({"name": name, "result": result})
    return baseline + tool_results

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
    "5. 纯金融计算（复利/年化收益率，不涉及具体家庭数据）→ 拒绝，说明这是独立的金融计算，"
    "需要结合家庭数据才有意义。\n"
    "6. 旧判断失效重判：当【记忆】里出现「上次判断已失效」时，先指出发生了什么变化"
    "（基于系统给出的失效原因，数字由系统提供、你只复述不计算），说明为什么旧判断"
    "不能直接沿用，再基于当前数据重新评估。绝不机械复述旧结论，也绝不自行判断"
    "「是否失效」——失效与否由系统确定性标记，你只负责解释变化并重新判断。\n"
    "7. VIP 边界：当 run_scenario / compare_scenarios 返回 forbidden（VIP 专属）时，"
    "绝不编造情景数字，也绝不冷冰冰说「该功能需要升级」。先用你已有的免费数据"
    "（overview / cashflow / issues）给出方向性的基础判断（定性、不写具体数值），"
    "再说明完整的情景模拟是 VIP 能力、能补充什么。系统会另外注入「进一步分析」"
    "说明，你只负责把基础判断说清楚、说人话。\n"
    "最终用自然语言完整回答（结论 + 为什么 + 证据链 + 权衡 + 建议 + 下一步），"
    "不要输出 JSON——结构化输出由系统单独完成，你只管把话说清楚、说人话。"
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


_ADVISOR_STRUCTURE_SYSTEM = (
    "你是家庭财富顾问回答的结构化压缩器。\n"
    "输入：用户问题 + 顾问的一段自然语言回答。\n"
    "任务：把这段回答转成规定的 JSON 结构，不改变原意、不新增原文没有的判断。\n"
    "铁律：\n"
    "1. 绝不计算、绝不编造任何数字。summary/finding/recommendations/next_actions/"
    "tradeoffs/missing 全部写定性文字，禁止出现任何数字。\n"
    "2. 需要引用具体数值时，只在 evidence 里用 metric_key 引用"
    "（合法 key 见 schema enum），数值由系统注入，不要写进文字里。\n"
    "3. missing 只在原文明确「信息不足、无法给出结论、需要用户补充信息才能判断」时输出，"
    "内容是「缺什么信息」。原文若已给出明确诊断，末尾建议「核实/补充数据」属于 next_actions，"
    "不是 missing，不要混。\n"
    "4. refuse 仅在原文明确「拒绝独立金融计算」（复利/年化/单利这类与家庭数据无关的纯计算）"
    "时才置 true；诊断出负面结果、风险、缺口、亏损都只是正常结论，绝不设 refuse。\n"
    "5. 不确定时用 uncertainty 表达，confidence 只能 high/medium/low。"
)


_ADVISOR_STRUCTURE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "finding": {"type": ["string", "null"]},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "metric_key": {"type": "string", "enum": list(EVIDENCE_METRIC_KEYS)},
                },
                "required": ["claim", "metric_key"],
            },
        },
        "tradeoffs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "option": {"type": "string"},
                    "gain": {"type": "string"},
                    "loss": {"type": "string"},
                },
                "required": ["option", "gain", "loss"],
            },
        },
        "uncertainty": {
            "type": ["object", "null"],
            "properties": {
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "missing": {"type": "array", "items": {"type": "string"}},
                "alternatives": {"type": "array", "items": {"type": "string"}},
            },
        },
        "recommendations": {"type": "array", "items": {"type": "string"}},
        "next_actions": {"type": "array", "items": {"type": "string"}},
        "missing": {"type": "array", "items": {"type": "string"}},
        "refuse": {"type": "boolean"},
    },
    "required": ["summary"],
}


def _structure_advisor_answer(llm: LLMProvider, prose: str | None,
                              message: str) -> dict | None:
    """两阶段结构输出：把工具循环产出的散文压成规定 JSON（强制 json_object）。

    结构由 complete_json（response_format=json_object）保证合法 JSON；数字不在此
    产生，只写定性 + metric_key 引用，下游 assemble 确定性注入数值。
    """
    user_prompt = (
        f"【用户问题】\n{message}\n\n"
        f"【顾问的自然语言回答】\n{prose or '（无）'}"
    )
    data = llm.complete_json(_ADVISOR_STRUCTURE_SYSTEM, user_prompt,
                             _ADVISOR_STRUCTURE_SCHEMA)
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
    tool_results = _with_baseline(raw.get("tool_results") or [], intent, user)
    llm_json = _structure_advisor_answer(llm, raw.get("content"), message)
    if llm_json is None:
        # structure 阶段失败但 tool_loop 已产出散文 → 用散文兜底（回答可用性），不整体降级。
        # prose 只是「回答可用性兜底」，非确定性事实来源：metrics/priorities/evidence 仍从
        # tool_results 确定性取，数字仍由 _strip_numeric_text 处理，source/status 绝不从 prose 猜。
        # 只有 chat 彻底无产出（content 空）才降级 None → 上层确定性兜底。
        prose = raw.get("content")
        if not prose:
            return None
        llm_json = {"summary": prose}

    if llm_json.get("refuse"):
        return _attach_vip_boundary(
            assemble_advisor_response(tool_results, llm_json, intent, status="refused"),
            user, intent)

    missing = llm_json.get("missing")
    if missing and isinstance(missing, list) and missing:
        # 只有顾问「没产出任何有效证据」时才判信息不足 → need_clarification。
        # 已基于数据诊断（evidence 非空）时的 missing 是「诊断后追问细节」，保持 ok，
        # 追问内容经 uncertainty.missing 呈现，绝不丢弃已做好的诊断结论。
        resp = assemble_advisor_response(tool_results, llm_json, intent, status="ok")
        if not resp.evidence:
            # 数字防编造闸：missing 是 LLM 定性文字，含数字的项 strip 掉（数字只来自
            # metrics），否则拼接进 summary 会违反「数字无编造」铁律。
            clean_missing = [m for m in missing
                             if isinstance(m, str) and _strip_numeric_text(m) is not None]
            clarify = _CLARIFY_PREFIX + "、".join(clean_missing)
            return resp.model_copy(update={"summary": clarify, "status": "need_clarification"})
        record_judgment(user, resp)
        return _attach_vip_boundary(resp, user, intent)

    resp = assemble_advisor_response(tool_results, llm_json, intent, status="ok")
    record_judgment(user, resp)
    return _attach_vip_boundary(resp, user, intent)


def _attach_vip_boundary(resp: AgentResponse, user: dict, intent: str) -> AgentResponse:
    """P2-A：Free 触发情景模拟但未执行（无 scenario_comparison）→ 注入确定性「进一步分析」边界。

    仅当情景确实被 VIP 门挡住（意图为 SCENARIO_COMPARE、Free 用户、无对比结果）才注入；
    VIP 用户或已产出对比结果时绝不注入（避免误标）。边界文字全定性、无数字。
    """
    if (intent == "SCENARIO_COMPARE" and user.get("tier") != "vip"
            and resp.scenario_comparison is None and not resp.vip_boundary):
        resp = resp.model_copy(update={"vip_boundary": VIP_BOUNDARY})
    return resp
