"""深度报告：把家庭数据快照组织成一份结构化财富报告 + LLM 生成建议。

这是 VIP 的核心交付物。报告 = 确定性数据（概览/资产配置/体检/目标） + LLM 生成的
「综合分析与行动建议」章节。LLM 只负责"解读"，绝不计算数字。
"""
from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from . import calc_engine as ce
from . import db
from .health import health_check


def _asset_allocation(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按类型聚合资产，算占比，按金额降序。"""
    groups: dict[str, float] = {}
    total = 0.0
    for a in assets:
        t = a.get("type") or "其他"
        v = float(a.get("value") or 0)
        groups[t] = groups.get(t, 0) + v
        total += v
    if total <= 0:
        return []
    out = [{"type": t, "value": round(v, 2), "pct": round(v / total * 100, 1)}
           for t, v in groups.items()]
    out.sort(key=lambda x: x["value"], reverse=True)
    return out


def build_report(family_id: int) -> dict[str, Any]:
    data = db.dump_family(family_id)
    snap = ce.snapshot(data)
    problems = health_check(data)

    members = [{
        "name": p.get("name"),
        "relation": p.get("relation"),
        "age": (date.today().year - int(p["birth_year"])) if p.get("birth_year") else None,
    } for p in data["persons"]]

    return {
        "family_name": (data["family"] or {}).get("name", "我的家庭"),
        "generated_at": date.today().isoformat(),
        "members": members,
        "snapshot": snap,
        "asset_allocation": _asset_allocation(data["assets"]),
        "problems": problems,
        "advice": _llm_advice(snap, problems),
    }


def _template_advice(snap: dict[str, Any], problems: list[dict[str, Any]]) -> str:
    """无 LLM 时的兜底建议：用结构化数据拼一份有依据的分析。"""
    sm = snap["safety_margin"]
    lines = ["## 家庭现状总评", f"家庭安全边际 {sm['score']} 分（{sm['level']}）。"]
    if snap["monthly_income"]:
        lines.append(
            f"月收入 {snap['monthly_income']:,.0f} 元，月支出 {snap['monthly_expense']:,.0f} 元，"
            f"月结余 {snap['monthly_surplus']:,.0f} 元。"
        )
    lines.append("## 行动建议")
    if problems:
        for p in problems:
            lines.append(f"- {p['title']}：{p['advice']}")
    else:
        lines.append("- 保持当前稳健状态，持续积累。")
    return "\n".join(lines)


def _llm_advice(snap: dict[str, Any], problems: list[dict[str, Any]]) -> str:
    """有 LLM 时，用家庭数据 + 体检结果生成个性化建议章节（markdown）。"""
    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        return _template_advice(snap, problems)

    import httpx

    base = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
    model = os.environ.get("LLM_MODEL", "deepseek-chat")

    context = json.dumps({"snapshot": snap, "problems": problems}, ensure_ascii=False)
    system = (
        "你是专业的家庭财富顾问。请基于给定的家庭财务数据，撰写「综合分析与行动建议」章节。"
        "严格用 markdown 输出，只包含两个部分："
        "「## 家庭现状总评」写一段话总评家庭财务状况；"
        "「## 行动建议」列 3~5 条具体建议，每条以「- 」开头，按优先级排序。"
        "只基于数据作答，不编造数字，不推荐具体金融产品，不构成投资建议。"
    )
    try:
        resp = httpx.post(
            f"{base.rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"家庭数据：{context}"},
                ],
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return _template_advice(snap, problems)
