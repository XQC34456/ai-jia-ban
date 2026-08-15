"""前端产品事件端点：接收后端看不见的「用户动作」埋点（entry / reassess）。

铁律：只接受白名单事件类型（entry / reassess）——后端能确定性捕获的事件
（intent_asked / stale_detected / adopt / action_complete / vip_boundary_hit /
upgrade）绝不开放给前端，防伪造污染漏斗数据。只落库，不参与任何财富计算。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db
from .deps import get_current_user

__all__ = ["router"]

router = APIRouter(prefix="/api", tags=["event"])

# 前端可上报的事件白名单（其余事件后端内部自记，不对外开放）
_FRONTEND_EVENTS = {"entry", "reassess"}


class EventIn(BaseModel):
    event_type: str
    intent: str | None = None
    meta: dict = Field(default_factory=dict)


@router.post("/event")
def record_frontend_event(body: EventIn, user: dict = Depends(get_current_user)):
    """记录一条前端产品事件（白名单：entry / reassess）。"""
    if body.event_type not in _FRONTEND_EVENTS:
        raise HTTPException(400, f"不支持的事件类型: {body.event_type}")
    pid = db.record_event(user["family_id"], body.event_type,
                          intent=body.intent, meta=body.meta or None)
    return {"id": pid}
