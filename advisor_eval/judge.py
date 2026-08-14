"""LLM 独立裁判：对「顾问感」主观维度打分（1-3），并要求原文证据。

铁律类（数字/source/status/内部标识）不在此判——由 rubric.run_iron_rules 确定性判定。
裁判只看对话原文，不接触家庭数据、不接触工具结果，避免「既当运动员又当裁判」。
"""
from __future__ import annotations

from app.agent.providers import get_provider

from .scripts import DIMENSIONS

__all__ = ["judge_advisor_feel", "JUDGE_SCHEMA"]

_JUDGE_SYSTEM = (
    "你是独立的评测裁判，负责给一个 AI 家庭财富顾问的「顾问感」打分。\n"
    "你只看对话原文，不接触家庭数据、不接触工具内部结果。\n"
    "打分规则：\n"
    "1. 每个分项打 1-3 分：1=不合格（像问答机器人/答非所问），2=及格（有顾问意识但不完整），"
    "3=好（像真人顾问）。\n"
    "2. 每个分项分数必须配 reason（为什么给这个分）。\n"
    "3. evidence 必须从对话原文逐字摘录（speaker 标 user/assistant），"
    "证明你的判断，不允许空口评分。\n"
    "4. 铁律类（数字对不对、source 对不对）不是你的职责，不要据此打分。\n"
    "5. overall 取分项均值（保留一位小数）。\n"
)

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "dimensions": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 1, "maximum": 3},
                    "reason": {"type": "string"},
                },
                "required": ["score", "reason"],
            },
        },
        "overall": {"type": "number", "minimum": 1, "maximum": 3},
        "reason": {"type": "string"},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string", "enum": ["user", "assistant"]},
                    "quote": {"type": "string"},
                },
                "required": ["speaker", "quote"],
            },
        },
    },
    "required": ["dimensions", "overall", "reason", "evidence"],
}


def judge_advisor_feel(script: dict, transcript: str,
                       llm=None) -> dict | None:
    """对单个观察点的顾问感打分。llm 缺省时用独立 provider（无状态 complete_json）。"""
    llm = llm or get_provider()
    dims = script.get("dimensions") or list(DIMENSIONS.keys())
    dim_desc = "\n".join(f"- {d}：{DIMENSIONS[d]}" for d in dims)
    user_prompt = (
        f"【观察点】{script['title']}\n"
        f"【核心问题】{script.get('judge_question', '')}\n"
        f"【适用分项】\n{dim_desc}\n\n"
        f"【对话原文】\n{transcript}\n\n"
        f"请只对上述分项打分（1-3），并给出 reason 和逐字 evidence。"
    )
    data = llm.complete_json(_JUDGE_SYSTEM, user_prompt, JUDGE_SCHEMA)
    return data if isinstance(data, dict) else None
