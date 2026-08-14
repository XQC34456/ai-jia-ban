"""冷启动 preview 入参模型（不落库，纯计算）。"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ProfileLevel(str, Enum):
    high = "high"
    mid = "mid"
    low = "low"
    unknown = "unknown"


class ProfileLevels(BaseModel):
    assets: ProfileLevel = ProfileLevel.unknown
    income: ProfileLevel = ProfileLevel.unknown
    debt: ProfileLevel = ProfileLevel.unknown
    savings: ProfileLevel = ProfileLevel.unknown


class OnboardingPreviewRequest(BaseModel):
    interests: list[str] = Field(default_factory=list)
    profile: ProfileLevels = Field(default_factory=ProfileLevels)
