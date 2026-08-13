"""Wealth Engine：确定性财富计算引擎（零 LLM 依赖）。

模块划分：metrics（基础指标）/ projection（长期投影）/ allocation（资产配置）/
goals（目标测算）/ score（财富评分）/ scenario（情景模拟）。
"""
from . import metrics, projection, allocation, goals  # noqa: F401
