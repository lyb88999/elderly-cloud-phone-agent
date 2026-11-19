"""ADB 客户端：用系统 adb 命令行和安卓设备说话。

只依赖 adb 可执行文件本身。demo 用 demo/fake-adb 模拟一台手机；
接真机 / 模拟器时把 adb 换成真的就行，代码不用改。
adb 参数可以传字符串路径，也可以传命令列表
（比如 [sys.executable, "demo/fake-adb"]，不用依赖可执行权限）。
"""
from __future__ import annotations

import subprocess


class ADBError(RuntimeError):
    pass


class ADBClient:
    def __init__(self, adb: str | list[str] = "adb", serial: str | None = None):
        self.adb = adb
        self.serial = serial

    def _base(self) -> list[str]:
        cmd = [self.adb] if isinstance(self.adb, str) else list(self.adb)
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def _run(
        self, *args: str, input_bytes: bytes | None = None
    ) -> subprocess.CompletedProcess:
        cmd = self._base() + list(args)
        try:
            return subprocess.run(
                cmd, input=input_bytes, capture_output=True, timeout=30
            )
        except FileNotFoundError as exc:
            raise ADBError(
                f"找不到 adb：{self.adb}，请先安装 Android platform-tools"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ADBError(f"adb 命令超时：{' '.join(cmd)}") from exc

    def devices(self) -> list[str]:
        result = self._run("devices")
        if result.returncode != 0:
            raise ADBError(result.stderr.decode("utf-8", "ignore"))
        serials = []
        for line in result.stdout.decode("utf-8", "ignore").splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                serials.append(parts[0])
        return serials

    def shell(self, *args: str) -> str:
        result = self._run("shell", *args)
        if result.returncode != 0:
            raise ADBError(
                f"adb shell {' '.join(args)} 失败："
                f"{result.stderr.decode('utf-8', 'ignore')[:200]}"
            )
        return result.stdout.decode("utf-8", "ignore")

    def exec_out(self, *args: str) -> bytes:
        result = self._run("exec-out", *args)
        if result.returncode != 0:
            raise ADBError(
                f"adb exec-out {' '.join(args)} 失败："
                f"{result.stderr.decode('utf-8', 'ignore')[:200]}"
            )
        return result.stdout

    def tap(self, x: int, y: int) -> None:
        self.shell("input", "tap", str(x), str(y))

    def launch(self, package: str) -> None:
        self.shell(
            "monkey", "-p", package, "-c",
            "android.intent.category.LAUNCHER", "1",
        )

    def dump_xml(self) -> str:
        self.shell("uiautomator", "dump", "/sdcard/window_dump.xml")
        return self.shell("cat", "/sdcard/window_dump.xml")

    def screencap(self) -> bytes:
        return self.exec_out("screencap", "-p")

    def screen_size(self) -> tuple[int, int]:
        out = self.shell("wm", "size")
        # "Physical size: 1080x1920"
        for token in out.replace(":", " ").split():
            if "x" in token and token.replace("x", "").isdigit():
                w, h = token.split("x")
                return int(w), int(h)
        return 1080, 1920

    def ping(self) -> bool:
        try:
            return self.shell("echo", "ok").strip() == "ok"
        except ADBError:
            return False
