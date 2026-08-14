"""冷启动 preview：粗画像档位 → 典型值 → build_overview 实算，绝不写库。

铁律：本接口纯计算，不落库、不接 LLM、不新增财富公式；
      返回的 overview 只是「演示用典型家庭」的实算结果，非用户真实财务数据。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..schemas.onboarding import OnboardingPreviewRequest
from ..services import build_overview
from ..services.onboarding import typical_family
from .deps import get_current_user

__all__ = ["router"]

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.post("/preview")
def onboarding_preview(req: OnboardingPreviewRequest, user: dict = Depends(get_current_user)):
    """按粗画像档位生成「演示画像」+ 1-3 个问题（全部由 build_overview 实算）。"""
    data = typical_family(req.profile.model_dump())
    return {"interests": req.interests, "overview": build_overview(data)}
