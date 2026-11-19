"""视觉定位：用语义找到屏幕上的目标元素。

比如“找到结账按钮”——不靠写死的坐标，靠 VLM 理解屏幕。
真实实现是 VisionGrounding：把截图发给视觉模型拿回坐标，
再对到无障碍树里最近的可点元素。MockGrounding 只按文字匹配，
没配 key 的演示时用。
"""
from __future__ import annotations

import json
from typing import Callable, Protocol

from ..llm.client import OpenAICompatibleClient
from ..phone.accessibility import Screen, UIElement


class VLMGrounding(Protocol):
    def locate(
        self,
        screen: Screen,
        description: str,
        screenshot: bytes | None = None,
    ) -> UIElement | None:
        """在当前屏幕上按语义描述定位一个元素，找不到返回 None。"""
        ...


class MockGrounding:
    """演示用：按文字 / 描述子串匹配，不看图。"""

    def locate(
        self,
        screen: Screen,
        description: str,
        screenshot: bytes | None = None,
    ) -> UIElement | None:
        return screen.find(description)


class VLMLocator:
    """注入定位函数的定位器：调用方自己决定怎么看图。"""

    def __init__(self, locate_fn: Callable):
        self._locate_fn = locate_fn

    def locate(
        self,
        screen: Screen,
        description: str,
        screenshot: bytes | None = None,
    ) -> UIElement | None:
        return self._locate_fn(screen, description, screenshot)


def nearest_element(screen: Screen, px: float, py: float) -> UIElement | None:
    """找离像素点 (px, py) 最近的可点元素，太远了就返回 None。"""
    best: UIElement | None = None
    best_dist = float("inf")
    for el in screen.elements:
        if not el.clickable:
            continue
        x, y, w, h = el.bounds
        cx, cy = x + w / 2, y + h / 2
        dist = (cx - px) ** 2 + (cy - py) ** 2
        if dist < best_dist:
            best, best_dist = el, dist
    if best is None or best_dist > 250**2:
        return None
    return best


class VisionGrounding:
    """真实 VLM 定位：截图 + 描述发给视觉模型，拿回 0-1000 坐标。

    坐标是相对值，要按屏幕实际宽高换算成像素，
    再对到无障碍树里最近的可点元素——模型指个大概位置就行，
    最后点下去的是真实元素，不是凭空算出来的点。
    """

    PROMPT = (
        "在这张手机截图里找到：{description}。"
        "只输出 JSON，例如 {{\"x\": 540, \"y\": 960}}，x、y 是 0-1000 的相对坐标。"
        "找不到就输出 {{\"x\": -1, \"y\": -1}}。"
    )

    def __init__(self, client: OpenAICompatibleClient):
        self._client = client

    def locate(
        self,
        screen: Screen,
        description: str,
        screenshot: bytes | None = None,
    ) -> UIElement | None:
        if not screenshot:
            return None  # 没有截图就没法看图，交给调用方 fallback
        raw = self._client.chat_with_image(
            self.PROMPT.format(description=description),
            screenshot,
            response_format="json_object",
        )
        point = json.loads(raw)
        x, y = point.get("x", -1), point.get("y", -1)
        if x < 0 or y < 0:
            return None
        return nearest_element(screen, x / 1000 * screen.width, y / 1000 * screen.height)
