"""语音识别：把老人的语音转成文字。

接口 ASR 只做一件事：transcribe(audio) -> str。
- FasterWhisperASR：真实实现，CPU 就能跑，tiny 模型约 75MB，首选。
- WhisperASR：openai-whisper 的真实实现，有 GPU 时用。
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


class FasterWhisperASR:
    """基于 faster-whisper 的真实 ASR：CPU 就能跑，tiny 模型只有约 75MB。

    首次使用会自动从 Hugging Face 下载模型，需要联网。
    transcribe_file 直接传文件路径（mp3/wav 都行）；transcribe 接 bytes，
    默认按 wav 处理。
    """

    def __init__(
        self,
        model: str = "tiny",
        language: str = "zh",
        device: str = "cpu",
        compute_type: str = "int8",
        # tiny 模型默认容易输出繁体，加一句提示把它稳在简体；
        # 顺便把手机上的应用名写进提示，宝/堡这类同音字就不会听错
        initial_prompt: str = "请用简体中文转录。手机应用有微信、支付宝、电话、相机。",
    ):
        self.model_name = model
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self.initial_prompt = initial_prompt
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError(
                    "没有安装 faster-whisper，请先 pip install faster-whisper"
                ) from exc
            self._model = WhisperModel(
                self.model_name, device=self.device, compute_type=self.compute_type
            )
        return self._model

    def transcribe(self, audio: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio)
            path = f.name
        try:
            return self.transcribe_file(path)
        finally:
            os.unlink(path)

    def transcribe_file(self, path: str) -> str:
        segments, _ = self._load().transcribe(
            path, language=self.language, initial_prompt=self.initial_prompt
        )
        return "".join(seg.text for seg in segments).strip()


class WhisperASR:
    """基于 openai-whisper 的真实 ASR（需要 torch，有 GPU 时用）。"""

    def __init__(
        self,
        model: str = "base",
        language: str = "zh",
        # 同样原因：默认提示把它稳在简体，并给出应用名防同音字听错
        initial_prompt: str = "请用简体中文转录。手机应用有微信、支付宝、电话、相机。",
    ):
        self.model_name = model
        self.language = language
        self.initial_prompt = initial_prompt
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
            result = self._load().transcribe(
                path, language=self.language, initial_prompt=self.initial_prompt
            )
            return result.get("text", "").strip()
        finally:
            os.unlink(path)
