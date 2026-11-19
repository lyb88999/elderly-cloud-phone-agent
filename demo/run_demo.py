"""端到端演示：真语音 → 真识别 → 真规划 → 真定位 → 真 ADB → 模拟手机。

每一步都会打印 [真实] 或 [演示]，诚实标注哪步是真跑的：
- 语音合成：Edge TTS（真实，免费，不用 key）
- 语音识别：faster-whisper tiny（真实，CPU 跑）
- 任务分解：有 OPENAI_API_KEY 或 DEEPSEEK_API_KEY 就走真实 LLM，否则用规则版
- 视觉定位：有 OPENAI_API_KEY 就走真实 VLM（需要能看图的模型），否则用文字匹配
- 云手机：真实 ADB 协议，对接 demo/fake-adb 模拟的手机；
  有真机 / 模拟器时把 adb 换成真的就行

跑：
    python3 demo/run_demo.py                  # 默认命令“打开微信”
    python3 demo/run_demo.py "打开支付宝"
    OPENAI_API_KEY=... python3 demo/run_demo.py
    DEEPSEEK_API_KEY=... python3 demo/run_demo.py

依赖：pip install -r requirements.txt（faster-whisper、edge-tts）。
"""
import os
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from src.agent.loop import VoiceToActionLoop
from src.grounding.vlm import MockGrounding, VisionGrounding
from src.llm.client import OpenAICompatibleClient
from src.phone.adb_client import ADBClient
from src.phone.cloud_phone import ADBCloudPhone
from src.planner.llm_planner import OpenAIPlanner, RuleBasedPlanner
from src.safety.guardrails import ConfirmationGate, HumanFallback, SpendingLimit
from src.voice.asr import FasterWhisperASR, MockASR
from src.voice.tts import EdgeTTS, GTTSTTS, MockTTS

FAKE_PHONE_STATE = "/tmp/elderly-agent-fake-phone.json"


def real_or_demo(real: bool) -> str:
    return "[真实]" if real else "[演示]"


def build_planner():
    """有 key 就用真实 LLM，否则规则版。"""
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIPlanner(OpenAICompatibleClient()), True, "OpenAI"
    if os.environ.get("DEEPSEEK_API_KEY"):
        client = OpenAICompatibleClient(
            api_key_env="DEEPSEEK_API_KEY",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
        )
        return OpenAIPlanner(client), True, "DeepSeek"
    return (
        RuleBasedPlanner(),
        False,
        "规则版（没配 OPENAI_API_KEY / DEEPSEEK_API_KEY）",
    )


def build_grounding():
    """只有 OpenAI 的多模态模型能看图；DeepSeek 没有视觉模型，走文字匹配。"""
    if os.environ.get("OPENAI_API_KEY"):
        client = OpenAICompatibleClient(model="gpt-4o-mini")
        return VisionGrounding(client), True, "OpenAI gpt-4o-mini"
    return MockGrounding(), False, "文字匹配（需要 OPENAI_API_KEY 才走 VLM）"


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "打开微信"
    print(f"演示命令：{command}\n")

    # 每次演示都从桌面开始
    if os.path.exists(FAKE_PHONE_STATE):
        os.unlink(FAKE_PHONE_STATE)

    # 1. 合成语音：先试 Edge TTS（音质好），不行就用 gTTS（走普通 HTTPS）
    audio_path = os.path.join(tempfile.gettempdir(), "elderly-agent-demo.mp3")
    tts_ok = False
    tts_name = ""
    for tts_cls, name in [(EdgeTTS, "Edge TTS"), (GTTSTTS, "gTTS")]:
        try:
            tts_cls().synthesize(command, audio_path)
            print(f"{real_or_demo(True)} 语音合成：{name} 已生成 {audio_path}")
            tts_ok, tts_name = True, name
            break
        except Exception as exc:
            print(f"[演示] {name} 合成失败（{str(exc)[:120]}），换下一个")

    # 2. 语音识别（真实 faster-whisper）
    heard = command
    asr_ok = False
    if tts_ok:
        try:
            print("正在加载 Whisper tiny 模型（首次运行会下载约 75MB）…")
            heard = FasterWhisperASR().transcribe_file(audio_path)
            heard = heard.strip().strip("。！？.,")
            print(f"{real_or_demo(True)} 语音识别：Whisper 听到的是“{heard}”")
            asr_ok = True
        except Exception as exc:
            print(f"{real_or_demo(False)} 语音识别失败（{exc}），用原命令继续演示")

    # 3. 任务分解
    planner, planner_real, planner_note = build_planner()
    print(f"{real_or_demo(planner_real)} 任务分解：{planner_note}")

    # 4. 视觉定位
    grounding, grounding_real, grounding_note = build_grounding()
    print(f"{real_or_demo(grounding_real)} 视觉定位：{grounding_note}")

    # 5. 云手机：真实 ADB 协议 + fake-adb 模拟手机
    fake_adb = os.path.join(REPO_ROOT, "demo", "fake-adb")
    phone = ADBCloudPhone(ADBClient(adb=[sys.executable, fake_adb]))
    phone.connect()
    print(f"{real_or_demo(True)} 云手机：ADB 已连上模拟手机（demo/fake-adb）")

    # 6. 跑一轮循环
    loop = VoiceToActionLoop(
        asr=MockASR([heard]),
        planner=planner,
        grounding=grounding,
        phone=phone,
        tts=MockTTS(),
        spending_limit=SpendingLimit(max_amount_cny=200),
        confirm_gate=ConfirmationGate(ask=lambda summary: True),
        fallback=HumanFallback(notify=lambda msg: print(f"[转人工] {msg}")),
    )
    try:
        result = loop.run_once(b"")
    except Exception as exc:
        print(f"\n演示失败：{exc}")
        print("（听错了、找不到应用、手机断线都会走到这里；真实场景会转人工处理）")
        return 1
    print(f"\n{result}")

    screen = phone.current_screen()
    print(f"当前屏幕：{screen.app}，共 {len(screen.elements)} 个元素")
    print("\n演示完成。步骤小结：")
    print(f"  语音合成：{real_or_demo(tts_ok)}（{tts_name or '失败'}）")
    print(f"  语音识别：{real_or_demo(asr_ok)}")
    print(f"  任务分解：{real_or_demo(planner_real)}")
    print(f"  视觉定位：{real_or_demo(grounding_real)}")
    print(f"  云手机 ADB：{real_or_demo(True)}（模拟手机）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
