"""语音播报：把提示说给老人听。

- EdgeTTS：微软 Edge 免费 TTS，真实实现，不用 key，音质最好。
- GTTSTTS：Google 翻译 TTS，真实实现，不用 key，走普通 HTTPS，
  在不支持 WebSocket 的网络里做兜底。
- MockTTS：只打印，演示兜底。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
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


def _play_audio(path: str, text: str) -> None:
    """有播放器就播出来，没有就告诉用户文件在哪。"""
    ffplay = shutil.which("ffplay")
    afplay = shutil.which("afplay")
    if ffplay:
        subprocess.run(
            [ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet", path],
            check=False,
        )
    elif afplay:
        subprocess.run([afplay, path], check=False)
    else:
        print(f"[语音播报] {text}（没有找到播放器，音频已保存到 {path}）")


class EdgeTTS:
    """微软 Edge 免费 TTS：不需要 key，中文语音效果不错。"""

    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural"):
        self.voice = voice

    def synthesize(self, text: str, path: str) -> str:
        """把文字转成语音，存成 mp3 文件，返回文件路径。"""
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError(
                "没有安装 edge-tts，请先 pip install edge-tts"
            ) from exc
        import asyncio
        import ssl

        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

        async def _run():
            import edge_tts.communicate as edge_comm

            # edge-tts 在 ws_connect 里写死了 ssl=_SSL_CTX（certifi 根证书），
            # 不认沙箱 / 公司网络的出口拦截 CA；传 connector 也绕不过去。
            # 这里把它换成系统证书库的上下文（包含这类 CA），
            # 再把 SSL_CERT_FILE 指向的 bundle 也加进来。
            # 在普通机器上这就是默认行为，不影响；验证没有关掉。
            ctx = ssl.create_default_context()
            cafile = os.environ.get("SSL_CERT_FILE")
            if cafile and os.path.exists(cafile):
                ctx.load_verify_locations(cafile=cafile)
            edge_comm._SSL_CTX = ctx
            communicate = edge_tts.Communicate(text, self.voice, proxy=proxy)
            await communicate.save(path)

        asyncio.run(_run())
        return path

    def speak(self, text: str) -> None:
        path = os.path.join(tempfile.gettempdir(), "elderly-agent-tts.mp3")
        self.synthesize(text, path)
        _play_audio(path, text)


class GTTSTTS:
    """Google 翻译 TTS：免费，不用 key，走普通 HTTPS。

    音质不如 Edge TTS，但在不支持 WebSocket 的网络里能跑，
    适合做演示兜底。
    """

    def __init__(self, lang: str = "zh-CN"):
        self.lang = lang

    def synthesize(self, text: str, path: str) -> str:
        """把文字转成语音，存成 mp3 文件，返回文件路径。"""
        try:
            from gtts import gTTS
        except ImportError as exc:
            raise RuntimeError("没有安装 gTTS，请先 pip install gTTS") from exc
        gTTS(text, lang=self.lang).save(path)
        return path

    def speak(self, text: str) -> None:
        path = os.path.join(tempfile.gettempdir(), "elderly-agent-tts.mp3")
        self.synthesize(text, path)
        _play_audio(path, text)
