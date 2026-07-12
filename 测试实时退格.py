import ctypes
import queue
import numpy as np
from pynput import keyboard

from voice_input import (
    INPUT,
    OfflineStreamingSession,
    build_live_edit,
    is_ignored_window_metadata,
    is_allowed_code_target_window,
    keyboard_event_token,
    looks_like_tool_feedback_fragment,
    looks_like_voice_feedback_echo,
    looks_like_window_candidate_selection,
    open_target_command_requests_input,
    launch_candidates,
    find_window_number_command,
    format_hotkey,
    join_transcript_parts,
    parse_show_window_candidates_command,
    parse_open_target_command,
    parse_hotkey,
    parse_window_number_command,
    parse_voice_command,
    parse_wake_command,
    resolve_live_voice_command,
    score_window_match,
    strip_voice_feedback_echo,
    WindowInfo,
    utf16_code_units,
)


cases = [
    ("我要的是热点", "我要的是我点"),
    ("你好呀", "你好"),
    ("打开文件", "打开文件夹"),
    ("", "你好"),
]

for old_text, new_text in cases:
    edit = build_live_edit(old_text, new_text)
    print(f"旧: {old_text}")
    print(f"新: {new_text}")
    print(f"退格: {edit.delete_count} 次")
    print(f"补入: {edit.suffix!r}")
    print()

commands = [
    "把这个功能做好，发送",
    "这个回车动作怎么做",
    "总结一下提交",
    "发送",
]

