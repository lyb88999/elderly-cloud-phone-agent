"""安全护栏：花钱要确认，失败要转人工。

三条红线：
1. 消费上限：单笔超过限额必须先问老人。
2. 支付确认：任何支付动作都要老人亲口说“确认”才执行。
3. 人工兜底：视觉-动作循环失败 3 次，转接家人处理。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


class BlockedByGuardrail(Exception):
    """被安全护栏拦下的操作。"""


@dataclass
class SpendingLimit:
    """单笔消费上限（元）。"""

    max_amount_cny: float = 200.0

    def check(self, amount_cny: float) -> None:
        if amount_cny > self.max_amount_cny:
            raise BlockedByGuardrail(
                f"金额 {amount_cny} 元超过单笔上限 {self.max_amount_cny} 元，需要人工确认"
            )


class ConfirmationGate:
    """支付确认门：ask 函数负责问老人，返回 True 才放行。

    ask 由调用方提供：真机上是语音播报 + 等老人回答；
    演示里用预设的回答。
    """

    def __init__(self, ask: Callable[[str], bool]):
        self._ask = ask

    def confirm(self, summary: str) -> None:
        if not self._ask(summary):
            raise BlockedByGuardrail(f"用户未确认，取消操作：{summary}")


class HumanFallback:
    """人工兜底：失败超过阈值就通知家人。"""

    def __init__(self, notify: Callable[[str], None], max_failures: int = 3):
        self._notify = notify
        self.max_failures = max_failures
        self.failures = 0

    def record_failure(self) -> bool:
        """记一次失败。返回 True 表示已达到阈值，需要转人工。"""
        self.failures += 1
        return self.failures >= self.max_failures

    def escalate(self, reason: str) -> None:
        self._notify(f"需要人工协助：{reason}（已失败 {self.failures} 次）")
        self.failures = 0
