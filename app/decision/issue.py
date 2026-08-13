"""Decision Layer · 财富问题组装：检测 → 排序 → 统一输出。"""
from __future__ import annotations

from .context import compute_context
from .detect import DETECTORS
from .priority import rank

__all__ = ["build_issues", "compute_context"]


def build_issues(family_data: dict, ctx: dict | None = None) -> dict:
    """跑 7 类检测器，返回统一财富问题集合。

    返回 {issues, alerts, priorities, recommendations}：
    - issues:          按 P0→P2 排序的完整 Issue 列表
    - alerts:          问题标题短串（供驾驶舱告警条）
    - priorities:      按优先级排序的问题摘要（issue_id/type/severity/title）
    - recommendations: 所有问题的动作化建议（去重按序合并）
    """
    ctx = ctx or compute_context(family_data)
    issues = [det(family_data, ctx) for det in DETECTORS]
    issues = rank([i for i in issues if i is not None])

    alerts = [i["title"] for i in issues]
    priorities = [{"issue_id": i["issue_id"], "type": i["type"],
                   "severity": i["severity"], "title": i["title"]} for i in issues]

    seen: set[str] = set()
    recommendations: list[dict] = []
    for i in issues:
        for rec in i.get("recommendations", []):
            key = rec.get("action", "")
            if key and key not in seen:
                seen.add(key)
                recommendations.append(rec)

    return {
        "issues": issues,
        "alerts": alerts,
        "priorities": priorities,
        "recommendations": recommendations,
    }
