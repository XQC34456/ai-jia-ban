"""Decision Layer · 财富问题组装：检测 → 排序 → 统一输出。"""
from __future__ import annotations

from .context import compute_context
from .detect import DETECTORS
from .priority import rank

__all__ = ["build_issues", "build_problems", "compute_context"]


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

    # 组装阶段统一补齐建议字段：recommendation_id / priority（继承 issue）/ current（继承 issue.metric）
    for i in issues:
        for idx, rec in enumerate(i.get("recommendations", []), start=1):
            rec["recommendation_id"] = f"{i['issue_id']}-R{idx}"
            rec["priority"] = i["severity"]
            if not rec.get("current"):
                rec["current"] = dict(i.get("metric", {}))

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


_SEVERITY_MAP = {"P0": 5, "P1": 3, "P2": 2}


def build_problems(family_data: dict, ctx: dict | None = None) -> list[dict]:
    """兼容旧 /api/family、/api/report 的扁平问题列表（纯 shape 映射）。

    只做转换：P0/P1/P2 → 5/3/2、finding → why、recommendations[0].detail → advice。
    绝不新增/删减问题、不重算 severity、不重新生成建议——财富判断的唯一真相是
    build_issues，这里只是给 report/family 的呈现层拍平。
    """
    result = build_issues(family_data, ctx)
    problems: list[dict] = []
    for i in result["issues"]:
        recs = i.get("recommendations") or []
        advice = recs[0]["detail"] if recs else i.get("finding", "")
        problems.append({
            "severity": _SEVERITY_MAP.get(i.get("severity"), 2),
            "title": i["title"],
            "why": i.get("finding", ""),
            "advice": advice,
        })
    return problems
