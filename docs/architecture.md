# 架构：老年人云手机 Agent

## 一句话

老人说一句话，Agent 在云手机上帮他把事办了——不用他自己点屏幕。

## 整体链路

```
老人说话
  → ASR（语音转文字，Whisper）
  → Planner（LLM 任务分解：一句话 → 操作列表）
  → VLM 定位（在屏幕上按语义找目标，如“结账按钮”）
  → 云手机执行（ADB + WebRTC）
  → 读屏核对（操作真的生效了吗）
```

## 模块

| 模块 | 职责 | 真实实现 | 演示实现 |
| --- | --- | --- | --- |
| `src/voice/asr.py` | 语音转文字 | openai-whisper | `MockASR` 返回预设句子 |
| `src/voice/tts.py` | 语音播报 | 任意 TTS 服务 | `MockTTS` 打印 |
| `src/planner/llm_planner.py` | 一句话 → 操作列表 | LLM 输出 JSON 操作 | `RuleBasedPlanner`（“打开XX”） |
| `src/grounding/vlm.py` | 语义定位屏幕元素 | VLM 看图定位 | `MockGrounding` 按文字匹配 |
| `src/phone/cloud_phone.py` | 云手机会话 | ADB + WebRTC | `MockCloudPhone` 模拟桌面 |
| `src/phone/accessibility.py` | 无障碍节点树 | 真机无障碍服务 | 模拟元素列表 |
| `src/safety/guardrails.py` | 安全护栏 | — | 消费上限 / 支付确认 / 人工兜底 |
| `src/agent/loop.py` | 语音-动作循环 | — | 串起上面所有模块 |

## 关键决策（谈判里承诺过的）

1. **不靠写死坐标**：UI 更新会打破坐标，定位靠 VLM 语义理解 + 无障碍树对齐。
2. **失败 3 次转人工**：视觉-动作循环失败 3 次，通知家人接手，不让机器死磕。
3. **ADB 断线有预案**：心跳发现断线 → 冻结界面 → 后台重连 → 语音安抚（“奶奶，网络卡了一下，我再试一次”）→ 3 次不行打给家人。
4. **花钱必须确认**：单笔超过限额（默认 200 元）或任何支付动作，都要老人亲口确认才执行。

## 怎么跑

```bash
# 演示模式：全 Mock，不需要麦克风、云手机、API key
python3 -m src.main --mock
python3 -m src.main --mock --command "打开支付宝"

# 测试
python3 -m unittest discover -s tests -v
```

## 接真实服务

1. 复制 `config.example.yaml` 为 `config.yaml`，填 ASR / LLM / 云手机配置。
2. `pip install -r requirements.txt`。
3. 把 `WhisperASR`、`LLMPlanner`、`VLMLocator`、`CloudPhone` 的真实实现接进来——
   循环逻辑在 `src/agent/loop.py`，换实现不用改循环。

## 下一步

- VLM 真实接入：截图 + 描述发给视觉模型，坐标回填到无障碍树。
- WebRTC 画面：真机屏幕流进循环，替代 `MockCloudPhone` 的模拟屏幕。
- 真机联调：先在自己的云手机实例上跑通“打开微信”，再接支付。
