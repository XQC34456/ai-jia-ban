"""问题优先级：severity 排序（P0 > P1 > P2）。

severity 业务语义（P0/P1/P2 的统一定义，全契约一致）：
- P0 = 若不处理将立即/近期危害财富安全（负现金流、应急金<3 月、DTI>0.5、退休流动资金不足）
- P1 = 影响长期目标达成（储蓄率<20%、应急金<6 月、DTI>0.3、配置适配度<60、目标超支、高杠杆资产结构）
- P2 = 优化项（现金闲置、目标缺口）——不紧急但建议行动
"""
from __future__ import annotations

__all__ = ["SEVERITY_ORDER", "SEVERITY_SEMANTICS", "rank"]

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}

SEVERITY_SEMANTICS = {
    "P0": "若不处理将立即/近期危害财富安全",
    "P1": "影响长期目标达成",
    "P2": "优化项——不紧急但建议行动",
}


def rank(issues: list[dict]) -> list[dict]:
    """按 severity（P0→P2）排序；同级保持检测顺序稳定。"""
    return sorted(issues, key=lambda i: SEVERITY_ORDER.get(i.get("severity", "P2"), 9))
