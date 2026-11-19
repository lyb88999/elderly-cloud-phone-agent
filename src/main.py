"""入口：

    python3 -m src.main --mock                          # 演示：打开微信
    python3 -m src.main --mock --command "打开支付宝"     # 演示：换一句命令

--mock 是演示模式：全 Mock，不需要麦克风、云手机和 API key。
真实模式先复制 config.example.yaml 为 config.yaml 并填好配置。
"""
from __future__ import annotations

import argparse
import sys


def build_mock_loop(command: str = "打开微信"):
    """组装一套全 Mock 的循环：能跑，不需要任何外部服务。"""
    from .agent.loop import VoiceToActionLoop
    from .grounding.vlm import MockGrounding
    from .phone.cloud_phone import MockCloudPhone
    from .planner.llm_planner import RuleBasedPlanner
    from .safety.guardrails import ConfirmationGate, HumanFallback, SpendingLimit
    from .voice.asr import MockASR
    from .voice.tts import MockTTS

    phone = MockCloudPhone()
    phone.connect()
    return VoiceToActionLoop(
        asr=MockASR([command]),
        planner=RuleBasedPlanner(),
        grounding=MockGrounding(),
        phone=phone,
        tts=MockTTS(),
        spending_limit=SpendingLimit(max_amount_cny=200),
        confirm_gate=ConfirmationGate(ask=lambda summary: True),
        fallback=HumanFallback(notify=lambda msg: print(f"[转人工] {msg}")),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="老年人云手机 Agent")
    parser.add_argument("--mock", action="store_true", help="演示模式：全 Mock，不需要外部服务")
    parser.add_argument("--command", default="打开微信", help="演示模式下要执行的语音命令")
    parser.add_argument("--config", default="config.yaml", help="真实模式配置文件")
    args = parser.parse_args(argv)

    if not args.mock:
        print("真实模式还没接好：先复制 config.example.yaml 为 config.yaml，"
              "填好 ASR / LLM / 云手机配置后再跑。")
        print("想先看效果：python3 -m src.main --mock")
        return 2

    loop = build_mock_loop(args.command)
    result = loop.run_once(b"")  # MockASR 不用真音频，传空字节即可
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
