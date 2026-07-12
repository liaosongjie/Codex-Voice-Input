# Contributing

感谢参与改进 Codex Voice Input。

## 开发环境

- Windows 10 或 Windows 11
- Python 3.10 或更高版本

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 运行测试

```powershell
.\.venv\Scripts\python.exe -X utf8 -m py_compile voice_input.py tests\test_voice_input.py
.\.venv\Scripts\python.exe -X utf8 -m tests.test_voice_input
```

Pull Request 会在 Windows 上使用 Python 3.10 和 3.13 自动运行同一套检查。

## 贡献要求

- 不提交 `models/`、`.venv/`、日志、个人设置或 API Key。
- 窗口操作相关修改不得改变用户已有的最大化或 Windows 分屏布局。
- 输入功能不得依赖或覆盖系统剪贴板。
- 新增语音命令、快捷键或窗口匹配行为时补充断言测试。
- 新增图片、音频或字体时提供来源和许可证声明。
- 将用户功能与维护者工具放在对应目录，不在仓库根目录增加临时脚本。

## 维护者工具

从根目录的 `奶蛙.mp4` 重新生成宠物动画和音效：

```powershell
.\.venv\Scripts\python.exe scripts\maintainer\build_pet_assets.py
```

生成用户发布包：

```powershell
.\scripts\maintainer\package_release.ps1
```

发布包只包含运行所需文件、用户脚本、资产、许可证和使用说明，不包含测试或维护工具。
