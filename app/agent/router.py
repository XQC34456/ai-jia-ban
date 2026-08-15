"""A3 Intent Router：拒算门（优先）→ 确定性关键词 → LLM 兜底 → Literal 七意图校验 → 兜底。

优先级（A3.1 冻结，不可调换）：
    拒算门 ↓ 确定性场景/意图关键词 ↓ LLM 结构化兜底 ↓ Literal 七意图校验 ↓ 仍失败 → VIEW_OVERVIEW

本模块只做「识别」，不做任何财富计算，也不产出数字。
"""
from __future__ import annotations

from ..schemas.agent import AGENT_INTENTS
from .provider import LLMProvider

__all__ = ["refusal_gate", "route_intent"]

_ROUTER_SYSTEM = (
    "你是财富顾问的意图路由器。只判断用户消息属于以下七类意图之一，输出 JSON "
    "{\"intent\": \"<其中一个>\"}，禁止输出七类之外的值。七类：VIEW_OVERVIEW / "
    "CHECK_ISSUES / CHECK_RETIREMENT / CHECK_ALLOCATION / CHECK_GOALS / "
    "SCENARIO_COMPARE / EXPLAIN_RESULT。"
)

# 确定性意图关键词（顺序即优先级：场景 > 问题 > 退休 > 配置 > 目标 > 解释）。
_INTENT_KEYWORDS = (
    ("SCENARIO_COMPARE", ("买房", "购房", "买套", "提前还", "还贷", "投资", "投入", "买入",
                          "收入下降", "降薪", "涨薪", "加薪")),
    ("CHECK_ISSUES", ("问题", "风险", "告警", "隐患", "失业", "撑多久")),
    ("CHECK_RETIREMENT", ("退休", "养老", "养老金", "RFR", "NWC")),
    ("CHECK_ALLOCATION", ("配置", "资产占比", "集中度", "持仓", "分散", "资产分配", "怎么投")),
    ("CHECK_GOALS", ("目标", "教育金", "上学", "攒钱", "计划")),
    ("EXPLAIN_RESULT", ("为什么", "解释", "说明", "原因")),
)

# 测算类信号词：命中则拒算门优先于普通意图路由。
_COMPUTE_WORDS = ("算", "复利", "年化", "收益", "利息", "测算", "回报", "涨到", "增值")
# 纯金融计算器信号（无家庭上下文）→ 直接拒绝，不自算。
_PURE_CALC_WORDS = ("复利", "年化", "单利", "本金")


def refusal_gate(message: str) -> dict | None:
    """拒算门：命中测算关键词时优先于普通意图路由。

    返回：
    - None                 → 非测算请求，走普通路由
    - {"scenario": "invest"} → 可表达为投资情景，转 SCENARIO_COMPARE（缺参数再追问）
    - {"disambiguate": True} → 纯金融计算词（复利/年化/单利/本金），交 LLM 消歧
      （知识问答 / 纯计算拒绝 / 家庭影响走 scenario），不直接 refuse
    """
    if not any(w in message for w in _COMPUTE_WORDS):
        return None
    if any(w in message for w in _PURE_CALC_WORDS):
        return {"disambiguate": True}
    return {"scenario": "invest"}


def route_intent(message: str, llm: LLMProvider | None = None,
                 wealth_context: str | None = None,
                 memory_context: str | None = None,
                 intent_hint: str | None = None) -> str:
    """确定性关键词 → 页面 intent_hint（SEED）→ LLM 兜底 → Literal 校验 → 兜底 Overview。

    Phase 1b：intent_hint（页面建议意图）只作 SEED，不是 OVERRIDE——关键词强路由
    （用户当前 query）永远优先；hint 仅在 query 未命中关键词时、于 LLM 兜底之前生效，
    帮 Advisor 缩小搜索空间，不压用户最新问题（设计 §3 优先级）。

    wealth_context 仅在 LLM 兜底注入（关键词命中的确定性路径不注入；意图分类输出
    是枚举、非数字，注入背景可消歧、无编造风险）。memory_context（近期对话）同样
    仅在 LLM 兜底注入，用于消解「这笔钱/这个/那」这类指代。
    """
    for intent, words in _INTENT_KEYWORDS:
        if any(w in message for w in words):
            return intent
    if intent_hint in AGENT_INTENTS:
        return intent_hint
    if llm is not None:
        user_prompt = message
        if memory_context:
            user_prompt = f"{message}\n\n【对话历史（用于消解指代）】\n{memory_context}"
        raw = llm.complete_json(
            system=_ROUTER_SYSTEM,
            user=user_prompt,
            schema={"type": "object",
                    "properties": {"intent": {"type": "string", "enum": list(AGENT_INTENTS)}},
                    "required": ["intent"]},
            context=wealth_context,
        )
        if raw and raw.get("intent") in AGENT_INTENTS:
            return raw["intent"]
    return "VIEW_OVERVIEW"
