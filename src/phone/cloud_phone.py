"""云手机连接：ADB + WebRTC 会话、心跳、断线重连。

真实实现要接云手机厂商的 ADB / WebRTC 服务；
这里先定义接口 + 一个可跑的 Mock。循环逻辑（心跳、冻结、重连）
已经在 VoiceToActionLoop 里实现，换真实实现不用改循环。
"""
from __future__ import annotations

from typing import Protocol

from .accessibility import Screen, UIElement


class CloudPhone(Protocol):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def is_alive(self) -> bool: ...
    def current_screen(self) -> Screen: ...
    def tap(self, element: UIElement) -> bool: ...
    def open_app(self, package: str) -> bool: ...
    def freeze_ui(self) -> None: ...
    def unfreeze_ui(self) -> None: ...


class MockCloudPhone:
    """模拟云手机：桌面上有几个应用，open_app 会“打开”它。

    fail_times：前 N 次操作故意失败，用来演练重试 / 兜底。
    drop_after：执行多少次操作后模拟 ADB 断线一次。
    """

    APPS = {
        "微信": "com.tencent.mm",
        "支付宝": "com.eg.android.AlipayGphone",
        "电话": "com.android.dialer",
        "相机": "com.android.camera",
    }

    def __init__(self, fail_times: int = 0, drop_after: int | None = None):
        self._fail_times = fail_times
        self._drop_after = drop_after
        self._ops = 0
        self._alive = False
        self._frozen = False
        self.current_app = "桌面"
        self.tapped: list[str] = []

    def connect(self) -> None:
        self._alive = True

    def disconnect(self) -> None:
        self._alive = False

    def is_alive(self) -> bool:
        return self._alive

    def _maybe_drop(self) -> bool:
        """模拟 ADB 中途断线：返回 True 表示这次断了。"""
        self._ops += 1
        if self._drop_after is not None and self._ops == self._drop_after:
            self._alive = False
            self._drop_after = None
            return True
        return False

    def _maybe_fail(self) -> bool:
        if self._fail_times > 0:
            self._fail_times -= 1
            return True
        return False

    def current_screen(self) -> Screen:
        if self.current_app == "桌面":
            elements = [
                UIElement(text=name, description=f"打开{name}应用", package=pkg)
                for name, pkg in self.APPS.items()
            ]
            return Screen(app="桌面", elements=elements)
        return Screen(app=self.current_app, elements=[
            UIElement(text=self.current_app, description=f"{self.current_app}主界面"),
        ])

    def tap(self, element: UIElement) -> bool:
        if not self._alive or self._frozen:
            return False
        if self._maybe_drop() or self._maybe_fail():
            return False
        self.tapped.append(element.text)
        return True

    def open_app(self, package: str) -> bool:
        if not self._alive or self._frozen:
            return False
        if self._maybe_drop() or self._maybe_fail():
            return False
        for name, pkg in self.APPS.items():
            if pkg == package:
                self.current_app = name
                return True
        return False

    def freeze_ui(self) -> None:
        self._frozen = True

    def unfreeze_ui(self) -> None:
        self._frozen = False
