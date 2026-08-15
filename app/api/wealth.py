"""Wealth Overview API：家庭财富驾驶舱全量状态 + 问题列表（免费）。

前端只消费 /overview 这一个对象，不自行计算任何财富逻辑。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import db
from ..agent.memory import build_review_status
from ..decision import build_issues
from ..schemas.wealth import Overview
from ..services import build_overview
from .deps import get_current_user

__all__ = ["router"]

router = APIRouter(prefix="/api/wealth", tags=["wealth"])


@router.get("/overview", response_model=Overview)
def wealth_overview(user: dict = Depends(get_current_user)):
    """一次性返回家庭财富驾驶舱核心状态（财富评分/净资产/配置/现金流/养老/问题）。"""
    data = db.dump_family(user["family_id"])
    return build_overview(data)


@router.get("/issues")
def wealth_issues(user: dict = Depends(get_current_user)):
    """返回 Decision Layer 的统一财富问题集合（供 AI Agent / 报告 / 提醒独立调用）。"""
    data = db.dump_family(user["family_id"])
    return build_issues(data)


@router.get("/review-status")
def wealth_review_status(user: dict = Depends(get_current_user)):
    """返回最近判断的评估状态 + 失效维度（供驾驶舱「重新评估」横幅）。"""
    return build_review_status(user["family_id"])


class ActionPlanCreate(BaseModel):
    issue_id: str | None = None
    action: str
    detail: str | None = None


class ActionPlanUpdate(BaseModel):
    status: str


@router.get("/action-plan")
def list_action_plan(user: dict = Depends(get_current_user)):
    """返回家庭行动计划列表（采纳的财富建议 + 完成状态）。"""
    return {"plans": db.list_action_plan(user["family_id"])}


@router.post("/action-plan")
def create_action_plan(body: ActionPlanCreate, user: dict = Depends(get_current_user)):
    """采纳一条建议进入行动计划；已存在同 issue+action 的未完成项 → id=None（不重复）。"""
    if not body.action or not body.action.strip():
        raise HTTPException(400, "action 不能为空")
    pid = db.create_action_plan(user["family_id"], body.issue_id, body.action.strip(), body.detail)
    if pid is not None:  # 去重命中（同 issue+action 已有 todo）不重复埋采纳
        db.record_event(user["family_id"], "adopt",
                        meta={"issue_id": body.issue_id, "action": body.action.strip()})
    return {"id": pid}


@router.put("/action-plan/{plan_id}")
def update_action_plan(plan_id: int, body: ActionPlanUpdate,
                       user: dict = Depends(get_current_user)):
    """更新行动计划状态（todo/done/skipped）。"""
    if body.status not in ("todo", "done", "skipped"):
        raise HTTPException(400, "非法状态")
    if db.get_entity_owner("action_plan", plan_id) != user["family_id"]:
        raise HTTPException(404, "计划不存在")
    db.update_action_plan_status(plan_id, body.status)
    if body.status == "done":
        db.record_event(user["family_id"], "action_complete", meta={"plan_id": plan_id})
    return {"ok": True}
