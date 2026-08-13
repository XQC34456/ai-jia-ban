"""Goal Engine API（免费）：统一目标对象列表。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import db
from ..services import build_goals
from .deps import get_current_user

__all__ = ["router"]

router = APIRouter(prefix="/api/wealth", tags=["goals"])


@router.get("/goals")
def goals_endpoint(user: dict = Depends(get_current_user)):
    """返回家庭所有目标的统一测算（金额/日期/资金/缺口/覆盖度/优先级）。"""
    data = db.dump_family(user["family_id"])
    return {"goals": build_goals(data)}
