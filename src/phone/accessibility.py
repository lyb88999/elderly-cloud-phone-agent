"""无障碍节点树：描述云手机当前屏幕上的可操作元素。

VLM 负责“语义定位”（比如“找到结账按钮”），
无障碍树负责给出结构化的元素列表，两者互补。

parse_uiautomator_dump 把真机 `uiautomator dump` 的 XML
解析成 Screen，是 ADBCloudPhone 读屏的真实实现。
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
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
    """当前屏幕快照：元素列表 + 所属应用 + 屏幕尺寸。"""

    app: str = "桌面"
    elements: list[UIElement] = field(default_factory=list)
    width: int = 1080
    height: int = 1920

    def find(self, keyword: str) -> UIElement | None:
        """按文字或描述模糊找一个元素。"""
        for el in self.elements:
            if keyword in el.text or keyword in el.description:
                return el
        return None


_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def parse_uiautomator_dump(
    xml_text: str, size: tuple[int, int] = (1080, 1920)
) -> Screen:
    """把 `uiautomator dump` 的 XML 解析成 Screen。

    bounds "[left,top][right,bottom]" 转成 (x, y, 宽, 高)。
    所属应用取出现最多的包名（去掉 systemui）；没有占主导的包名时算桌面。
    """
    root = ET.fromstring(xml_text)
    elements: list[UIElement] = []
    for node in root.iter("node"):
        text = node.get("text", "") or ""
        desc = node.get("content-desc", "") or ""
        if not text and not desc:
            continue  # 没有任何文字信息的容器节点，跳过
        bounds = node.get("bounds", "")
        m = _BOUNDS_RE.match(bounds)
        if not m:
            continue
        left, top, right, bottom = map(int, m.groups())
        elements.append(UIElement(
            text=text,
            description=desc,
            bounds=(left, top, right - left, bottom - top),
            clickable=node.get("clickable", "false") == "true",
            package=node.get("package", "") or "",
        ))
    pkgs = Counter(
        el.package for el in elements
        if el.package and el.package != "com.android.systemui"
    )
    app = "桌面"
    if pkgs:
        top_package, count = pkgs.most_common(1)[0]
        if count >= 2:
            app = top_package
    return Screen(app=app, elements=elements, width=size[0], height=size[1])
