"""对话编排层：把「抽取 → 确认 → 落地 → 重算 → 反馈」串起来。

状态机核心：用户说话先抽取，命中建档动作则要求确认（防止 LLM 幻觉污染数据），
确认后才写入数据库并重算；没有动作则当成提问，基于家庭真实数据回答。
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any

from . import calc_engine as ce
from . import db
from .extraction import get_extractor
from .health import health_check

# 待确认动作的内存暂存（MVP 单进程；生产换 Redis/DB）
_PENDING: dict[str, dict[str, Any]] = {}


# ---------- 确认流程 ----------

def handle_message(family_id: int, message: str) -> dict[str, Any]:
    """处理用户消息：返回确认请求或直接回答。"""
    extractor = get_extractor()
    actions = extractor.extract(message)

    if actions:
        pending_id = uuid.uuid4().hex
        _PENDING[pending_id] = {"family_id": family_id, "actions": actions}
        return {
            "type": "confirm",
            "pending_id": pending_id,
            "message": "我理解到以下信息，确认后我就为你建档：",
            "items": [a["summary"] for a in actions],
        }

    return answer_question(family_id, message)


def handle_confirm(family_id: int, pending_id: str, confirmed: bool) -> dict[str, Any]:
    """确认或撤销待定动作。"""
    pending = _PENDING.pop(pending_id, None)
    if pending is None or pending["family_id"] != family_id:
        return {"type": "error", "message": "该确认已失效，请重新输入。"}

    if not confirmed:
        return {"type": "discarded", "message": "好的，已忽略，没有改动你的档案。"}

    for action in pending["actions"]:
        db.apply_action(family_id, action)

    return _build_applied_response(family_id, pending["actions"])


def _build_applied_response(family_id: int, actions: list[dict[str, Any]]) -> dict[str, Any]:
    data = db.dump_family(family_id)
    snap = ce.snapshot(data)
    problems = health_check(data)
    joined = "、".join(a["summary"] for a in actions)
    return {
        "type": "applied",
        "message": f"已记录：{joined}。",
        "snapshot": snap,
        "problems": problems,
    }


# ---------- 提问回答 ----------

_QUESTION_KEYWORDS = ["资产", "结构", "风险", "退休", "买房", "应急", "怎么样", "如何", "能不能", "何时"]


def answer_question(family_id: int, message: str) -> dict[str, Any]:
    data = db.dump_family(family_id)
    snap = ce.snapshot(data)
    problems = health_check(data)

    llm_answer = _llm_answer(family_id, message, data, snap, problems)
    return {
        "type": "answer",
        "message": llm_answer,
        "snapshot": snap,
        "problems": problems,
    }


def _template_answer(snap: dict[str, Any], problems: list[dict[str, Any]]) -> str:
    """无 LLM 时的兜底回答：用结构化数据拼一段有依据的分析。"""
    sm = snap["safety_margin"]
    lines = [
        f"你家目前的家庭安全边际是 {sm['score']} 分（{sm['level']}）。",
    ]
    if snap["monthly_income"]:
        lines.append(
            f"月收入 {snap['monthly_income']:,.0f} 元，月支出 {snap['monthly_expense']:,.0f} 元，"
            f"月结余 {snap['monthly_surplus']:,.0f} 元。"
        )
    if snap["net_worth"]:
        lines.append(
            f"净资产 {snap['net_worth']:,.0f} 元（总资产 {snap['total_assets']:,.0f} - "
            f"总负债 {snap['total_liabilities']:,.0f}）。"
        )
    if snap["emergency_months"] is not None:
        lines.append(f"应急资金可覆盖约 {snap['emergency_months']} 个月的支出。")

    if problems:
        lines.append("\n最值得关注的 3 个问题：")
        for i, p in enumerate(problems, 1):
            lines.append(f"{i}. {p['title']}：{p['why']}")
    else:
        lines.append("\n目前没有发现明显的风险点，继续保持。")

    return "\n".join(lines)


def _llm_answer(
    family_id: int,
    message: str,
    data: dict[str, Any],
    snap: dict[str, Any],
    problems: list[dict[str, Any]],
) -> str:
    """有 LLM 时，用家庭数据 + 体检结果做上下文，生成自然回答。"""
    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        return _template_answer(snap, problems)

    import httpx

    base = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
    model = os.environ.get("LLM_MODEL", "deepseek-chat")

    context = json.dumps({"snapshot": snap, "problems": problems}, ensure_ascii=False)
    system = (
        "你是专业的家庭财富顾问。请基于给定的家庭财务数据回答用户问题，"
        "只基于数据作答，不编造数字，不推荐具体金融产品，不构成投资建议。"
        "回答要简洁、有依据，控制在 200 字以内。"
    )
    try:
        resp = httpx.post(
            f"{base.rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"家庭数据：{context}\n\n用户问题：{message}"},
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return _template_answer(snap, problems)
