"""端到端测试：全 Mock，不需要任何外部服务。

跑：python3 -m unittest discover -s tests -v
"""
import unittest

from src.agent.loop import VoiceToActionLoop
from src.grounding.vlm import MockGrounding
from src.phone.cloud_phone import MockCloudPhone
from src.planner.llm_planner import Action, RuleBasedPlanner
from src.safety.guardrails import (
    BlockedByGuardrail,
    ConfirmationGate,
    HumanFallback,
    SpendingLimit,
)
from src.voice.asr import MockASR
from src.voice.tts import MockTTS


def make_loop(phone=None, asr=None, planner=None, confirm=True):
    phone = phone or MockCloudPhone()
    phone.connect()
    loop = VoiceToActionLoop(
        asr=asr or MockASR(),
        planner=planner or RuleBasedPlanner(),
        grounding=MockGrounding(),
        phone=phone,
        tts=MockTTS(),
        spending_limit=SpendingLimit(max_amount_cny=200),
        confirm_gate=ConfirmationGate(ask=lambda summary: confirm),
        fallback=HumanFallback(notify=lambda msg: None),
    )
    return loop, phone


class TestVoiceToActionLoop(unittest.TestCase):
    def test_open_wechat_end_to_end(self):
        loop, phone = make_loop(asr=MockASR(["打开微信"]))
        result = loop.run_once(b"")
        self.assertEqual(phone.current_app, "微信")
        self.assertIn("打开微信", result)

    def test_pay_without_confirmation_is_blocked(self):
        class PayPlanner:
            def plan(self, command):
                return [Action(kind="pay", target="水果店", params={"amount_cny": 50})]

        loop, _ = make_loop(planner=PayPlanner(), confirm=False)
        with self.assertRaises(BlockedByGuardrail):
            loop.run_once(b"")

    def test_pay_over_limit_is_blocked_even_with_confirmation(self):
        class PayPlanner:
            def plan(self, command):
                return [Action(kind="pay", target="水果店", params={"amount_cny": 500})]

        loop, _ = make_loop(planner=PayPlanner(), confirm=True)
        with self.assertRaises(BlockedByGuardrail):
            loop.run_once(b"")

    def test_three_failures_escalate_to_human(self):
        notified = []
        phone = MockCloudPhone(fail_times=99)
        loop, _ = make_loop(phone=phone, asr=MockASR(["打开微信"]))
        loop.fallback = HumanFallback(notify=notified.append)
        with self.assertRaises(RuntimeError):
            loop.run_once(b"")
        self.assertTrue(notified, "3 次失败后应该转人工")
        self.assertEqual(phone.current_app, "桌面")

    def test_adb_drop_mid_call_reconnects_and_completes(self):
        phone = MockCloudPhone(drop_after=1)
        loop, _ = make_loop(phone=phone, asr=MockASR(["打开微信"]))
        result = loop.run_once(b"")
        self.assertEqual(phone.current_app, "微信")
        self.assertIn("打开微信", result)


if __name__ == "__main__":
    unittest.main()
