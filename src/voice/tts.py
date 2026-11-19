"""语音播报：把提示说给老人听。

MockTTS 只打印，真实实现可以接任何 TTS 服务。
"""
from __future__ import annotations

from typing import Protocol


class TTS(Protocol):
    def speak(self, text: str) -> None:
        """播报一句话。"""
        ...


class MockTTS:
    def speak(self, text: str) -> None:
        print(f"[语音播报] {text}")


# 断线重连时安抚老人的固定话术
NETWORK_LAG_PROMPT = "奶奶，网络卡了一下，我再试一次。"
