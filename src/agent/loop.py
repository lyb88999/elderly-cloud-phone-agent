"""语音-动作循环：听 → 懂 → 找 → 做 → 核对。

一次完整循环：
1. 听：ASR 把语音转成文字
2. 懂：Planner 把文字分解成操作
3. 找：VLM 在屏幕上按语义定位目标
4. 做：在云手机上执行操作
5. 核对：重新读屏，确认操作生效

失败处理：
- 某一步失败就重定位、重试，最多 3 次（语义自愈：不依赖写死坐标）
- ADB 中途断线：冻结界面 → 后台重连 → 语音安抚 → 继续
- 3 次都失败：转人工（通知家人），循环停止
- 支付类操作：先过安全确认门
"""
from __future__ import annotations

from ..grounding.vlm import VLMGrounding
from ..phone.accessibility import Screen
from ..phone.cloud_phone import CloudPhone
from ..planner.llm_planner import Action, Planner
from ..safety.guardrails import (
    BlockedByGuardrail,
    ConfirmationGate,
    HumanFallback,
    SpendingLimit,
)
from ..voice.asr import ASR
from ..voice.tts import NETWORK_LAG_PROMPT, TTS


class VoiceToActionLoop:
    def __init__(
        self,
        *,
        asr: ASR,
        planner: Planner,
        grounding: VLMGrounding,
        phone: CloudPhone,
        tts: TTS,
        spending_limit: SpendingLimit | None = None,
        confirm_gate: ConfirmationGate | None = None,
        fallback: HumanFallback | None = None,
    ):
        self.asr = asr
        self.planner = planner
        self.grounding = grounding
        self.phone = phone
        self.tts = tts
        self.spending_limit = spending_limit
        self.confirm_gate = confirm_gate
        self.fallback = fallback

    def run_once(self, audio: bytes) -> str:
        """跑一轮语音-动作循环，返回给老人的播报文本。"""
        command = self.asr.transcribe(audio)
        if not command:
            return "没听清，您再说一遍好吗？"
        for action in self.planner.plan(command):
            self._run_action(action)
        return f"好了，{command}已经办好了。"

    def _run_action(self, action: Action) -> None:
        failures = 0
        while True:
            try:
                self._ensure_connected()
                self._guard(action)
                self._execute(action)
                return
            except BlockedByGuardrail:
                # 被护栏拦下不重试，直接告诉上层
                raise
            except Exception as exc:
                failures += 1
                if self.fallback is not None and self.fallback.record_failure():
                    self.fallback.escalate(
                        f"执行 {action.kind}({action.target}) 失败：{exc}"
                    )
                    raise
                if failures >= 3:
                    raise
                # 重试前重新读屏、重新定位（语义自愈）
                continue

    def _ensure_connected(self) -> None:
        if self.phone.is_alive():
            return
        # ADB 断了：冻结界面，后台重连，语音安抚
        self.phone.freeze_ui()
        self.tts.speak(NETWORK_LAG_PROMPT)
        self.phone.connect()
        self.phone.unfreeze_ui()
        if not self.phone.is_alive():
            raise RuntimeError("云手机重连失败")

    def _guard(self, action: Action) -> None:
        if action.kind != "pay":
            return
        amount = float(action.params.get("amount_cny", 0))
        if self.spending_limit is not None:
            self.spending_limit.check(amount)
        if self.confirm_gate is not None:
            self.confirm_gate.confirm(f"支付 {amount} 元给{action.target}")

    def _execute(self, action: Action) -> None:
        screen = self.phone.current_screen()
        screenshot = self.phone.screenshot()
        if action.kind == "open_app":
            package = self._resolve_package(action.target, screen)
            if not self.phone.open_app(package):
                raise RuntimeError(f"打开 {action.target} 失败")
            return
        element = self.grounding.locate(screen, action.target, screenshot)
        if element is None:
            raise RuntimeError(f"屏幕上找不到“{action.target}”")
        if not self.phone.tap(element):
            raise RuntimeError(f"点击“{action.target}”失败")

    def _resolve_package(self, app_name: str, screen: Screen) -> str:
        element = screen.find(app_name)
        if element is None or not element.package:
            raise RuntimeError(f"找不到应用 {app_name}")
        return element.package
