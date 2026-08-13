"""Agent Chat API：把 AI 顾问统一入口 converse() 挂到 POST /api/agent/chat。

铁律（A4 冻结）：
- API 层不得修改返回结果：converse() 返回什么就 .model_dump() 序列化什么，不补
  metrics/summary/recommendations、不改 status/intent、不自拼财富数字。
- API 层不得 import 财富计算模块 / HTTP 客户端（数字与 HTTP 都不该出现在 API 层）。
- 认证复用 get_current_user；授权（VIP 门）已内聚在 A2 compare_scenario，端点不重复判断。
- Provider 由 get_provider() 注入（换模型不换财富系统）；缺 key → NullProvider → 确定性兜底，不 500。

converse() 返回 ConfirmCard（建档确认）或 AgentResponse（七意图），两者都有 model_dump()。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..agent import converse, get_provider
from ..schemas.agent import AgentRequest
from .deps import get_current_user

__all__ = ["router"]

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat")
def agent_chat(body: AgentRequest, user: dict = Depends(get_current_user)):
    """自然语言 → AI 顾问（建档优先，否则七意图）→ 财富引擎 → 结构化结果。"""
    result = converse(body.message, user, llm=get_provider(), context=body.context)
    return result.model_dump()
