"""LLM Provider 抽象：A3 Runtime 只认这个协议，绝不 import 具体模型 SDK。

铁律：核心层只冻结 `class LLMProvider(Protocol)`，具体接哪个模型在 A3.2 通过配置注入，
绝不 `from <vendor> import ...` 进入本文件。
"""
from __future__ import annotations

import json
from typing import Protocol

__all__ = ["LLMProvider", "NullProvider", "FakeLLMProvider"]


class LLMProvider(Protocol):
    """一次受 JSON-schema 约束的结构化补全；失败/超时返回 None。"""

    def complete_json(self, system: str, user: str, schema: dict,
                      context: str | None = None) -> dict | None:
        ...

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict | None:
        """真实 function calling 多轮对话；失败/超时返回 None。

        返回 {"content": str | None, "tool_calls": [{"id", "name", "arguments"}]}
        或 None（失败降级）。
        """
        ...


class NullProvider:
    """永远返回 None → Runtime 走纯确定性回退，不产生任何 LLM 内容。"""

    def complete_json(self, system: str, user: str, schema: dict,
                      context: str | None = None) -> dict | None:
        return None

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict | None:
        return None


class FakeLLMProvider:
    """按脚本顺序返回预置结构化输出；脚本耗尽返回 None（测试专用）。

    三条独立队列，对应真实场景里互不干扰的调用：
    - router_script 驱动意图路由（route_intent 的 complete_json，schema 含 intent）。
    - script 驱动结构化输出（advisor 两阶段 / 情景参数抽取）。
    - chat_script 驱动 function calling 对话（chat，元素为 chat 返回 dict）。
    chat_messages 记录每次 chat 的 messages，供测试断言工具结果是否回传。
    """

    def __init__(self, script: list | None = None,
                 chat_script: list | None = None,
                 router_script: list | None = None):
        self._script = list(script or [])
        self._chat_script = list(chat_script or [])
        self._router_script = list(router_script or [])
        self.last_context: str | None = None
        self.chat_messages: list[list[dict]] = []

    def complete_json(self, system: str, user: str, schema: dict,
                      context: str | None = None) -> dict | None:
        self.last_context = context
        props = schema.get("properties") or {}
        queue = self._router_script if "intent" in props else self._script
        if not queue:
            return None
        item = queue.pop(0)
        if isinstance(item, str):          # 允许脚本直接写 JSON 字符串，简化两阶段测试
            try:
                return json.loads(item)
            except json.JSONDecodeError:
                return None
        return item

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict | None:
        self.chat_messages.append(list(messages))
        if not self._chat_script:
            return None
        return self._chat_script.pop(0)
