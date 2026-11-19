"""语音识别：把老人的语音转成文字。

接口 ASR 只做一件事：transcribe(audio) -> str。
- WhisperASR：真实实现，懒加载 openai-whisper，没装会给明确提示。
- MockASR：演示用，按顺序返回预设的句子。
"""
from __future__ import annotations

import os
import tempfile
from typing import Iterable, Protocol


class ASR(Protocol):
    def transcribe(self, audio: bytes) -> str:
        """把一段语音转成文字。"""
        ...


class MockASR:
    """演示用 ASR：按顺序返回预设文本，不需要麦克风。"""

    def __init__(self, scripts: Iterable[str] = ("打开微信",)):
        self._scripts = iter(scripts)

    def transcribe(self, audio: bytes) -> str:
        return next(self._scripts, "")


class WhisperASR:
    """基于 openai-whisper 的真实 ASR。"""

    def __init__(self, model: str = "base", language: str = "zh"):
        self.model_name = model
        self.language = language
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                import whisper
            except ImportError as exc:
                raise RuntimeError(
                    "没有安装 openai-whisper，请先 pip install -r requirements.txt"
                ) from exc
            self._model = whisper.load_model(self.model_name)
        return self._model

    def transcribe(self, audio: bytes) -> str:
        # whisper 接受文件路径，这里把内存里的音频落成临时文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio)
            path = f.name
        try:
            result = self._load().transcribe(path, language=self.language)
            return result.get("text", "").strip()
        finally:
            os.unlink(path)
