# Codex 中文语音输入

一个面向 Windows 的开源中文语音输入工具。它可以把语音直接输入到 Codex 桌面客户端、Visual Studio Code 及兼容编辑器的当前输入框，不使用或覆盖系统剪贴板。

> 本项目是社区工具，与 OpenAI 无隶属或官方合作关系。

## 功能

- 离线实时识别：使用 `sherpa-onnx`，无需 API 和网络。
- API 转写：录音结束后调用 OpenAI 音频转写接口。
- 实时输入：离线识别结果边说边进入目标输入框，并处理识别修正。
- 语音发送：句尾说“发送、提交、回车”等命令后自动按 Enter。
- 可编辑快捷键：默认 `Ctrl+Alt+Space`，也支持 `F8`、`Ctrl+Shift+M` 等组合。
- 可选鼠标侧键：支持 X1 或 X2，没有侧键的鼠标不受影响。
- 直接输入与语音选窗口两种工作方式。
- 可选语音状态反馈和启动后自动监听。
- 奶蛙桌面宠物，待机、监听、目标、输入和错误状态使用不同动作。
- 可独立开关的宠物动作提示音。

## 支持的目标应用

当前内置支持：

- Codex Windows 桌面客户端
- Visual Studio Code
- Cursor
- Windsurf
- Trae
- VSCodium

程序只向明确支持的代码工具窗口发送键盘事件，避免误输入到终端、系统输入窗口或其他应用。

## 系统要求

- Windows 10 或 Windows 11
- Python 3.10 或更高版本
- 可用的麦克风

## 快速开始

直接双击：

```text
启动语音输入.vbs
```

首次启动会创建 `.venv` 并安装 `requirements.txt` 中的依赖。

也可以使用 PowerShell 启动：

```powershell
.\run.ps1
```

创建桌面快捷方式：

```powershell
.\创建桌面快捷方式.ps1
```

## 离线模型

在设置中点击“安装模型”，或者运行：

```powershell
.\安装离线模型.ps1
```

默认使用 sherpa-onnx 中文/英文流式模型：

```text
sherpa-onnx-x-asr-480ms-streaming-zipformer-transducer-zh-en-punct-int8-2026-06-05
```

模型大小约 128 MB，安装到本地 `models/`，不会提交到仓库。

## 工作方式

### 直接输入当前窗口

1. 在设置中启用“直接输入当前窗口”。
2. 点一下 Codex 或编辑器的目标输入框。
3. 按全局快捷键或点击“开始”。
4. 开始说话，句尾说“发送”可以自动回车。

离线模式会实时输入；API 模式会在停止录音并完成转写后一次性输入。

### 语音选择目标窗口

该方式用于离线模式。关闭“直接输入当前窗口”，然后说：

```text
打开 Codex 输入
打开 VS Code 输入
打开 项目名称 然后输入帮我检查这个文件发送
```

存在多个匹配窗口时，工具会显示候选窗口并等待编号选择。

## 快捷键设置

在“设置 → 启动快捷键”中直接编辑。支持：

```text
Ctrl+Alt+Space
Ctrl+Shift+M
Alt+F8
F8
```

普通字母不能单独作为全局快捷键，避免正常打字时误触。

鼠标侧键默认关闭。需要时可以启用并选择：

- 后退侧键 X1
- 前进侧键 X2

## API 模式

可以在启动程序前设置环境变量：

```powershell
$env:OPENAI_API_KEY="你的 API Key"
```

也可以临时填入设置界面。API Key 不会写入 `用户设置.json`。

## 设置与隐私

- 个人设置保存在 `用户设置.json`，该文件已加入 `.gitignore`。
- 示例配置见 `用户设置.example.json`。
- 程序不使用系统剪贴板输入文字。
- 调试日志最多保留当前 2 MB 和一个备份文件。
- 日志不记录完整实时语音正文。
- 离线模式的音频和识别均在本机完成。

## 更换宠物形象

当前程序优先读取 `assets/pet/` 中按状态分组的透明 PNG 帧：

```text
assets/pet/idle
assets/pet/listen
assets/pet/target
assets/pet/busy
assets/pet/error
```

状态含义：

- `idle`：未启动时的轻微待机动作。
- `listen`：麦克风正在监听。
- `target`：已选择目标窗口。
- `busy`：正在识别、转写或向输入框写入文字。
- `error`：目标丢失或发生错误。

“设置 → 宠物动作音效”可以独立开启或关闭短提示音，不影响语音状态反馈。
“快捷键切换笑声”使用源视频中的 1.8 秒笑声，只在按键盘全局快捷键或鼠标侧键开始录音时播放。停止录音、输入文字以及点击界面的“开始/停止”都不会触发笑声。笑声播放期间不会被其他宠物提示音打断。
“音效音量”滑杆可以在 `0%` 到 `100%` 之间调整宠物短提示音和笑声，不影响语音状态反馈音量。

开发者可以安装 FFmpeg 后，用以下脚本从源视频重新生成透明帧和提示音：

将源视频放在项目根目录并命名为 `奶蛙.mp4`，然后运行：

```powershell
.\.venv\Scripts\python.exe tools\build_pet_assets.py
```

旧版 `oneko.js` 贴图仍作为缺少新素材时的回退，许可证见：

```text
assets\oneko-LICENSE.txt
```

奶蛙动画和笑声由项目作者原创，并随项目按 MIT License 发布，详情见 `assets/pet/ASSET-NOTICE.md`。发布自己的贴图时，请同时提供对应许可证和来源说明。

## 开发与测试

仓库包含 Windows GitHub Actions，推送和 Pull Request 会在 Python 3.10 与 3.13 上自动运行测试。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m py_compile voice_input.py 测试实时退格.py
.\.venv\Scripts\python.exe 测试实时退格.py
```

贡献说明见 [CONTRIBUTING.md](CONTRIBUTING.md)。
版本记录见 [CHANGELOG.md](CHANGELOG.md)。

生成不包含模型、虚拟环境、日志和个人设置的发布压缩包：

```powershell
.\发布开源包.ps1
```

## License

项目代码使用 [MIT License](LICENSE)。第三方素材继续遵循各自许可证。
