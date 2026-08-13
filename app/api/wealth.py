"""Wealth Overview API：家庭财富驾驶舱全量状态 + 问题列表（免费）。

前端只消费 /overview 这一个对象，不自行计算任何财富逻辑。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import db
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
