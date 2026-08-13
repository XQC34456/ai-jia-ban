"""AI Agent 层：交互智能层（A2 起），把用户意图接到财富服务层。

分层铁律：Tool = 获取事实，Decision = 判断，LLM = 理解 + 解释。
本层不包含任何财富计算逻辑，绝不自行计算 Wealth Score / RFR / NWC / DTI。
"""
from .tools import (
    ToolError, resolve_scenario_name,
    get_overview, get_issues, get_goals, compare_scenario,
)
from .provider import LLMProvider, NullProvider, FakeLLMProvider
from .router import refusal_gate, route_intent
from .params import PARAM_LABELS, ParamResult, extract_scenario_params
from .dispatch import INTENT_TOOL, dispatch
from .errors import map_tool_error
from .response import build_metrics, known_limitations_of, build_response
from .runtime import handle
from .entry import converse
from .providers import DeepSeekProvider, get_provider

__all__ = [
    "ToolError", "resolve_scenario_name",
    "get_overview", "get_issues", "get_goals", "compare_scenario",
    "LLMProvider", "NullProvider", "FakeLLMProvider",
    "refusal_gate", "route_intent",
    "PARAM_LABELS", "ParamResult", "extract_scenario_params",
    "INTENT_TOOL", "dispatch",
    "map_tool_error",
    "build_metrics", "known_limitations_of", "build_response",
    "handle",
    "converse",
    "DeepSeekProvider", "get_provider",
]
