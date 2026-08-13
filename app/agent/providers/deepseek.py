"""A3.2 DeepSeek Provider：唯一允许 import HTTP 的 Agent 文件。

铁律：
- 本文件是 HTTP/SDK 的唯一落点，核心 Runtime 层（runtime/router/params/response/
  provider）绝不 import httpx/requests/openai。
- 模型名从构造参数（LLM_MODEL）注入，绝不硬编码具体型号。
- complete_json 只返回「结构化 JSON dict」或 None；超时/HTTP 错误/非 JSON/非对象
  一律返回 None → 上层走确定性兜底，绝不自行猜测。
"""
from __future__ import annotations

import json

import httpx

__all__ = ["DeepSeekProvider", "DEFAULT_BASE_URL"]

DEFAULT_BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider:
    """通过 OpenAI 兼容接口做「结构化 JSON」补全，符合 LLMProvider Protocol。

    complete_json(system, user, schema) -> dict | None
    """

    def __init__(self, api_key: str, model: str, base_url: str = DEFAULT_BASE_URL,
                 timeout: float = 30.0):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout = timeout

    def complete_json(self, system: str, user: str, schema: dict) -> dict | None:
        schema_str = json.dumps(schema, ensure_ascii=False)
        full_system = (
            f"{system}\n\n你必须只输出一个 JSON 对象，严格符合以下 JSON Schema，"
            f"不要输出任何 JSON 之外的文字：\n{schema_str}"
        )
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": full_system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            resp = httpx.post(
                f"{self._base_url.rstrip('/')}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            return data if isinstance(data, dict) else None
        except Exception:
            return None
