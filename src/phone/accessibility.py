"""无障碍节点树：描述云手机当前屏幕上的可操作元素。

VLM 负责“语义定位”（比如“找到结账按钮”），
无障碍树负责给出结构化的元素列表，两者互补。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UIElement:
    text: str = ""                    # 元素上显示的文字，如“微信”
    description: str = ""             # 无障碍描述，如“打开微信应用”
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, 宽, 高
    clickable: bool = True
    package: str = ""                 # 所属应用包名


@dataclass
class Screen:
    """当前屏幕快照：元素列表 + 所属应用。"""

    app: str = "桌面"
    elements: list[UIElement] = field(default_factory=list)

    def find(self, keyword: str) -> UIElement | None:
        """按文字或描述模糊找一个元素。"""
        for el in self.elements:
            if keyword in el.text or keyword in el.description:
                return el
        return None
