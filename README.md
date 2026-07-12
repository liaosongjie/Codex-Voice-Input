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

关闭“直接输入当前窗口”后，可使用语音选择目标：

```text
打开 Codex 输入
打开 VS Code 输入
打开 项目名称 然后输入帮我检查这个文件发送
```

## 常见问题

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
