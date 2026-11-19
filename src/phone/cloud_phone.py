"""云手机连接：ADB + WebRTC 会话、心跳、断线重连。

- ADBCloudPhone：真实实现，通过 adb 和真机 / 模拟器 / 云手机实例通信。
  读屏用 uiautomator dump，截图用 screencap，点击用 input tap，
  打开应用用 monkey，心跳用 shell echo ok。
  WebRTC 画面流是生产环境的下一步：先用 screencap 轮询把链路跑通，
  再把 screenshot() 换成 WebRTC 帧。
- MockCloudPhone：可跑的模拟手机，循环逻辑和测试用它。

循环逻辑（心跳、冻结、重连）已经在 VoiceToActionLoop 里实现，
换真实实现不用改循环。
"""
from __future__ import annotations

from typing import Protocol

from .accessibility import Screen, UIElement, parse_uiautomator_dump
from .adb_client import ADBClient, ADBError


class CloudPhone(Protocol):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def is_alive(self) -> bool: ...
    def current_screen(self) -> Screen: ...
    def screenshot(self) -> bytes: ...
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

    def screenshot(self) -> bytes:
        return b""  # 模拟手机没有真实画面

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


class ADBCloudPhone:
    """真实云手机：通过 adb 和设备通信。

    常见包名到应用名的映射只用来显示，找不到就直接显示包名。
    """

    KNOWN_APPS = {
        "com.tencent.mm": "微信",
        "com.eg.android.AlipayGphone": "支付宝",
        "com.android.dialer": "电话",
        "com.android.camera": "相机",
    }

    def __init__(self, adb: ADBClient | None = None):
        self.adb = adb or ADBClient()
        self._alive = False
        self._frozen = False
        self._screen_size: tuple[int, int] = (1080, 1920)

    def connect(self) -> None:
        devices = self.adb.devices()
        if self.adb.serial and self.adb.serial not in devices:
            raise ADBError(f"设备 {self.adb.serial} 没连上，当前设备：{devices}")
        if not devices:
            raise ADBError(
                "没有连上的设备：请接真机 / 模拟器，或用 demo/fake-adb 跑演示"
            )
        self._alive = True
        try:
            self._screen_size = self.adb.screen_size()
        except ADBError:
            pass

    def disconnect(self) -> None:
        self._alive = False

    def is_alive(self) -> bool:
        # 心跳：每次都真实 ping 一下设备
        return self._alive and self.adb.ping()

    def current_screen(self) -> Screen:
        xml = self.adb.dump_xml()
        screen = parse_uiautomator_dump(xml, self._screen_size)
        screen.app = self.KNOWN_APPS.get(screen.app, screen.app)
        return screen

    def screenshot(self) -> bytes:
        return self.adb.screencap()

    def tap(self, element: UIElement) -> bool:
        if not self._alive or self._frozen:
            return False
        x, y, w, h = element.bounds
        try:
            self.adb.tap(x + w // 2, y + h // 2)
        except ADBError:
            return False
        return True

    def open_app(self, package: str) -> bool:
        if not self._alive or self._frozen:
            return False
        try:
            self.adb.launch(package)
        except ADBError:
            return False
        return True

    def freeze_ui(self) -> None:
        self._frozen = True

    def unfreeze_ui(self) -> None:
        self._frozen = False
