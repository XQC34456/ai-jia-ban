"""Decision Layer：判断层（规则引擎，确定性，零 LLM）。

Engine 算数字，Decision Layer 判问题——把「数字」翻译成「问题 / 原因 / 优先级 / 建议」。
输出统一为财富问题对象（Issue），供 AI Agent / 前端 / 报告 / 提醒共同读取。
"""
from .issue import build_issues, compute_context
from .quadrant import retirement_quadrant

__all__ = ["build_issues", "compute_context", "retirement_quadrant"]
