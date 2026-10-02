# Codex Voice Input

[![Windows CI](https://github.com/liaosongjie/Codex-Voice-Input/actions/workflows/ci.yml/badge.svg)](https://github.com/liaosongjie/Codex-Voice-Input/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Windows](https://img.shields.io/badge/Platform-Windows-0078D4)](https://www.microsoft.com/windows)

面向 Windows 的中文语音输入工具，可将识别结果直接输入 Codex 桌面客户端、Visual Studio Code 及兼容编辑器，不使用或覆盖系统剪贴板。

> 本项目是社区开源工具，与 OpenAI 无隶属或官方合作关系。

## 主要功能

- 离线实时识别：基于 `sherpa-onnx`，语音和识别均在本机处理。
- OpenAI API 转写：录音结束后调用音频转写接口。
- 直接输入：将文字发送到当前 Codex 或编辑器输入框。
- 语音命令：支持“发送”“提交”“回车”等句尾命令。
- 自定义快捷键：支持组合键、F 功能键和可选鼠标侧键。
- 目标窗口选择：支持直接输入和语音选择窗口两种模式。
- 桌面宠物：提供待机、监听、目标、输入和错误状态动画。
- 可配置反馈：可分别控制语音反馈、宠物音效、笑声和音量。

## 支持的软件

- Codex Windows 桌面客户端
- Visual Studio Code
- Cursor
- Windsurf
- Trae
- VSCodium

程序仅向明确支持的代码工具窗口发送键盘事件，避免误输入到终端、系统输入窗口或其他应用。

## 快速开始

### 推荐：Windows 便携版

1. 打开 [最新 Release](https://github.com/liaosongjie/Codex-Voice-Input/releases/latest)。
2. 在 **Assets** 中下载 `CodexVoiceInput-版本号-win64.zip`，不要下载 `Source code`。
3. 将 ZIP 完整解压到普通文件夹，不要直接在压缩包内运行。
4. 双击 `CodexVoiceInput.exe`。

Windows 便携版已经包含 Python 和程序依赖，不需要另行安装 Python。可以运行 `CreateDesktopShortcut.ps1` 创建桌面快捷方式。

程序第一次打开时会询问是否下载约 128 MB 的离线模型：

- 选择“是”：显示下载进度，安装完成后可直接使用离线实时识别。
- 选择“否”：可以稍后在设置中点击“下载离线模型”，或切换到 OpenAI API 模式并填写 API Key。

系统要求：64 位 Windows 10/11 和可用麦克风。

### 开发者：从源码运行

源码运行需要 Python 3.10 或更高版本：

```powershell
git clone https://github.com/liaosongjie/Codex-Voice-Input.git
cd Codex-Voice-Input
.\run.ps1
```

创建桌面快捷方式：

```powershell
.\scripts\create_desktop_shortcut.ps1
```

Release 中名称包含 `-python.zip` 的包同样需要预装 Python，主要用于源码调试和二次开发。普通用户应下载 `-win64.zip`。

## 离线识别

首次运行会主动询问是否下载。也可以随时在设置中点击“下载离线模型”，或运行：

```powershell
.\scripts\install_offline_model.ps1
```

默认模型约 128 MB，安装到本地 `models/`，仅需下载一次。下载和安装过程中会显示状态，网络中断后可以直接重试。

## OpenAI API 模式

启动前设置环境变量：

```powershell
$env:OPENAI_API_KEY="你的 API Key"
.\run.ps1
```

也可以在设置界面临时填写。API Key 不会保存到个人设置文件。程序会在开始录音前检查 Key，避免录完后才提示配置缺失。

## 基本使用

1. 确认离线模型已经安装，或 API Key 已填写。
2. 在 Codex 或编辑器中点选目标输入框。
3. 按默认快捷键 `Ctrl+Alt+Space` 开始监听。
4. 说出要输入的内容。
5. 再按一次快捷键停止；句尾说“发送”可自动按 Enter。

快捷键可在设置中修改，例如 `Ctrl+Shift+M`、`Alt+F8` 或 `F8`。鼠标侧键默认关闭，没有侧键的设备不受影响。

在设置的“输入目标”中选择工作方式：

- **当前窗口输入**：不切换窗口，直接把语音实时输入到当前已聚焦的输入框。微信、浏览器、办公软件等只要当前焦点是可输入位置，都可以使用。
- **Codex 输入**：开始录音时自动切到 Codex 窗口并聚焦输入框，再直接输入语音。
- **打开/找到窗口**：绑定程序后，打开时启动并扫描，找到时只扫描已运行窗口。

切换“输入目标”后会自动开始监听；如果已经在监听，只会切换后续文字的目标，不需要再次点击“开始”。

语音命令中“打开”与“找到/切换”是不同动作：

- **打开**：先启动程序，再扫描它出现的窗口；如果有多个窗口，会列出编号，等你说窗口编号后再进入输入。
- **找到/切换**：只扫描已经运行的窗口，不会启动新程序。找到多个窗口时同样先列出编号，再进入输入。

已配置的程序优先使用配置路径；未配置的程序会尝试从桌面、开始菜单快捷方式和常见安装路径查找，
例如可以直接说“打开豆包”。

选择“打开/找到窗口”后，可使用语音选择目标：

```text
打开 Codex 输入
打开 VS Code 输入
打开 项目名称 然后输入帮我检查这个文件发送
```

## 常见问题

### 自定义程序与项目

在设置里点击“程序与项目”，只需添加程序名称、语音别名、启动地址和进程名。
启动地址支持 `.exe`、`.lnk` 快捷方式及软件跳转链接；不是命令行，不拼接额外命令。
程序路径可通过“选择程序或快捷方式”选择。进程名填写实际窗口所属进程，例如
`chatgpt.exe`、`code.exe`；多个进程名或别名用逗号分隔。浏览器也不需要填写窗口标题。

更快的方式是点击“一键绑定当前窗口”。工具会暂时隐藏设置窗口，你切到目标程序即可自动读取启动路径和进程名。
启动后工具会扫描该程序内部的任务、对话框和可点击项目，不再要求填写窗口标题、输入框名称或控件 ID。

软件内部有多个任务时，打开程序后直接说任务名称，例如“日常”或“用户打招呼”。之后可以说：

```text
打开 WorkBuddy 日常
切换到 WorkBuddy 用户打招呼
```

工具会先打开或找到软件，扫描并选择对应任务，最后聚焦输入框并等待语音输入。

保存后选择“打开/找到窗口”，使用离线识别模式并开始监听，例如：

```text
打开 WorkBuddy
日常
帮我检查这个项目发送
```

指令在语句结束后执行，避免说到一半就切换。省略程序名时优先使用最近一次成功切换的程序。
多窗口会显示编号；程序内部任务会先扫描再按语音名称选择。播报“窗口已打开等待输入”之前会核对输入框焦点；
发送后继续监听，不退出录音。程序和项目配置仅保存在本机的 `程序与项目.json`，不提交 Git。
部分软件不向 Windows UI Automation 暴露项目或输入框，这类界面会先尝试 Windows 屏幕文字识别，
找到你说的任务后点击并聚焦底部输入区；如果屏幕文字识别也没有找到，会提示重新说一次。
这不是额外聊天 API，不会上传屏幕截图。

### Windows 提示来源未知或安全软件报警

当前便携版没有商业代码签名。程序还需要全局快捷键和模拟按键权限，因此 Windows SmartScreen 或安全软件可能提示。请确认文件来自本仓库 Release，再按需要选择“更多信息 → 仍要运行”。

### Python 版本提示没有 Python

说明下载的是源码 ZIP 或名称包含 `-python.zip` 的开发包。普通用户请改为下载 `CodexVoiceInput-版本号-win64.zip`；只有源码运行才需要安装 Python。

### 离线模式无法开始

打开设置，点击“下载离线模型”，等待进度完成后重试。模型只需安装一次。

### API 模式无法开始

在“模型与 API”中填写有效的 OpenAI API Key。API 模式会将录音发送到 OpenAI 进行转写。

### 安全软件提示键盘或鼠标权限

程序需要监听全局快捷键并向目标编辑器发送按键，因此部分安全软件可能提示相关权限。请仅从本仓库 Release 下载，并按需要授权。

## 隐私与权限

- 离线模式不会上传录音或识别内容。
- API 模式会将录音发送到所配置的 OpenAI API。
- 程序不读取、不使用也不覆盖系统剪贴板。
- `用户设置.json`、日志、模型和虚拟环境均已排除在版本控制之外。
- 程序使用全局键盘/鼠标监听和模拟按键，部分安全软件可能提示相关权限。

## 项目结构

```text
assets/                 宠物动画、音效及第三方素材声明
config/                 示例配置
scripts/                用户安装和快捷方式脚本
scripts/maintainer/     发布与素材维护工具
tests/                  自动化断言测试
voice_input.py          主程序
run.ps1                 PowerShell 启动入口
start_voice_input.vbs   无控制台窗口启动入口
```

开发、测试和发布说明见 [CONTRIBUTING.md](CONTRIBUTING.md)，版本记录见 [CHANGELOG.md](CHANGELOG.md)。

## License

项目代码和原创奶蛙素材使用 [MIT License](LICENSE)。第三方素材继续遵循各自许可证，详情见 `assets/` 中的声明文件。
