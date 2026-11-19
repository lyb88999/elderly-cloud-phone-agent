"""任务分解：把老人的一句话变成一步步的操作。

Action 是最小执行单元：kind + target + params。
- open_app：打开应用，target 是应用名，如“微信”
- tap：点屏幕上的某个元素，target 是语义描述，如“结账按钮”
- pay：支付，必须过安全确认门

真实实现是 OpenAIPlanner：走 OpenAI 兼容接口（OpenAI、DeepSeek 都行），
让模型输出 JSON 操作列表。RuleBasedPlanner 只留给演示兜底。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Protocol

from ..llm.client import OpenAICompatibleClient


@dataclass
class Action:
    kind: str                            # open_app | tap | pay
    target: str                          # 应用名或元素语义描述
    params: dict = field(default_factory=dict)


def parse_actions(raw: str) -> list[Action]:
    """把 LLM 输出的 JSON 解析成操作列表。

    接受裸数组 [{"kind": ..., "target": ...}]，
    也接受包一层的 {"actions": [...]} / {"steps": [...]}。
    """
    data = json.loads(raw)
    if isinstance(data, dict):
        steps = data.get("actions") or data.get("steps") or data.get("plan") or []
    else:
        steps = data
    return [
        Action(kind=s["kind"], target=s["target"], params=s.get("params", {}) or {})
        for s in steps
    ]


class Planner(Protocol):
    def plan(self, command: str) -> list[Action]:
        """把一句话命令分解成操作列表。"""
        ...


class RuleBasedPlanner:
    """演示兜底：只覆盖最常见的“打开XX”句式，没配 key 时用。"""

    def plan(self, command: str) -> list[Action]:
        command = command.strip()
        if command.startswith("打开"):
            app = command[2:].strip()
            return [Action(kind="open_app", target=app)]
        return [Action(kind="tap", target=command)]


class LLMPlanner:
    """通用 LLM 规划器：注入一个 chat 函数即可用。

    chat_fn(messages) -> str，返回 LLM 输出的 JSON 操作列表。
    """

    def __init__(
        self,
        chat_fn: Callable[[list[dict]], str],
        system_prompt: str = "",
    ):
        self._chat_fn = chat_fn
        self.system_prompt = system_prompt or (
            "你是一个帮老人操作手机的助手。把用户的一句话变成 JSON 操作列表，"
            "每个操作是 {kind, target}，kind 只能是 open_app、tap、pay。"
        )

    def plan(self, command: str) -> list[Action]:
        raw = self._chat_fn([
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": command},
        ])
        return parse_actions(raw)


class OpenAIPlanner:
    """真实 LLM 规划器：走 OpenAI 兼容接口，输出 JSON 操作列表。"""

    SYSTEM_PROMPT = (
        "你是一个帮老人操作手机的助手。把用户的一句话变成 JSON 操作列表，"
        "只输出 JSON，不要解释。每个操作是 {\"kind\": ..., \"target\": ..., \"params\": {...}}，"
        "kind 只能是 open_app（打开应用）、tap（点屏幕元素）、pay（支付）。"
        "比如“打开微信” → [{\"kind\": \"open_app\", \"target\": \"微信\"}]。"
    )

    def __init__(self, client: OpenAICompatibleClient):
        self._client = client

    def plan(self, command: str) -> list[Action]:
        raw = self._client.chat(
            [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": command},
            ],
            response_format="json_object",
        )
        return parse_actions(raw)
