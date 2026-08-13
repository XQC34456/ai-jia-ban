"""家庭数据输入 Schema：定义 Wealth Engine 消费的家庭数据形状。

注意：这是「文档化 + 校验」用途的宽松模型——engine 与 db 内部仍用 dict，
本模型只在 API 边界把 db.dump_family 的结果结构化、并对外统一形状。
子实体用宽松 dict（extra 忽略），避免对既有数据的严格校验导致运行期崩溃。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = ["FamilyData"]


class FamilyData(BaseModel):
    """家庭完整数据快照（与 db.dump_family 返回结构一致）。

    assets/liabilities/cashflows/goals/persons/insurance 均为 dict 列表，
    每个 dict 的字段见 engine 各模块 docstring；此处不逐字段强校验，
    保持 engine 的容错语义（缺字段用默认值）。
    """
    model_config = ConfigDict(extra="ignore")

    family: dict | None = None
    persons: list[dict] = []
    assets: list[dict] = []
    liabilities: list[dict] = []
    cashflows: list[dict] = []
    goals: list[dict] = []
    reminders: list[dict] = []
    insurance: list[dict] = []
    family_profile: dict | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "FamilyData":
        """从 db.dump_family 的 dict 构造；缺失/None 键按字段默认值补齐。"""
        return cls(**{k: v for k, v in data.items() if v is not None and k in cls.model_fields})
