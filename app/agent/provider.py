"""LLM Provider 抽象：A3 Runtime 只认这个协议，绝不 import 具体模型 SDK。

铁律：核心层只冻结 `class LLMProvider(Protocol)`，具体接哪个模型在 A3.2 通过配置注入，
绝不 `from <vendor> import ...` 进入本文件。
"""
from __future__ import annotations

from typing import Protocol

__all__ = ["LLMProvider", "NullProvider", "FakeLLMProvider"]


class LLMProvider(Protocol):
    """一次受 JSON-schema 约束的结构化补全；失败/超时返回 None。"""

    def complete_json(self, system: str, user: str, schema: dict) -> dict | None:
        ...


class NullProvider:
    """永远返回 None → Runtime 走纯确定性回退，不产生任何 LLM 内容。"""

    def complete_json(self, system: str, user: str, schema: dict) -> dict | None:
        return None


class FakeLLMProvider:
    """按脚本顺序返回预置结构化输出；脚本耗尽返回 None（测试专用）。"""

    def __init__(self, script: list[dict] | None = None):
        self._script = list(script or [])

    def complete_json(self, system: str, user: str, schema: dict) -> dict | None:
        if not self._script:
            return None
        return self._script.pop(0)
