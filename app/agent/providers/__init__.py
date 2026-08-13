"""A3.2 Provider 工厂：按配置返回 LLMProvider 实现，未配置/失败则安全降级 NullProvider。

铁律：
- 只有 deepseek.py 可以 import HTTP/SDK；核心 Runtime 层绝不 import。
- 模型名从 LLM_MODEL 读，不冻结具体型号。
- LLM_PROVIDER != deepseek，或缺 key / 缺 model → NullProvider（安全降级，绝不猜）。
"""
from __future__ import annotations

import os

from ..provider import LLMProvider, NullProvider
from .deepseek import DEFAULT_BASE_URL, DeepSeekProvider

__all__ = ["DeepSeekProvider", "get_provider"]


def get_provider() -> LLMProvider:
    """返回可用 Provider。这是「换模型不换财富系统」的唯一切换点。

    - LLM_PROVIDER 非 deepseek → NullProvider
    - 缺 LLM_API_KEY / LLM_MODEL → NullProvider
    - 否则 → DeepSeekProvider（base_url 来自 LLM_BASE_URL）
    """
    provider_name = (os.getenv("LLM_PROVIDER") or "deepseek").strip().lower()
    if provider_name != "deepseek":
        return NullProvider()

    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL")
    if not api_key or not model:
        return NullProvider()

    base_url = os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL
    return DeepSeekProvider(api_key=api_key, model=model, base_url=base_url)
