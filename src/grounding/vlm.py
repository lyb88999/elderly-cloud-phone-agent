"""视觉定位：用语义找到屏幕上的目标元素。

比如“找到结账按钮”——不靠写死的坐标，靠 VLM 理解屏幕。
MockGrounding 按文字 / 描述匹配；真实实现把截图 + 描述发给 VLM。
"""
from __future__ import annotations

from typing import Callable, Protocol

from ..phone.accessibility import Screen, UIElement


class VLMGrounding(Protocol):
    def locate(self, screen: Screen, description: str) -> UIElement | None:
        """在当前屏幕上按语义描述定位一个元素，找不到返回 None。"""
        ...


class MockGrounding:
    """演示用：按文字 / 描述子串匹配。"""

    def locate(self, screen: Screen, description: str) -> UIElement | None:
        return screen.find(description)


class VLMLocator:
    """真实 VLM 定位：调用方注入一个能看图的定位函数。

    locate_fn(screen, description) -> UIElement | None，
    内部实现一般是：把屏幕截图 + 描述发给视觉模型，
    拿到坐标后再和无障碍树里的元素对齐，返回最接近的那个。
    """

    def __init__(self, locate_fn: Callable[[Screen, str], UIElement | None]):
        self._locate_fn = locate_fn

    def locate(self, screen: Screen, description: str) -> UIElement | None:
        return self._locate_fn(screen, description)
