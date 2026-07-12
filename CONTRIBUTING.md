# Contributing

感谢参与改进 Codex 中文语音输入。

## 开发环境

- Windows 10 或 Windows 11
- Python 3.10 或更高版本
- 建议使用项目自带的 `.venv`

安装依赖：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m py_compile voice_input.py 测试实时退格.py
.\.venv\Scripts\python.exe 测试实时退格.py
```

## 提交要求

- 不提交 `models/`、`.venv/`、日志或个人 `用户设置.json`。
- 窗口操作相关修改需要验证不会取消最大化或 Windows 分屏布局。
- 输入相关修改不得依赖或覆盖系统剪贴板。
- 新增语音命令或快捷键解析行为时补充断言测试。
- 涉及贴图素材时保留对应来源和许可证。
