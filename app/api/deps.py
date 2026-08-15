"""共享鉴权依赖：get_current_user + require_vip。

从 main.py 抽出，供 /api/wealth/* 路由与旧路由共同使用（避免循环 import）。
"""
from __future__ import annotations

from fastapi import Header, HTTPException

from .. import db

__all__ = ["get_current_user", "require_vip"]


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """从 Authorization: Bearer <token> 解析当前登录用户。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    user = db.get_user_by_token(authorization[7:])
    if user is None:
        raise HTTPException(401, "登录已失效，请重新登录")
    return user


def require_vip(user: dict, scope: str = "vip") -> None:
    """VIP 门：Free 用户触发 → 埋 vip_boundary_hit 后 403（scope 标记触发了哪个能力）。"""
    if user.get("tier") != "vip":
        db.record_event(user["family_id"], "vip_boundary_hit", meta={"scope": scope})
        raise HTTPException(403, "深度报告和决策模拟是 VIP 专属功能，升级后即可使用")
