"""OpenAI 兼容的 HTTP 客户端：只用标准库，不引入新依赖。

OpenAI、DeepSeek 以及其他 OpenAI 兼容服务都能用，
改 base_url 和 key 就行。key 从环境变量读，不写进代码和配置。
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request


class OpenAICompatibleClient:
    """最小的 chat completions 客户端：文本 + 看图都走它。"""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: int = 60,
    ):
        self.api_key = api_key or os.environ.get(api_key_env, "")
        if not self.api_key:
            raise RuntimeError(
                f"没有找到 API key：请设置环境变量 {api_key_env}，"
                "或把 key 传给 OpenAICompatibleClient(api_key=...)"
            )
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(
        self,
        messages: list[dict],
        *,
        response_format: str | None = None,
    ) -> str:
        """发一次 chat 请求，返回助手消息的文本内容。"""
        body: dict = {"model": self.model, "messages": messages}
        if response_format == "json_object":
            body["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")
            raise RuntimeError(
                f"LLM 请求失败（HTTP {exc.code}）：{detail[:300]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM 请求网络错误：{exc}") from exc
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"LLM 返回格式看不懂：{str(payload)[:300]}") from exc

    def chat_with_image(
        self,
        text: str,
        image_png: bytes,
        *,
        response_format: str | None = None,
    ) -> str:
        """带一张图的 chat 请求：截图 base64 后发给视觉模型。"""
        b64 = base64.b64encode(image_png).decode("ascii")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ]
        return self.chat(messages, response_format=response_format)
