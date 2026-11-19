# 端到端演示

`run_demo.py` 跑一轮完整的语音-动作循环：真语音 → 真识别 → 真规划 →
真定位 → 真 ADB → 模拟手机。每一步都会打印 `[真实]` 或 `[演示]`，
诚实标注哪步是真跑的。

## 跑

```bash
pip install -r requirements.txt
python3 demo/run_demo.py                  # 默认命令“打开微信”
python3 demo/run_demo.py "打开支付宝"
```

有 LLM key 时，任务分解和视觉定位也会走真实服务：

```bash
OPENAI_API_KEY=... python3 demo/run_demo.py
DEEPSEEK_API_KEY=... python3 demo/run_demo.py   # 只有任务分解走真实 LLM，视觉定位没有 DeepSeek 模型
```

## 每一步是什么

| 步骤 | 真实实现 | 演示时 |
| --- | --- | --- |
| 语音合成 | Edge TTS（免费，不用 key）或 gTTS | 真实；Edge TTS 的 WebSocket 在这台沙箱机器上被出口代理拦了，会自动换 gTTS |
| 语音识别 | faster-whisper tiny（CPU 跑） | 真实 |
| 任务分解 | OpenAI / DeepSeek 兼容接口 | 有 key 真实，没 key 用规则版 |
| 视觉定位 | OpenAI gpt-4o-mini 看图 | 有 key 真实，没 key 用文字匹配 |
| 云手机 | 真实 ADB 协议 | 对接 `demo/fake-adb` 模拟的手机 |

## 环境说明

- `requirements.txt` 把 `av` 固定在 14.2.0：faster-whisper 1.2.1 需要
  `av.open(..., metadata_errors=...)`，PyAV 15+ 删了这个参数。
- Whisper 的 `initial_prompt` 默认写了“请用简体中文转录。手机应用有
  微信、支付宝、电话、相机。”：tiny 模型默认容易输出繁体，
  “支付宝”还曾被听成“支付堡”，这句提示两个问题一起解决。

## fake-adb 是什么

一台假手机：用 Python 模拟 `adb` 命令行，返回写死的
`uiautomator dump` 和截图，记录 `monkey` 启动和 `input tap`。
`ADBCloudPhone` 的代码是真的——它发的每一条 adb 命令、
解析的每一段 XML 都和接真机时一模一样。

## 接真机 / 模拟器

把 `run_demo.py` 里的 `ADBClient(adb=[sys.executable, fake_adb])`
换成 `ADBClient()`（用系统里真的 `adb`），再 `adb devices`
确认设备连上就行，其他代码不用改。