assert not looks_like_voice_feedback_echo("已打开 codex语音输入，请说要输入的内容")
assert strip_voice_feedback_echo("窗口已打开等待输入您好你好你好") == "您好你好你好"
assert not looks_like_voice_feedback_echo("正在输入到 Windows 输入体验，说发送结束")
assert not looks_like_voice_feedback_echo("你好这是我要输入的正文")
assert looks_like_tool_feedback_fragment("窗口三目标窗口时切过去窗口随机频音，请说记号")
assert looks_like_voice_feedback_echo("窗口三目标窗口时切过去窗口随机频音，请说记号")
assert not looks_like_tool_feedback_fragment("窗口三这段内容帮我改小一点")
assert is_ignored_window_metadata("TextInputHost.exe", "Windows.UI.Core.CoreWindow", "Windows 输入体验")
assert is_ignored_window_metadata("pythonw.exe", "TkTopLevel", "Codex 中文语音输入")
assert not is_ignored_window_metadata("Code.exe", "Chrome_WidgetWin_1", "codex语音输入 - Visual Studio Code")
assert join_transcript_parts("你好", "世界") == "你好世界"
assert join_transcript_parts("OpenAI", "API") == "OpenAI API"
assert utf16_code_units("你A") == [20320, 65]
assert utf16_code_units("😀") == [55357, 56832]
assert ctypes.sizeof(INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
assert parse_hotkey("Ctrl+Alt+Space") == frozenset({"ctrl", "alt", "space"})
assert parse_hotkey("F8") == frozenset({"f8"})
assert parse_hotkey("Ctrl+Shift+M") == frozenset({"ctrl", "shift", "m"})
assert parse_hotkey("A") is None
assert parse_hotkey("Ctrl+Alt") is None
assert format_hotkey(frozenset({"shift", "ctrl", "m"})) == "Ctrl+Shift+M"
assert keyboard_event_token(keyboard.KeyCode.from_vk(0x4D)) == "m"
assert keyboard_event_token(keyboard.Key.f8) == "f8"


class FakeStream:
    def __init__(self):
        self.pending = False
        self.result = ""

    def accept_waveform(self, _sample_rate, samples):
        if np.any(samples):
            self.pending = True

    def input_finished(self):
        return None


class FakeRecognizer:
    def __init__(self):
        self.parts = ["第一句。", "第二句。"]
        self.part_index = 0

    def create_stream(self):
        return FakeStream()

    def is_ready(self, stream):
        return stream.pending

    def decode_stream(self, stream):
        stream.result = self.parts[self.part_index]
        stream.pending = False

    def get_result(self, stream):
        return stream.result

    def is_endpoint(self, stream):
        return bool(stream.result)

    def reset(self, stream):
        stream.result = ""
        self.part_index = min(self.part_index + 1, len(self.parts) - 1)


endpoint_events = queue.Queue()
endpoint_session = OfflineStreamingSession(FakeRecognizer(), endpoint_events)
endpoint_session.audio_queue.put(np.ones(160, dtype=np.float32))
endpoint_session.audio_queue.put(np.ones(160, dtype=np.float32))
endpoint_session.stop_event.set()
endpoint_session._decode_loop()
endpoint_payloads = []
while not endpoint_events.empty():
    endpoint_payloads.append(endpoint_events.get_nowait())
endpoint_transcripts = [payload for kind, payload in endpoint_payloads if kind == "transcript"]
assert endpoint_transcripts
assert sum(kind == "utterance_endpoint" for kind, _payload in endpoint_payloads) == 2
assert endpoint_transcripts[-1][1].text == "第一句。第二句。"

for text in commands:
    command = parse_voice_command(text)
    print(f"识别: {text}")
    print(f"正文: {command.text!r}")
    print(f"发送: {command.submit}")
    print()

live_cases = [
    ("把这个功能做好", "发送"),
    ("", "发送"),
    ("把这个功能做好", "把这个功能做好发送"),
]

for current_text, raw_text in live_cases:
    command = resolve_live_voice_command(raw_text, current_text, True)
    print(f"当前已输入: {current_text!r}")
    print(f"新识别: {raw_text!r}")
    print(f"实时目标正文: {command.text!r}")
    print(f"发送: {command.submit}")
    print()

wake_cases = [
    "打开 Codex 输入帮我总结这个文件发送",
    "切到浏览器然后输入搜索 sherpa onnx 实时语音发送",
    "在记事本写今天先把语音输入工具测完提交",
]

for text in wake_cases:
    command = parse_wake_command(text)
    print(f"唤醒识别: {text}")
    print(f"目标: {command.target_query if command else None!r}")
    print(f"正文: {command.text if command else None!r}")
    print(f"发送: {command.submit if command else None}")
    print()

open_cases = [
    "打开 code",
    "打开 condex",
    "打开后台输入",
    "打开后代输入",
    "打开 Codex 输入",
    "打开 codex语音输入窗口",
    "打开 codex语音速度",
    "语音输入打开 codex语音速度",
    "打开 context 语音输入",
    "打开 AI交易猎人对话框 输入",
    "打开 AI 交易猎人对话框 输入",
    "打开 AI 交易猎人",
    "打开口袋语音输入输入",
]

for text in open_cases:
    target = parse_open_target_command(text)
    print(f"打开识别: {text}")
    print(f"目标: {target!r}")
    print(f"要求输入: {open_target_command_requests_input(text)}")
    print()

assert parse_open_target_command("打开 code") == "code"
assert parse_open_target_command("打开 condex") == "condex"
assert parse_open_target_command("打开后台输入") == "后台"
assert parse_open_target_command("打开后代输入") == "后代"
assert parse_open_target_command("打开 Codex 输入") == "Codex"
assert parse_open_target_command("打开输入") is None
assert parse_open_target_command("打开语音输入") is None
assert parse_open_target_command("打开 codex语音输入窗口") == "codex语音输入"
assert parse_open_target_command("打开 codex语音速度") == "codex语音输入"
assert open_target_command_requests_input("打开 codex语音速度")
assert parse_open_target_command("语音输入打开 codex语音速度") == "codex语音输入"
assert open_target_command_requests_input("语音输入打开 codex语音速度")
assert parse_open_target_command("打开 context 语音输入") == "context 语音输入"
assert open_target_command_requests_input("打开 context 语音输入")
assert parse_open_target_command("打开 AI交易猎人对话框 输入") == "AI交易猎人"
assert open_target_command_requests_input("打开 AI交易猎人对话框 输入")
assert parse_open_target_command("打开 AI 交易猎人对话框 输入") == "AI 交易猎人"
assert open_target_command_requests_input("打开 AI 交易猎人对话框 输入")
assert parse_open_target_command("打开 AI 交易猎人") == "AI 交易猎人"
assert parse_open_target_command("打开口袋语音输入输入") == "口袋语音输入"
assert open_target_command_requests_input("打开口袋语音输入输入")
assert parse_wake_command("打开语音输入法设置") is None
assert parse_wake_command("打开语音输入法设置发送", require_submit=True) is None
assert parse_wake_command("打开 AI交易猎人 输入帮我测试") is not None
assert parse_open_target_command("打开 AI交易猎人 输入帮我测试") is None
assert parse_wake_command("打开 AI交易猎人输入法设置") is None
assert parse_show_window_candidates_command("打开窗口编号")
assert parse_show_window_candidates_command("请打开窗口编号")
assert parse_show_window_candidates_command("请选择窗口编号")
assert parse_window_number_command("打开窗口1") == 1
assert parse_window_number_command("打开窗口二") == 2
assert parse_window_number_command("选择3号") == 3
assert parse_window_number_command("窗口四") == 4
assert parse_window_number_command("二号") == 2
assert parse_window_number_command("第二个") == 2
assert parse_window_number_command("选二号") == 2
assert parse_window_number_command("2号") == 2
assert parse_window_number_command("请选择窗口编号一，编号一，窗口已打开，等待窗口打开打开窗口等待收入。您好你好你好") is None
assert find_window_number_command("窗口一") == 1
assert find_window_number_command("窗口一号") == 1
assert find_window_number_command("选第一个") == 1
assert find_window_number_command("把这里窗口一，A二交易别人。窗口二，指数画五。窗口三，提取视频音频。请说几号？窗口一") == 1
assert looks_like_window_candidate_selection("窗口一")
assert looks_like_window_candidate_selection("把这里窗口一，A二交易别人。窗口二，指数画五。窗口三，提取视频音频。请说几号？窗口一")
assert not looks_like_window_candidate_selection("窗口一号你好卡片缩小")
assert strip_voice_feedback_echo("窗口已打开等待输入您好你好你好") == "您好你好你好"

full = parse_wake_command("打开 code 输入帮我总结这个文件发送", require_submit=True)
assert full is not None
assert full.target_query == "code"
assert full.text == "帮我总结这个文件"
assert full.submit

precise = parse_wake_command("打开 codex语音输入 然后输入帮我总结这个文件发送", require_submit=True)
assert precise is not None
assert precise.target_query == "codex语音输入"
assert precise.text == "帮我总结这个文件"
assert precise.submit

right_window = WindowInfo(1, "codex语音输入 - Visual Studio Code", "Code.exe", "Chrome_WidgetWin_1")
wrong_window = WindowInfo(2, "其他项目 - Visual Studio Code", "Code.exe", "Chrome_WidgetWin_1")
assert score_window_match(right_window, "codex语音输入") > score_window_match(wrong_window, "codex语音输入")
assert is_allowed_code_target_window(WindowInfo(9, "Codex", "Codex.exe", "Chrome_WidgetWin_1"))
assert is_allowed_code_target_window(WindowInfo(10, "ChatGPT", "ChatGPT.exe", "Chrome_WidgetWin_1"))
assert is_allowed_code_target_window(right_window)

ai_window = WindowInfo(3, "ai交易插入 - Visual Studio Code", "Code.exe", "Chrome_WidgetWin_1")
voice_window = WindowInfo(4, "codex语音输入 - Visual Studio Code", "Code.exe", "Chrome_WidgetWin_1")
windows_input = WindowInfo(5, "Windows 输入体验", "TextInputHost.exe", "Windows.UI.Core.CoreWindow")
pet_window = WindowInfo(6, "Codex 中文语音输入", "pythonw.exe", "TkTopLevel")
chrome_window = WindowInfo(7, "纳米AI - 首页 - Google Chrome", "chrome.exe", "Chrome_WidgetWin_1")
explorer_window = WindowInfo(8, "codex语音输入 - 文件资源管理器", "explorer.exe", "CabinetWClass")
assert score_window_match(windows_input, "输入") == 0
assert score_window_match(windows_input, "codex语音输入") == 0
assert score_window_match(pet_window, "codex语音输入") == 0
assert score_window_match(chrome_window, "纳米AI") == 0
assert score_window_match(chrome_window, "打开窗口") == 0
assert score_window_match(explorer_window, "codex语音输入") == 0
assert launch_candidates("打开浏览器") == []
assert launch_candidates("打开 chrome") == []
assert score_window_match(ai_window, "ai交易插入") > score_window_match(voice_window, "ai交易插入")
assert score_window_match(ai_window, "ai交易") > score_window_match(voice_window, "ai交易")
assert score_window_match(ai_window, "AI交易猎人") > score_window_match(voice_window, "AI交易猎人")
assert score_window_match(ai_window, "AI 交易猎人") > score_window_match(voice_window, "AI 交易猎人")
assert score_window_match(voice_window, "codex语音输入") > score_window_match(ai_window, "codex语音输入")
assert score_window_match(voice_window, "codex语音速度") > score_window_match(ai_window, "codex语音速度")
assert score_window_match(voice_window, "context语音输入") > score_window_match(ai_window, "context语音输入")
assert score_window_match(voice_window, "口袋语音输入") > score_window_match(ai_window, "口袋语音输入")
