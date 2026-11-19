# 架构：老年人云手机 Agent

## 一句话

老人说一句话，Agent 在云手机上帮他把事办了——不用他自己点屏幕。

## 整体链路

```
老人说话
  → ASR（语音转文字，faster-whisper）
  → Planner（LLM 任务分解：一句话 → 操作列表）
  → VLM 定位（在屏幕上按语义找目标，如“结账按钮”）
  → 云手机执行（ADB + WebRTC）
  → 读屏核对（操作真的生效了吗）
```

## 模块

| 模块 | 真实实现 | 演示 / 兜底 |
| --- | --- | --- |
| `src/voice/asr.py` | `FasterWhisperASR`（CPU 跑 tiny 模型）或 `WhisperASR`（openai-whisper） | `MockASR` 返回预设句子 |
| `src/voice/tts.py` | `EdgeTTS`（微软免费语音）、`GTTSTTS`（Google 翻译语音） | `MockTTS` 打印 |
| `src/planner/llm_planner.py` | `OpenAIPlanner`（OpenAI / DeepSeek 兼容接口） | `RuleBasedPlanner`（“打开XX”） |
| `src/grounding/vlm.py` | `VisionGrounding`（视觉模型看图给坐标） | `MockGrounding` 按文字匹配 |
| `src/phone/adb_client.py` | `ADBClient`（调系统 adb 命令行） | — |
| `src/phone/cloud_phone.py` | `ADBCloudPhone`（uiautomator dump + screencap + input tap + monkey） | `MockCloudPhone` 模拟桌面 |
| `src/phone/accessibility.py` | `parse_uiautomator_dump`（解析真机 XML） | 模拟元素列表 |
| `src/llm/client.py` | `OpenAICompatibleClient`（标准库 urllib，文本 + 看图） | — |
| `src/safety/guardrails.py` | 消费上限 / 支付确认 / 人工兜底 | — |
| `src/agent/loop.py` | 语音-动作循环 | — |

## 端到端演示

```bash
pip install -r requirements.txt
python3 demo/run_demo.py                  # 默认命令“打开微信”
python3 demo/run_demo.py "打开支付宝"
OPENAI_API_KEY=... python3 demo/run_demo.py
DEEPSEEK_API_KEY=... python3 demo/run_demo.py   # 只有任务分解走真实 LLM
```

每一步都会打印 `[真实]` 或 `[演示]`。demo 的手机是 `demo/fake-adb`
模拟的：它假装成 adb 命令行，返回写死的 `uiautomator dump` 和截图，
记录 `monkey` 启动和 `input tap`；`ADBCloudPhone` 的代码是真的，
发的每一条 adb 命令、解析的每一段 XML 都和接真机时一模一样。

## 关键决策（谈判里承诺过的）

1. **不靠写死坐标**：UI 更新会打破坐标，定位靠 VLM 语义理解 + 无障碍树对齐。
2. **失败 3 次转人工**：视觉-动作循环失败 3 次，通知家人接手，不让机器死磕。
3. **ADB 断线有预案**：心跳发现断线 → 冻结界面 → 后台重连 → 语音安抚（“奶奶，网络卡了一下，我再试一次”）→ 3 次不行打给家人。
4. **花钱必须确认**：单笔超过限额（默认 200 元）或任何支付动作，都要老人亲口确认才执行。

## 实现里的坑（已踩过）

- **Whisper 输出繁体**：tiny 模型默认容易输出繁体（“打開微信”），
  `initial_prompt` 写一句“请用简体中文转录”就稳在简体了。
- **Whisper 同音字听错**：gTTS 的“支付宝”曾被听成“支付堡”，
  把应用名写进 `initial_prompt`（“手机应用有微信、支付宝……”）后听对了。
- **faster-whisper 和 PyAV 版本**：1.2.1 调用 `av.open(..., metadata_errors=...)`，
  PyAV 15+ 删了这个参数；`requirements.txt` 里把 av 固定在 14.2.0。
- **Edge TTS 走 WebSocket**：有的沙箱 / 公司网络出口代理不支持 WebSocket 升级，
  会报 `101 Invalid connection header`；demo 会自动换成 gTTS。
  Edge TTS 还把 SSL 上下文写死成 certifi，不认出口拦截 CA，
  `EdgeTTS` 里会把上下文换成系统证书库（验证没关）。
- **VLM 需要能看图的模型**：DeepSeek 只有文本模型，视觉定位目前只支持 OpenAI。

## 怎么跑

```bash
# 演示模式：全 Mock，不需要麦克风、云手机、API key
python3 -m src.main --mock
python3 -m src.main --mock --command "打开支付宝"

# 端到端演示：真语音、真识别、真 ADB（模拟手机）
python3 demo/run_demo.py

# 测试（不连网、不接真机）
python3 -m unittest discover -s tests -v
```

## 接真机 / 真服务

1. 复制 `config.example.yaml` 为 `config.yaml`，填 ASR / LLM / 云手机配置。
2. `pip install -r requirements.txt`。
3. 真机：把 `ADBClient(adb=[...fake-adb])` 换成 `ADBClient()`（系统真 adb），
   `adb devices` 确认设备连上就行，其他代码不用改。
4. LLM：设 `OPENAI_API_KEY` 或 `DEEPSEEK_API_KEY` 环境变量。
5. VLM：需要 OpenAI 的多模态模型（`gpt-4o-mini`）。

## 下一步

- WebRTC 画面：把 `screenshot()` 从 screencap 轮询换成 WebRTC 帧流。
- 真机联调：先在自己的云手机实例上跑通“打开微信”，再接支付。
- 更大的 Whisper 模型：tiny 够演示用；老人说话含糊时换 small/base 更稳。
