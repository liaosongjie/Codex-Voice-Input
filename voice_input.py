from __future__ import annotations

import base64
import ctypes
import json
import os
import queue
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
import traceback
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pyautogui
import sounddevice as sd
import tkinter as tk
from openai import OpenAI
from pynput import keyboard, mouse
from tkinter import messagebox, ttk

try:
    import winsound
except ImportError:
    winsound = None


BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)
APP_VERSION = "0.3.1"
ASSETS_DIR = BASE_DIR / "assets"
MODELS_DIR = BASE_DIR / "models"
DEFAULT_OFFLINE_MODEL_NAME = (
    "sherpa-onnx-x-asr-480ms-streaming-zipformer-transducer-"
    "zh-en-punct-int8-2026-06-05"
)
DEFAULT_OFFLINE_MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    f"{DEFAULT_OFFLINE_MODEL_NAME}.tar.bz2"
)
DEFAULT_OFFLINE_MODEL_DIR = MODELS_DIR / DEFAULT_OFFLINE_MODEL_NAME

DEFAULT_API_MODEL = "gpt-4o-mini-transcribe"
DEFAULT_API_PROMPT = "请转写为简体中文。保留 Codex、Python、PowerShell、API、JSON 等技术词。"
DEFAULT_HOTKEY = "Ctrl+Alt+Space"
DEFAULT_MOUSE_BUTTON = "后退侧键 (X1)"
MOUSE_BUTTON_OPTIONS = ("后退侧键 (X1)", "前进侧键 (X2)")
SAMPLE_RATE = 16000
CHANNELS = 1
DEBUG_LOG_PATH = BASE_DIR / "运行调试.log"
DEBUG_LOG_BACKUP_PATH = BASE_DIR / "运行调试.log.1"
DEBUG_LOG_MAX_BYTES = 2 * 1024 * 1024
USER_SETTINGS_PATH = BASE_DIR / "用户设置.json"
PET_ASSET_DIR = ASSETS_DIR / "pet"
PET_SPRITE_PATH = ASSETS_DIR / "oneko.gif"
PET_FRAME_SIZE = 180
LEGACY_SPRITE_FRAME_SIZE = 32
LEGACY_SPRITE_SCALE = 3
PET_ANIMATION_INTERVAL_MS = 125
PET_TRANSPARENT_COLOR = "#00ff7f"
PET_COLLAPSED_GEOMETRY = "200x200+60+120"
PET_EXPANDED_GEOMETRY = "660x250"
PET_DETAIL_GEOMETRY = "660x450"
PET_SETTINGS_GEOMETRY = "700x790"
WINDOW_CANDIDATE_LIMIT = 4
LEGACY_PET_SPRITE_SETS = {
    "idle": [(-3, -3), (-3, -3), (-3, -2)],
    "listen": [(-7, -3), (-1, -2), (-1, -3)],
    "target": [(-5, 0), (-6, 0), (-7, 0)],
    "busy": [(-3, 0), (-3, -1), (-4, -2), (-4, -3)],
    "error": [(-7, -3), (-3, -2)],
}

MODE_OFFLINE = "离线实时"
MODE_API = "OpenAI API"

if os.name == "nt":
    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.c_long),
            ("dy", ctypes.c_long),
            ("mouseData", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", ctypes.c_ulong),
            ("wParamL", ctypes.c_ushort),
            ("wParamH", ctypes.c_ushort),
        ]

    class INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("mi", MOUSEINPUT),
            ("ki", KEYBDINPUT),
            ("hi", HARDWAREINPUT),
        ]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("union",)
        _fields_ = [("type", ctypes.c_ulong), ("union", INPUT_UNION)]

    USER32 = ctypes.windll.user32
    KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    USER32.GetForegroundWindow.restype = ctypes.c_void_p
    USER32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    USER32.GetWindowThreadProcessId.restype = ctypes.c_ulong
    USER32.IsWindow.argtypes = [ctypes.c_void_p]
    USER32.IsWindow.restype = ctypes.c_bool
    USER32.IsWindowVisible.argtypes = [ctypes.c_void_p]
    USER32.IsWindowVisible.restype = ctypes.c_bool
    USER32.IsIconic.argtypes = [ctypes.c_void_p]
    USER32.IsIconic.restype = ctypes.c_bool
    USER32.EnumWindows.argtypes = [WNDENUMPROC, ctypes.c_void_p]
    USER32.EnumWindows.restype = ctypes.c_bool
    USER32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    USER32.GetClassNameW.restype = ctypes.c_int
    USER32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    USER32.GetWindowTextW.restype = ctypes.c_int
    USER32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
    USER32.GetWindowRect.restype = ctypes.c_bool
    USER32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    USER32.ShowWindow.restype = ctypes.c_bool
    USER32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    USER32.SetForegroundWindow.restype = ctypes.c_bool
    USER32.BringWindowToTop.argtypes = [ctypes.c_void_p]
    USER32.BringWindowToTop.restype = ctypes.c_bool
    USER32.SetActiveWindow.argtypes = [ctypes.c_void_p]
    USER32.SetActiveWindow.restype = ctypes.c_void_p
    USER32.SetFocus.argtypes = [ctypes.c_void_p]
    USER32.SetFocus.restype = ctypes.c_void_p
    USER32.AttachThreadInput.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_bool]
    USER32.AttachThreadInput.restype = ctypes.c_bool
    USER32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
    USER32.SendInput.restype = ctypes.c_uint
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        USER32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        USER32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        USER32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        USER32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    else:
        USER32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        USER32.GetWindowLongW.restype = ctypes.c_long
        USER32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
        USER32.SetWindowLongW.restype = ctypes.c_long
    USER32.SetWindowPos.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    USER32.SetWindowPos.restype = ctypes.c_bool
    KERNEL32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    KERNEL32.CreateMutexW.restype = ctypes.c_void_p
    KERNEL32.GetLastError.restype = ctypes.c_ulong
    KERNEL32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
    KERNEL32.OpenProcess.restype = ctypes.c_void_p
    KERNEL32.GetCurrentThreadId.restype = ctypes.c_ulong
    KERNEL32.QueryFullProcessImageNameW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    KERNEL32.QueryFullProcessImageNameW.restype = ctypes.c_bool
    KERNEL32.CloseHandle.argtypes = [ctypes.c_void_p]
    KERNEL32.CloseHandle.restype = ctypes.c_bool
else:
    USER32 = None
    KERNEL32 = None
    WNDENUMPROC = None
    RECT = None
    INPUT = None

ERROR_ALREADY_EXISTS = 183
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MAX_SENDINPUT_EVENTS = 120
SINGLE_INSTANCE_MUTEX_NAME = "Local\\CodexChineseVoiceInputPet"

IGNORED_TARGET_PROCESSES = {
    "cmd.exe",
    "conhost.exe",
    "inputapp.exe",
    "openconsole.exe",
    "powershell.exe",
    "pwsh.exe",
    "tabtip.exe",
    "textinputhost.exe",
    "windowsterminal.exe",
}

IGNORED_TARGET_CLASSES = {
    "ConsoleWindowClass",
    "CASCADIA_HOSTING_WINDOW_CLASS",
}

IGNORED_TARGET_TITLE_EXACT = {
    "codex 中文语音输入",
    "codex 语音宠物",
    "windows 输入体验",
    "windows input experience",
}

IGNORED_TARGET_TITLE_PARTS = (
    "codex 中文语音输入",
    "codex 语音宠物",
    "microsoft text input application",
    "语音宠物",
    "windows 输入体验",
    "windows input experience",
)

CODE_TARGET_PROCESSES = {
    "code.exe",
    "chatgpt.exe",
    "codex.exe",
    "codexapp.exe",
    "openai.codex.exe",
    "cursor.exe",
    "trae.exe",
    "windsurf.exe",
    "vscodium.exe",
}
PET_STATES = ("idle", "listen", "target", "busy", "error")
PET_SOUND_PATHS = {
    state: PET_ASSET_DIR / "sounds" / f"{state}.wav"
    for state in ("listen", "target", "busy", "error")
}
PET_LAUGH_SOUND_PATH = PET_ASSET_DIR / "sounds" / "laugh.wav"

HOTKEY_MODIFIERS = ("ctrl", "alt", "shift", "win")
HOTKEY_TOKEN_ALIASES = {
    "control": "ctrl",
    "ctl": "ctrl",
    "option": "alt",
    "windows": "win",
    "cmd": "win",
    "command": "win",
    "escape": "esc",
    "return": "enter",
    "pgup": "page_up",
    "pageup": "page_up",
    "pgdn": "page_down",
    "pagedown": "page_down",
}
HOTKEY_NAMED_KEYS = {
    "space",
    "enter",
    "tab",
    "esc",
    "pause",
    "insert",
    "delete",
    "home",
    "end",
    "page_up",
    "page_down",
    "up",
    "down",
    "left",
    "right",
}

CODE_LAUNCH_COMMANDS = {
    "code",
    "cursor",
    "trae",
    "windsurf",
}

SW_HIDE = 0
SW_RESTORE = 9
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
VOICE_FEEDBACK_SCRIPT_TEMPLATE = """
$ErrorActionPreference = 'SilentlyContinue'
$text = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{text_b64}'))
try {{
    Add-Type -AssemblyName System.Speech
    $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {{
        $s.SelectVoiceByHints(
            [System.Speech.Synthesis.VoiceGender]::NotSet,
            [System.Speech.Synthesis.VoiceAge]::NotSet,
            0,
            [System.Globalization.CultureInfo]'zh-CN'
        )
    }} catch {{}}
    $s.Rate = 1
    $s.Volume = 100
    $s.Speak($text)
    exit
}} catch {{}}
try {{
    $v = New-Object -ComObject SAPI.SpVoice
    $v.Volume = 100
    $v.Rate = 1
    [void]$v.Speak($text)
}} catch {{}}
"""


def _rotate_debug_log_if_needed() -> None:
    if not DEBUG_LOG_PATH.exists() or DEBUG_LOG_PATH.stat().st_size < DEBUG_LOG_MAX_BYTES:
        return
    try:
        if DEBUG_LOG_BACKUP_PATH.exists():
            DEBUG_LOG_BACKUP_PATH.unlink()
        DEBUG_LOG_PATH.replace(DEBUG_LOG_BACKUP_PATH)
    except OSError:
        pass


def debug_log(message: str) -> None:
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        _rotate_debug_log_if_needed()
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as log:
            log.write(f"{timestamp} {message}\n")
    except Exception:
        pass


def debug_log_exception(context: str, exc: BaseException) -> None:
    details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
    debug_log(f"{context}: {details}")


def utf16_code_units(text: str) -> list[int]:
    encoded = text.encode("utf-16-le", errors="surrogatepass")
    return [int.from_bytes(encoded[index : index + 2], "little") for index in range(0, len(encoded), 2)]


def send_unicode_text(text: str) -> bool:
    if not text:
        return True
    if USER32 is None or INPUT is None:
        return False

    code_units = utf16_code_units(text)
    units_per_batch = max(1, MAX_SENDINPUT_EVENTS // 2)
    input_size = ctypes.sizeof(INPUT)
    for offset in range(0, len(code_units), units_per_batch):
        chunk = code_units[offset : offset + units_per_batch]
        inputs = (INPUT * (len(chunk) * 2))()
        for index, code_unit in enumerate(chunk):
            down = inputs[index * 2]
            down.type = INPUT_KEYBOARD
            down.ki.wVk = 0
            down.ki.wScan = code_unit
            down.ki.dwFlags = KEYEVENTF_UNICODE
            down.ki.time = 0
            down.ki.dwExtraInfo = 0

            up = inputs[index * 2 + 1]
            up.type = INPUT_KEYBOARD
            up.ki.wVk = 0
            up.ki.wScan = code_unit
            up.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            up.ki.time = 0
            up.ki.dwExtraInfo = 0
        sent = USER32.SendInput(len(inputs), inputs, input_size)
        if sent != len(inputs):
            debug_log(f"send_unicode_text_failed sent={sent} expected={len(inputs)}")
            return False
        time.sleep(0.01)
    return True


def load_user_settings() -> dict[str, object]:
    try:
        data = json.loads(USER_SETTINGS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def settings_bool(settings: dict[str, object], key: str, default: bool) -> bool:
    value = settings.get(key)
    return value if isinstance(value, bool) else default


def settings_text(settings: dict[str, object], key: str, default: str) -> str:
    value = settings.get(key)
    return value if isinstance(value, str) and value else default


def settings_number(settings: dict[str, object], key: str, default: float, minimum: float, maximum: float) -> float:
    value = settings.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return default
    return max(minimum, min(maximum, float(value)))


def normalize_hotkey_token(token: str) -> str:
    token = token.strip().lower().replace("-", "_").replace(" ", "_")
    return HOTKEY_TOKEN_ALIASES.get(token, token)


def parse_hotkey(text: str) -> Optional[frozenset[str]]:
    parts = [normalize_hotkey_token(part) for part in text.split("+") if part.strip()]
    if not parts or len(parts) != len(set(parts)):
        return None

    for token in parts:
        is_function_key = bool(re.fullmatch(r"f(?:[1-9]|1[0-9]|2[0-4])", token))
        is_character = len(token) == 1 and token.isalnum()
        if token not in HOTKEY_MODIFIERS and token not in HOTKEY_NAMED_KEYS and not is_function_key and not is_character:
            return None

    non_modifiers = [token for token in parts if token not in HOTKEY_MODIFIERS]
    if len(non_modifiers) != 1:
        return None
    if len(parts) == 1 and not re.fullmatch(r"f(?:[1-9]|1[0-9]|2[0-4])", non_modifiers[0]):
        return None
    return frozenset(parts)


def format_hotkey(tokens: frozenset[str]) -> str:
    labels = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win", "page_up": "PageUp", "page_down": "PageDown"}
    ordered = [token for token in HOTKEY_MODIFIERS if token in tokens]
    ordered.extend(sorted(token for token in tokens if token not in HOTKEY_MODIFIERS))
    return "+".join(labels.get(token, token.upper() if re.fullmatch(r"f\d+", token) else token.title()) for token in ordered)


def keyboard_event_token(key) -> Optional[str]:
    modifier_map = {
        keyboard.Key.ctrl_l: "ctrl",
        keyboard.Key.ctrl_r: "ctrl",
        keyboard.Key.alt_l: "alt",
        keyboard.Key.alt_r: "alt",
        keyboard.Key.shift_l: "shift",
        keyboard.Key.shift_r: "shift",
        keyboard.Key.cmd_l: "win",
        keyboard.Key.cmd_r: "win",
    }
    if key in modifier_map:
        return modifier_map[key]
    if isinstance(key, keyboard.KeyCode):
        vk = getattr(key, "vk", None)
        if isinstance(vk, int) and (0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A):
            return chr(vk).lower()
        if key.char:
            return normalize_hotkey_token(key.char)
    name = getattr(key, "name", None)
    return normalize_hotkey_token(name) if name else None


def mouse_button_from_setting(value: str):
    return mouse.Button.x2 if value == MOUSE_BUTTON_OPTIONS[1] else mouse.Button.x1


def get_foreground_hwnd() -> Optional[int]:
    if USER32 is None:
        return None
    hwnd = USER32.GetForegroundWindow()
    return int(hwnd) if hwnd else None


def is_valid_hwnd(hwnd: Optional[int]) -> bool:
    return bool(hwnd and USER32 is not None and USER32.IsWindow(ctypes.c_void_p(hwnd)))


def window_process_id(hwnd: Optional[int]) -> Optional[int]:
    if not is_valid_hwnd(hwnd):
        return None
    pid = ctypes.c_ulong()
    USER32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    return int(pid.value)


def window_class_name(hwnd: Optional[int]) -> str:
    if not is_valid_hwnd(hwnd):
        return ""
    buffer = ctypes.create_unicode_buffer(256)
    USER32.GetClassNameW(ctypes.c_void_p(hwnd), buffer, len(buffer))
    return buffer.value


def window_title(hwnd: Optional[int]) -> str:
    if not is_valid_hwnd(hwnd):
        return ""
    buffer = ctypes.create_unicode_buffer(512)
    USER32.GetWindowTextW(ctypes.c_void_p(hwnd), buffer, len(buffer))
    return buffer.value


def is_window_visible(hwnd: Optional[int]) -> bool:
    return bool(is_valid_hwnd(hwnd) and USER32.IsWindowVisible(ctypes.c_void_p(hwnd)))


def is_ignored_window_metadata(process: str, class_name: str, title: str) -> bool:
    process = process.lower().strip()
    class_name = class_name.strip()
    class_lower = class_name.lower()
    title_lower = title.lower().strip()

    if process in IGNORED_TARGET_PROCESSES:
        return True

    ignored_classes = {item.lower() for item in IGNORED_TARGET_CLASSES}
    if class_name in IGNORED_TARGET_CLASSES or class_lower in ignored_classes:
        return True

    if title_lower in IGNORED_TARGET_TITLE_EXACT:
        return True
    if any(part in title_lower for part in IGNORED_TARGET_TITLE_PARTS):
        return True
    if process == "pythonw.exe" and class_name == "TkTopLevel" and "codex" in title_lower:
        return True

    return title_lower.startswith("c:\\windows\\system32\\cmd") or title_lower.startswith("管理员: c:\\windows\\system32\\cmd")


def process_image_name(pid: Optional[int]) -> str:
    if not pid or KERNEL32 is None:
        return ""

    handle = KERNEL32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""

    try:
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if KERNEL32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
        return ""
    finally:
        KERNEL32.CloseHandle(handle)


def process_basename(pid: Optional[int]) -> str:
    image = process_image_name(pid)
    return Path(image).name.lower() if image else ""


def is_allowed_code_target_window(window: WindowInfo) -> bool:
    process = window.process.lower().strip()
    class_name = window.class_name.lower().strip()
    title = window.title.lower().strip()
    if is_ignored_window_metadata(process, class_name, title):
        return False
    if process in CODE_TARGET_PROCESSES:
        return True
    return class_name == "chrome_widgetwin_1" and "visual studio code" in title


def visible_code_windows() -> list[WindowInfo]:
    return [window for window in enum_windows() if is_allowed_code_target_window(window)]


def enum_windows() -> list[WindowInfo]:
    if USER32 is None or WNDENUMPROC is None:
        return []

    windows: list[WindowInfo] = []

    def callback(hwnd, _lparam):
        hwnd_int = int(hwnd)
        title = window_title(hwnd_int).strip()
        pid = window_process_id(hwnd_int)
        if title and pid != os.getpid() and is_window_visible(hwnd_int) and not is_ignored_target_window(hwnd_int):
            windows.append(
                WindowInfo(
                    hwnd=hwnd_int,
                    title=title,
                    process=process_basename(pid),
                    class_name=window_class_name(hwnd_int),
                )
            )
        return True

    USER32.EnumWindows(WNDENUMPROC(callback), None)
    return windows


def window_info_from_hwnd(hwnd: Optional[int]) -> Optional[WindowInfo]:
    if not is_valid_hwnd(hwnd):
        return None
    pid = window_process_id(hwnd)
    if not pid or pid == os.getpid() or not is_window_visible(hwnd):
        return None
    return WindowInfo(
        hwnd=int(hwnd),
        title=window_title(hwnd).strip(),
        process=process_basename(pid),
        class_name=window_class_name(hwnd),
    )


def is_ignored_target_window(hwnd: Optional[int]) -> bool:
    if not is_valid_hwnd(hwnd):
        return True

    pid = window_process_id(hwnd)
    return is_ignored_window_metadata(process_basename(pid), window_class_name(hwnd), window_title(hwnd))


def focus_window(hwnd: Optional[int]) -> bool:
    if not is_valid_hwnd(hwnd):
        return False
    if USER32.IsIconic(ctypes.c_void_p(hwnd)):
        USER32.ShowWindow(ctypes.c_void_p(hwnd), SW_RESTORE)
        time.sleep(0.05)
    foreground = get_foreground_hwnd()
    current_thread = KERNEL32.GetCurrentThreadId() if KERNEL32 is not None else 0
    target_thread = USER32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), None)
    foreground_thread = USER32.GetWindowThreadProcessId(ctypes.c_void_p(foreground), None) if foreground else 0
    attached_threads: list[int] = []
    for thread_id in {int(target_thread), int(foreground_thread)}:
        if thread_id and thread_id != int(current_thread):
            if USER32.AttachThreadInput(ctypes.c_ulong(current_thread), ctypes.c_ulong(thread_id), True):
                attached_threads.append(thread_id)
    try:
        USER32.BringWindowToTop(ctypes.c_void_p(hwnd))
        USER32.SetForegroundWindow(ctypes.c_void_p(hwnd))
    finally:
        for thread_id in attached_threads:
            USER32.AttachThreadInput(ctypes.c_ulong(current_thread), ctypes.c_ulong(thread_id), False)
    time.sleep(0.15)
    return get_foreground_hwnd() == hwnd


def set_window_activation(hwnd: Optional[int], allow_activation: bool) -> None:
    if not is_valid_hwnd(hwnd) or USER32 is None:
        return

    hwnd_ptr = ctypes.c_void_p(hwnd)
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        style = USER32.GetWindowLongPtrW(hwnd_ptr, GWL_EXSTYLE)
        if allow_activation:
            style = (style & ~WS_EX_NOACTIVATE) | WS_EX_TOOLWINDOW
        else:
            style = style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        USER32.SetWindowLongPtrW(hwnd_ptr, GWL_EXSTYLE, style)
    else:
        style = USER32.GetWindowLongW(hwnd_ptr, GWL_EXSTYLE)
        if allow_activation:
            style = (style & ~WS_EX_NOACTIVATE) | WS_EX_TOOLWINDOW
        else:
            style = style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        USER32.SetWindowLongW(hwnd_ptr, GWL_EXSTYLE, style)
    USER32.SetWindowPos(
        hwnd_ptr,
        ctypes.c_void_p(0),
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
    )


def set_window_no_activate(hwnd: Optional[int]) -> None:
    set_window_activation(hwnd, allow_activation=False)


def click_likely_input_area(hwnd: Optional[int]) -> bool:
    if not is_valid_hwnd(hwnd) or USER32 is None or RECT is None:
        return False

    rect = RECT()
    if not USER32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect)):
        return False

    width = max(0, rect.right - rect.left)
    height = max(0, rect.bottom - rect.top)
    if width < 160 or height < 120:
        return False

    x = rect.left + width // 2
    y = rect.top + int(height * 0.88)
    try:
        pyautogui.click(x, y)
        time.sleep(0.08)
        return True
    except Exception:
        return False


def hide_own_console_window() -> None:
    if USER32 is None:
        return

    hwnd = get_foreground_hwnd()
    if not hwnd or not is_ignored_target_window(hwnd):
        return

    pid = window_process_id(hwnd)
    if process_basename(pid) in {"cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe"}:
        USER32.ShowWindow(ctypes.c_void_p(hwnd), SW_HIDE)


def acquire_single_instance_mutex() -> Optional[int]:
    if KERNEL32 is None:
        return None

    ctypes.set_last_error(0)
    handle = KERNEL32.CreateMutexW(None, 1, SINGLE_INSTANCE_MUTEX_NAME)
    last_error = ctypes.get_last_error()
    if not handle:
        return None
    if last_error == ERROR_ALREADY_EXISTS:
        KERNEL32.CloseHandle(handle)
        return 0
    return int(handle)


@dataclass
class TranscriptResult:
    text: str
    source: str
    audio_path: Optional[Path] = None


@dataclass
class LiveEdit:
    delete_count: int
    suffix: str


@dataclass
class VoiceCommand:
    text: str
    submit: bool = False


@dataclass
class WakeCommand:
    target_query: str
    text: str
    submit: bool = False


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    process: str
    class_name: str


WINDOW_NUMBER_WORDS = ("一", "二", "三", "四")
WINDOW_TITLE_SUFFIXES = (
    "Visual Studio Code",
    "Codex",
    "Cursor",
    "Trae",
    "Windsurf",
    "VSCodium",
)


def speech_window_title(window: WindowInfo) -> str:
    title = window.title.strip()
    if not title:
        return "未命名窗口"

    parts = [part.strip() for part in re.split(r"\s+[-–—]\s+", title) if part.strip()]
    if parts and parts[-1].lower() in {suffix.lower() for suffix in WINDOW_TITLE_SUFFIXES}:
        parts = parts[:-1]

    if len(parts) >= 2 and re.search(r"\.[a-zA-Z0-9]{1,8}$", parts[0]):
        title = parts[-1]
    elif parts:
        title = parts[-1] if len(parts[-1]) <= 32 else parts[0]

    return title[:32] + "…" if len(title) > 32 else title


SUBMIT_COMMANDS = (
    "发送",
    "提交",
    "回车",
    "发出去",
    "发出",
    "发一下",
    "提交一下",
    "发送一下",
)

COMMAND_TRAILING_PUNCT = " ，。！？、；：,.!?;:"

WAKE_PREFIXES = (
    "打开",
    "唤醒",
    "切到",
    "切换到",
    "转到",
    "找到",
    "进入",
    "在",
)

OPEN_ONLY_PREFIXES = (
    "打开",
    "唤醒",
    "切到",
    "切换到",
    "转到",
    "找到",
    "进入",
)

INPUT_MARKERS = (
    "然后输入",
    "然后写入",
    "然后写",
    "并输入",
    "再输入",
    "帮我输入",
    "帮我写",
    "输入",
    "写入",
    "写上",
    "写",
)

EXPLICIT_INPUT_MARKERS = tuple(marker for marker in INPUT_MARKERS if marker not in {"输入", "写入", "写上", "写"})
OPEN_INPUT_SUFFIXES = ("然后输入", "开始输入", "请输入")

ASR_CONFUSION_REPLACEMENTS = (
    ("语音速度", "语音输入"),
    ("语音速读", "语音输入"),
    ("语音书入", "语音输入"),
    ("语音树入", "语音输入"),
    ("语音输录", "语音输入"),
    ("语音属入", "语音输入"),
)

GENERIC_TARGET_QUERIES = {
    "输入",
    "输入框",
    "语音输入",
    "文本输入",
    "文字输入",
    "输入体验",
    "windows输入",
    "windows输入体验",
}

TARGET_WORD_SUFFIXES = (
    "这个窗口",
    "对话框",
    "聊天框",
    "输入框",
    "窗口",
    "软件",
    "应用",
    "程序",
    "里面",
    "里",
    "中",
    "一下",
)

TARGET_ALIAS_TERMS = {
    "codex": (
        "codex",
        "condex",
        "code x",
        "codes",
        "chatgpt",
        "openai",
        "visual studio code",
        "vscode",
        "code.exe",
        "cursor",
        "cursor.exe",
        "windsurf",
        "trae",
    ),
    "condex": (
        "codex",
        "condex",
        "code x",
        "codes",
        "visual studio code",
        "vscode",
        "code.exe",
        "cursor",
        "cursor.exe",
    ),
    "context": (
        "codex",
        "condex",
        "code x",
        "codes",
        "visual studio code",
        "vscode",
        "code.exe",
        "cursor",
        "cursor.exe",
    ),
    "contexts": (
        "codex",
        "condex",
        "code x",
        "codes",
        "visual studio code",
        "vscode",
        "code.exe",
        "cursor",
        "cursor.exe",
    ),
    "contest": (
        "codex",
        "condex",
        "code x",
        "codes",
        "visual studio code",
        "vscode",
        "code.exe",
        "cursor",
        "cursor.exe",
    ),
    "扣得": ("codex", "code x", "codes", "visual studio code", "vscode", "code.exe"),
    "酷得": ("codex", "code x", "codes", "visual studio code", "vscode", "code.exe"),
    "口袋": ("codex", "code x", "codes", "visual studio code", "vscode", "code.exe", "cursor.exe"),
    "扣袋": ("codex", "code x", "codes", "visual studio code", "vscode", "code.exe", "cursor.exe"),
    "空袋": ("codex", "code x", "codes", "visual studio code", "vscode", "code.exe", "cursor.exe"),
    "空代": ("codex", "code x", "codes", "visual studio code", "vscode", "code.exe", "cursor.exe"),
    "后台": ("codex", "code x", "codes", "visual studio code", "vscode", "code.exe", "cursor.exe"),
    "后代": ("codex", "code x", "codes", "visual studio code", "vscode", "code.exe", "cursor.exe"),
    "候代": ("codex", "code x", "codes", "visual studio code", "vscode", "code.exe", "cursor.exe"),
    "后台输入": ("codex", "code x", "codes", "visual studio code", "vscode", "code.exe", "cursor.exe"),
    "后代输入": ("codex", "code x", "codes", "visual studio code", "vscode", "code.exe", "cursor.exe"),
    "代输入": ("codex", "code x", "codes", "visual studio code", "vscode", "code.exe", "cursor.exe"),
    "代码": ("codex", "visual studio code", "vscode", "code.exe", "cursor", "cursor.exe"),
    "vscode": ("visual studio code", "vscode", "code.exe"),
    "vs code": ("visual studio code", "vscode", "code.exe"),
    "code": ("visual studio code", "vscode", "code.exe", "codex"),
    "浏览器": ("chrome.exe", "chrome", "msedge.exe", "edge", "firefox.exe", "browser"),
    "谷歌": ("chrome.exe", "chrome", "google chrome"),
    "chrome": ("chrome.exe", "chrome", "google chrome"),
    "edge": ("msedge.exe", "edge", "microsoft edge"),
    "记事本": ("notepad.exe", "notepad", "记事本"),
    "微信": ("wechat.exe", "weixin", "微信"),
    "企业微信": ("wxwork.exe", "企业微信"),
    "文件资源管理器": ("explorer.exe", "文件资源管理器"),
    "资源管理器": ("explorer.exe", "文件资源管理器"),
}

LAUNCH_ALIASES = {
    "codex": ("code", "cursor", "windsurf", "trae"),
    "condex": ("code", "cursor"),
    "context": ("code", "cursor"),
    "contexts": ("code", "cursor"),
    "contest": ("code", "cursor"),
    "扣得": ("code", "cursor"),
    "酷得": ("code", "cursor"),
    "口袋": ("code", "cursor"),
    "扣袋": ("code", "cursor"),
    "空袋": ("code", "cursor"),
    "空代": ("code", "cursor"),
    "后台": ("code", "cursor"),
    "后代": ("code", "cursor"),
    "候代": ("code", "cursor"),
    "后台输入": ("code", "cursor"),
    "后代输入": ("code", "cursor"),
    "代输入": ("code", "cursor"),
    "代码": ("code", "cursor"),
    "vscode": ("code",),
    "vs code": ("code",),
    "code": ("code",),
    "cursor": ("cursor",),
    "浏览器": ("chrome", "msedge", "firefox"),
    "谷歌": ("chrome",),
    "chrome": ("chrome",),
    "edge": ("msedge",),
    "记事本": ("notepad",),
    "文件资源管理器": ("explorer",),
    "资源管理器": ("explorer",),
}

COMMON_APP_PATHS = {
    "code": (
        "%LOCALAPPDATA%\\Programs\\Microsoft VS Code\\Code.exe",
        "%PROGRAMFILES%\\Microsoft VS Code\\Code.exe",
        "%PROGRAMFILES(X86)%\\Microsoft VS Code\\Code.exe",
    ),
    "cursor": (
        "%LOCALAPPDATA%\\Programs\\cursor\\Cursor.exe",
        "%PROGRAMFILES%\\Cursor\\Cursor.exe",
    ),
    "windsurf": (
        "%LOCALAPPDATA%\\Programs\\Windsurf\\Windsurf.exe",
        "%PROGRAMFILES%\\Windsurf\\Windsurf.exe",
    ),
    "trae": (
        "%LOCALAPPDATA%\\Programs\\Trae\\Trae.exe",
        "%PROGRAMFILES%\\Trae\\Trae.exe",
    ),
    "chrome": (
        "%PROGRAMFILES%\\Google\\Chrome\\Application\\chrome.exe",
        "%PROGRAMFILES(X86)%\\Google\\Chrome\\Application\\chrome.exe",
        "%LOCALAPPDATA%\\Google\\Chrome\\Application\\chrome.exe",
    ),
    "msedge": (
        "%PROGRAMFILES(X86)%\\Microsoft\\Edge\\Application\\msedge.exe",
        "%PROGRAMFILES%\\Microsoft\\Edge\\Application\\msedge.exe",
    ),
    "firefox": (
        "%PROGRAMFILES%\\Mozilla Firefox\\firefox.exe",
        "%PROGRAMFILES(X86)%\\Mozilla Firefox\\firefox.exe",
    ),
}


def common_prefix_len(left: str, right: str) -> int:
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[index] == right[index]:
        index += 1
    return index


def build_live_edit(old_text: str, new_text: str) -> LiveEdit:
    prefix_len = common_prefix_len(old_text, new_text)
    return LiveEdit(
        delete_count=len(old_text) - prefix_len,
        suffix=new_text[prefix_len:],
    )


def parse_voice_command(text: str) -> VoiceCommand:
    cleaned = clean_transcript(text)
    stripped = cleaned.rstrip(COMMAND_TRAILING_PUNCT)
    for command in sorted(SUBMIT_COMMANDS, key=len, reverse=True):
        if stripped == command:
            return VoiceCommand(text="", submit=True)
        if stripped.endswith(command):
            before = stripped[: -len(command)].rstrip(COMMAND_TRAILING_PUNCT)
            if before:
                return VoiceCommand(text=before, submit=True)
    return VoiceCommand(text=cleaned, submit=False)


def resolve_live_voice_command(raw_text: str, current_text: str, enabled: bool) -> VoiceCommand:
    command = parse_voice_command(raw_text) if enabled else VoiceCommand(clean_transcript(raw_text))
    if command.submit and not command.text and current_text:
        return VoiceCommand(text=current_text, submit=True)
    return command


def normalize_match_text(text: str) -> str:
    text = normalize_asr_confusions(text)
    text = text.lower()
    return re.sub(r"[\s\-_.,!?;:，。！？、；：'\"“”‘’（）()\[\]【】<>《》/\\|]+", "", text)


def compact_text_with_indices(text: str) -> tuple[str, list[int]]:
    compact_chars: list[str] = []
    raw_indices: list[int] = []
    for index, char in enumerate(normalize_asr_confusions(text).lower()):
        if re.match(r"[\s\-_.,!?;:，。！？、；：'\"“”‘’（）()\[\]【】<>《》/\\|]", char):
            continue
        compact_chars.append(char)
        raw_indices.append(index)
    return "".join(compact_chars), raw_indices


def normalize_asr_confusions(text: str) -> str:
    for wrong, right in ASR_CONFUSION_REPLACEMENTS:
        text = text.replace(wrong, right)
    return text


def clean_command_text(text: str) -> str:
    return normalize_asr_confusions(clean_transcript(text))


VOICE_FEEDBACK_PREFIXES = (
    "正在识别窗口",
    "窗口已打开等待输入",
    "窗口已打开等候输入",
    "窗口已打开等待收入",
    "窗口已打开",
    "打开窗口等待输入",
    "打开窗口等待收入",
    "等待窗口打开等待输入",
    "等待输入",
    "等待收入",
    "请选择窗口编号",
    "请选择窗口号",
    "请说几号",
    "已发送继续待命",
)


def remove_compact_prefix(text: str, prefix: str) -> str:
    compact, indices = compact_text_with_indices(text)
    compact_prefix = normalize_match_text(prefix)
    if not compact_prefix or not compact.startswith(compact_prefix):
        return text
    if len(indices) < len(compact_prefix):
        return ""
    end_index = indices[len(compact_prefix) - 1] + 1
    return text[end_index:].lstrip(COMMAND_TRAILING_PUNCT)


def strip_voice_feedback_echo(text: str) -> str:
    stripped = clean_transcript(text)
    changed = True
    while changed and stripped:
        changed = False
        for prefix in sorted(VOICE_FEEDBACK_PREFIXES, key=len, reverse=True):
            updated = remove_compact_prefix(stripped, prefix)
            if updated != stripped:
                stripped = updated.strip()
                changed = True
                break
    return stripped


def looks_like_voice_feedback_echo(text: str) -> bool:
    compact = normalize_match_text(text)
    if not compact:
        return False
    echo_parts = (
        "已打开",
        "请说要输入的内容",
        "正在输入到",
        "说发送结束",
        "已切到",
        "继续待命",
        "没找到",
        "找到多个窗口",
        "找到几个相近窗口",
        "目标窗口",
        "语音反馈正常",
        "我在听",
        "正在识别窗口",
        "请说几号",
        "窗口一",
        "窗口二",
        "窗口三",
        "窗口四",
        "目标窗口时切过去",
        "目标窗口切过去",
        "请说记号",
    )
    for part in echo_parts:
        compact_part = normalize_match_text(part)
        if compact == compact_part:
            return True
        if compact.startswith(compact_part) and len(compact) <= len(compact_part) + 2:
            return True
    if looks_like_tool_feedback_fragment(text):
        return True
    return False


def looks_like_tool_feedback_fragment(text: str) -> bool:
    compact = normalize_match_text(text)
    if not compact:
        return False
    markers = (
        "正在识别窗口",
        "目标窗口",
        "请说几号",
        "请说记号",
        "窗口已打开",
        "等待输入",
        "正在输入到",
    )
    if not any(normalize_match_text(marker) in compact for marker in markers):
        return False
    window_markers = ("窗口一", "窗口二", "窗口三", "窗口四")
    window_hits = sum(1 for marker in window_markers if normalize_match_text(marker) in compact)
    if window_hits:
        return True
    if any(normalize_match_text(marker) in compact for marker in ("请说几号", "请说记号", "窗口已打开", "正在识别窗口")):
        return True
    return normalize_match_text("目标窗口") in compact and len(compact) <= 28


def trim_to_command_prefix(text: str, prefixes: tuple[str, ...]) -> str:
    stripped = text.strip().lstrip(COMMAND_TRAILING_PUNCT)
    if any(stripped.startswith(prefix) for prefix in prefixes):
        return stripped

    matches = [index for prefix in prefixes if (index := stripped.find(prefix)) > 0]
    if not matches:
        return stripped
    return stripped[min(matches) :].lstrip(COMMAND_TRAILING_PUNCT)


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def longest_common_substring(left: str, right: str) -> str:
    if not left or not right:
        return ""

    best_start = 0
    best_len = 0
    lengths = [0] * (len(right) + 1)
    for left_index, left_char in enumerate(left, start=1):
        previous = 0
        for right_index, right_char in enumerate(right, start=1):
            current = lengths[right_index]
            if left_char == right_char:
                lengths[right_index] = previous + 1
                if lengths[right_index] > best_len:
                    best_len = lengths[right_index]
                    best_start = left_index - best_len
            else:
                lengths[right_index] = 0
            previous = current
    return left[best_start : best_start + best_len]


def fuzzy_title_score(compact_query: str, compact_title: str) -> int:
    if not compact_query or not compact_title or len(compact_query) < 3:
        return 0
    if compact_query in compact_title:
        return 120

    prefix_len = common_prefix_len(compact_query, compact_title)
    prefix = compact_query[:prefix_len]
    if prefix_len >= 4 or (prefix_len >= 3 and contains_cjk(prefix)):
        return 45 + min(prefix_len, 8) * 8

    shared = longest_common_substring(compact_query, compact_title)
    shared_len = len(shared)
    if shared_len >= 4 and contains_cjk(shared):
        return 35 + min(shared_len, 8) * 6
    if shared_len >= 2 and contains_cjk(shared) and len(compact_query) >= 4:
        return 25 + shared_len * 8
    return 0


def strip_target_query(text: str) -> str:
    target = clean_command_text(text).strip(COMMAND_TRAILING_PUNCT)
    changed = True
    while changed and target:
        changed = False
        for suffix in TARGET_WORD_SUFFIXES:
            if target.endswith(suffix):
                target = target[: -len(suffix)].strip(COMMAND_TRAILING_PUNCT)
                changed = True
    return target.strip()


def is_simple_app_query(target_query: str) -> bool:
    compact = normalize_match_text(target_query)
    simple_aliases = set(TARGET_ALIAS_TERMS) | set(LAUNCH_ALIASES) | {
        "codex",
        "condex",
        "context",
        "contexts",
        "contest",
        "code",
        "vscode",
        "vs code",
    }
    return bool(compact and compact in {normalize_match_text(item) for item in simple_aliases})


def is_generic_target_query(target_query: str) -> bool:
    compact = normalize_match_text(target_query)
    return compact in GENERIC_TARGET_QUERIES


def contains_input_marker_as_command(text: str) -> bool:
    for marker in sorted(INPUT_MARKERS, key=len, reverse=True):
        start = 0
        while True:
            index = text.find(marker, start)
            if index < 0:
                break
            before = strip_target_query(text[:index])
            if index > 0 and input_marker_allowed(text, index, marker, before):
                return True
            start = index + len(marker)
    return False


def marker_has_leading_separator(text: str, index: int) -> bool:
    return index > 0 and (text[index - 1].isspace() or text[index - 1] in COMMAND_TRAILING_PUNCT)


def is_embedded_input_marker(text: str, index: int, marker: str) -> bool:
    after = text[index + len(marker) :]
    return marker == "输入" and after.startswith(("法", "框", "体验"))


def input_marker_allowed(text: str, index: int, marker: str, before: str) -> bool:
    if marker in EXPLICIT_INPUT_MARKERS:
        return True
    if is_embedded_input_marker(text, index, marker):
        return False
    return bool(before and (is_simple_app_query(before) or marker_has_leading_separator(text, index)))


def parse_wake_command(text: str, require_submit: bool = False) -> Optional[WakeCommand]:
    cleaned = trim_to_command_prefix(clean_command_text(text), WAKE_PREFIXES)
    if not cleaned:
        return None

    stripped = cleaned.rstrip(COMMAND_TRAILING_PUNCT)
    prefix = next((item for item in sorted(WAKE_PREFIXES, key=len, reverse=True) if stripped.startswith(item)), None)
    if prefix is None:
        return None

    body = stripped[len(prefix) :].lstrip(COMMAND_TRAILING_PUNCT)
    marker_matches: list[tuple[int, int, str]] = []
    for marker in sorted(INPUT_MARKERS, key=len, reverse=True):
        priority = 1 if marker in EXPLICIT_INPUT_MARKERS else 0
        start = 0
        while True:
            index = body.find(marker, start)
            if index < 0:
                break
            if index > 0:
                before = strip_target_query(body[:index])
                if not input_marker_allowed(body, index, marker, before):
                    start = index + len(marker)
                    continue
                marker_priority = priority
                if priority == 0 and before and not is_simple_app_query(before):
                    marker_priority = -1
                marker_matches.append((marker_priority, index, marker))
            start = index + len(marker)

    if not marker_matches:
        return None

    _, marker_index, marker = sorted(marker_matches, key=lambda item: (-item[0], item[1] if item[0] >= 0 else -item[1]))[0]
    target_query = strip_target_query(body[:marker_index])
    if not target_query:
        return None

    command = parse_voice_command(body[marker_index + len(marker) :])
    if require_submit and not command.submit:
        return None
    if not command.text:
        return None

    return WakeCommand(target_query=target_query, text=command.text, submit=command.submit)


def parse_open_target_command(text: str) -> Optional[str]:
    cleaned = trim_to_command_prefix(clean_command_text(text), OPEN_ONLY_PREFIXES)
    if not cleaned:
        return None

    stripped = cleaned.rstrip(COMMAND_TRAILING_PUNCT)
    prefix = next((item for item in sorted(OPEN_ONLY_PREFIXES, key=len, reverse=True) if stripped.startswith(item)), None)
    if prefix is None:
        return None

    body = stripped[len(prefix) :].lstrip(COMMAND_TRAILING_PUNCT)
    for suffix in OPEN_INPUT_SUFFIXES:
        if body.endswith(suffix):
            body = body[: -len(suffix)].rstrip(COMMAND_TRAILING_PUNCT)
            break
    if body.endswith("输入"):
        before_input = body[: -len("输入")].rstrip(COMMAND_TRAILING_PUNCT)
        if is_simple_app_query(before_input) or before_input.endswith(("对话框", "聊天框", "输入框", "窗口", "输入")):
            body = before_input

    if not body or contains_input_marker_as_command(body):
        return None

    target_query = strip_target_query(body)
    if not target_query or is_generic_target_query(target_query):
        return None
    return target_query


def parse_show_window_candidates_command(text: str) -> bool:
    cleaned = trim_to_command_prefix(clean_command_text(text), OPEN_ONLY_PREFIXES).strip()
    if not cleaned:
        return False
    compact = normalize_match_text(cleaned.rstrip(COMMAND_TRAILING_PUNCT))
    return compact in {
        "打开窗口",
        "打开窗户",
        "打开窗口编号",
        "打开窗户编号",
        "请打开窗口",
        "请打开窗口编号",
        "请选择窗口",
        "请选择窗口编号",
        "选择窗口",
        "选择窗口编号",
        "窗口编号",
        "窗口",
    }


def find_window_number_command(text: str) -> Optional[int]:
    cleaned = strip_voice_feedback_echo(clean_command_text(text))
    if not cleaned:
        return None

    compact = normalize_match_text(cleaned.rstrip(COMMAND_TRAILING_PUNCT))
    if not compact:
        return None

    digit_pattern = r"[1-4一二三四]"
    patterns = (
        rf"(?:打开|选择|选|切到|进入)?(?:第)?(?:窗口|窗户|候选)({digit_pattern})(?:号)?",
        rf"(?:打开|选择|选|切到|进入)(?:第)?({digit_pattern})(?:号)?(?:窗口|窗户|候选)?",
        rf"(?:打开|选择|选|切到|进入)?(?:第)?({digit_pattern})(?:号|个|项|条)",
        rf"(?:打开|选择|选|切到|进入)?(?:第)?({digit_pattern})",
    )
    for pattern in patterns:
        match = re.search(pattern, compact)
        if match:
            digits = {"1": 1, "一": 1, "2": 2, "二": 2, "3": 3, "三": 3, "4": 4, "四": 4}
            return digits.get(match.group(1))
    return None


def parse_window_number_command(text: str) -> Optional[int]:
    cleaned = trim_to_command_prefix(clean_command_text(text), OPEN_ONLY_PREFIXES).strip()
    if not cleaned:
        return None
    stripped = cleaned.rstrip(COMMAND_TRAILING_PUNCT)
    compact = normalize_match_text(stripped)
    match = re.fullmatch(
        r"(?:打开|选择|选|切到|进入)?(?:第)?(?:窗口|窗户|候选)([1-4一二三四])(?:号)?",
        compact,
    )
    if match is None:
        match = re.fullmatch(
            r"(?:打开|选择|选|切到|进入)(?:第)?([1-4一二三四])(?:号)?(?:窗口|窗户|候选)?",
            compact,
        )
    if match is None:
        match = re.fullmatch(
            r"(?:打开|选择|选|切到|进入)?(?:第)?([1-4一二三四])(?:号|个|项|条)",
            compact,
        )
    if match is None:
        match = re.fullmatch(
            r"(?:打开|选择|选|切到|进入)?(?:第)?([1-4一二三四])",
            compact,
        )
    if not match:
        return None
    return find_window_number_command(stripped)


def looks_like_window_candidate_selection(text: str) -> bool:
    cleaned = strip_voice_feedback_echo(clean_command_text(text))
    compact = normalize_match_text(cleaned.rstrip(COMMAND_TRAILING_PUNCT))
    if not compact or find_window_number_command(cleaned) is None:
        return False
    if parse_window_number_command(cleaned) is not None:
        return True

    selection_markers = ("请说几号", "请选择窗口", "窗口编号", "打开窗口编号")
    if any(normalize_match_text(marker) in compact for marker in selection_markers):
        return True

    window_mentions = sum(1 for marker in ("窗口一", "窗口二", "窗口三", "窗口四") if normalize_match_text(marker) in compact)
    return window_mentions >= 2


def open_target_command_requests_input(text: str) -> bool:
    cleaned = clean_command_text(text).strip().rstrip(COMMAND_TRAILING_PUNCT)
    if cleaned.endswith(OPEN_INPUT_SUFFIXES):
        return True
    if cleaned.endswith("输入") and parse_open_target_command(text) is not None:
        return True

    target_query = parse_open_target_command(text)
    if target_query is None:
        return False
    if is_generic_target_query(target_query):
        return False
    return is_simple_app_query(target_query)


def looks_like_wake_command_prefix(text: str) -> bool:
    cleaned = clean_command_text(text).strip()
    if not cleaned:
        return False

    stripped = cleaned.rstrip(COMMAND_TRAILING_PUNCT)
    prefix = next((item for item in sorted(WAKE_PREFIXES, key=len, reverse=True) if stripped.startswith(item)), None)
    if prefix is None:
        return False

    body = stripped[len(prefix) :].lstrip(COMMAND_TRAILING_PUNCT).lower()
    for marker in sorted(INPUT_MARKERS, key=len, reverse=True):
        start = 0
        while True:
            index = body.find(marker, start)
            if index < 0:
                break
            if index > 0:
                before = strip_target_query(body[:index])
                if input_marker_allowed(body, index, marker, before):
                    return True
            start = index + len(marker)

    compact_body = normalize_match_text(body)
    for alias, values in TARGET_ALIAS_TERMS.items():
        if normalize_match_text(alias) in compact_body:
            return True
        if any(normalize_match_text(value) in compact_body for value in values):
            return True
    return False


def is_current_target_query(target_query: str) -> bool:
    compact = normalize_match_text(target_query)
    return compact in {"当前", "当前窗口", "当前输入框", "这里", "这边", "这个", "这个窗口", "这个输入框"}


def is_generic_window_query(target_query: str) -> bool:
    compact = normalize_match_text(target_query)
    return compact in {
        "窗口",
        "窗户",
        "编号",
        "窗口编号",
        "窗户编号",
        "打开窗口",
        "打开窗户",
        "选择窗口",
        "选择窗户",
        "代码窗口",
        "vscode窗口",
        "code窗口",
        "codex窗口",
    }


def window_match_terms(target_query: str) -> list[str]:
    lower_query = target_query.lower()
    compact_query = normalize_match_text(target_query)
    terms = [lower_query, compact_query]
    for alias, values in TARGET_ALIAS_TERMS.items():
        alias_lower = alias.lower()
        alias_compact = normalize_match_text(alias)
        if alias_lower in lower_query or alias_compact in compact_query:
            terms.extend(values)

    seen: set[str] = set()
    unique_terms: list[str] = []
    for term in terms:
        normalized = term.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_terms.append(normalized)
    return unique_terms


def target_query_tokens(target_query: str) -> list[str]:
    tokens: list[str] = []
    for raw in re.split(r"[\s\-_.,!?;:，。！？、；：'\"“”‘’（）()\[\]【】<>《》/\\|]+", target_query.lower()):
        token = normalize_match_text(raw)
        if token:
            tokens.append(token)

    compact_query = normalize_match_text(target_query)
    for alias in sorted(TARGET_ALIAS_TERMS, key=len, reverse=True):
        compact_alias = normalize_match_text(alias)
        if compact_alias and compact_alias in compact_query:
            tokens.append(compact_alias)
            compact_query = compact_query.replace(compact_alias, "")

    if compact_query:
        tokens.append(compact_query)

    seen: set[str] = set()
    unique_tokens: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            unique_tokens.append(token)
    return unique_tokens


def launch_candidates(target_query: str) -> list[str]:
    lower_query = target_query.lower()
    compact_query = normalize_match_text(target_query)
    candidates: list[str] = []
    for alias, commands in LAUNCH_ALIASES.items():
        alias_lower = alias.lower()
        alias_compact = normalize_match_text(alias)
        if alias_lower in lower_query or alias_compact in compact_query:
            candidates.extend(commands)

    seen: set[str] = set()
    unique_candidates: list[str] = []
    for command in candidates:
        if command in CODE_LAUNCH_COMMANDS and command not in seen:
            seen.add(command)
            unique_candidates.append(command)
    return unique_candidates


def resolve_launch_command(command: str) -> Optional[str]:
    if command not in CODE_LAUNCH_COMMANDS:
        return None

    direct = shutil.which(command)
    if direct:
        return direct

    for template in COMMON_APP_PATHS.get(command, ()):
        path = Path(os.path.expandvars(template))
        if path.exists():
            return str(path)
    return None


def launch_target_application(target_query: str) -> bool:
    for command in launch_candidates(target_query):
        executable = resolve_launch_command(command)
        if not executable:
            continue
        try:
            subprocess.Popen(
                [executable],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=True,
                creationflags=CREATE_NO_WINDOW,
            )
            return True
        except Exception:
            continue
    return False


def score_window_match(window: WindowInfo, target_query: str) -> int:
    if not is_allowed_code_target_window(window):
        return 0

    title = window.title.lower()
    process = window.process.lower()
    class_name = window.class_name.lower()
    haystack = f"{title} {process} {class_name}"
    compact_haystack = normalize_match_text(haystack)
    compact_title = normalize_match_text(title)
    compact_process = normalize_match_text(process)
    compact_query = normalize_match_text(target_query)
    score = 0
    score += fuzzy_title_score(compact_query, compact_title)

    for term in window_match_terms(target_query):
        compact_term = normalize_match_text(term)
        if term == process:
            score = max(score, 100)
        elif term and term in process:
            score = max(score, 90)
        elif term and term in title:
            score = max(score, 80)
        elif compact_term and compact_term in compact_haystack:
            score = max(score, 70)
        else:
            pieces = [piece for piece in re.split(r"\s+", term) if piece]
            if pieces and all(piece in haystack for piece in pieces):
                score = max(score, 55)

    token_hits = 0
    title_hits = 0
    for token in target_query_tokens(target_query):
        if not token:
            continue
        alias_values = TARGET_ALIAS_TERMS.get(token, ())
        alias_hit = any(normalize_match_text(value) in compact_haystack for value in alias_values)
        direct_hit = token in compact_haystack
        if direct_hit or alias_hit:
            token_hits += 1
            score += 18
        if token in compact_title:
            title_hits += 1
            score += 18
        else:
            fuzzy_token_score = fuzzy_title_score(token, compact_title)
            if fuzzy_token_score:
                title_hits += 1
                score += min(fuzzy_token_score, 65)
                if len(token) >= 4:
                    token_hits += 1

        if alias_hit and any(normalize_match_text(value) in compact_process for value in alias_values):
            score += 8

    if token_hits >= 2:
        score += 45
    if title_hits >= 1 and any(
        normalize_match_text(value) in compact_process
        for alias in ("codex", "condex", "context", "contexts", "contest", "code", "代码", "扣得", "酷得", "后台")
        for value in TARGET_ALIAS_TERMS.get(alias, ())
    ):
        score += 35

    return score


def clean_transcript(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([，。！？、；：,.!?;:])", r"\1", text)
    text = re.sub(r"([（【《])\s+", r"\1", text)
    text = re.sub(r"\s+([）】》])", r"\1", text)
    return text.strip()


def join_transcript_parts(prefix: str, suffix: str) -> str:
    prefix = clean_transcript(prefix)
    suffix = clean_transcript(suffix)
    if not prefix:
        return suffix
    if not suffix:
        return prefix
    if prefix[-1].isascii() and suffix[0].isascii() and prefix[-1].isalnum() and suffix[0].isalnum():
        return f"{prefix} {suffix}"
    return prefix + suffix


def safe_online_result(recognizer, stream) -> str:
    try:
        return clean_transcript(recognizer.get_result(stream))
    except (IndexError, RuntimeError):
        return ""


def offline_model_ready() -> bool:
    required = (
        "tokens.txt",
        "encoder.int8.onnx",
        "decoder.onnx",
        "joiner.int8.onnx",
        "bpe.model",
    )
    return all((DEFAULT_OFFLINE_MODEL_DIR / name).exists() for name in required)


def safe_extract_tar(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    base = destination.resolve()
    with tarfile.open(archive, "r:bz2") as tar:
        for member in tar.getmembers():
            target = (base / member.name).resolve()
            try:
                target.relative_to(base)
            except ValueError:
                raise RuntimeError(f"Unsafe archive member: {member.name}")
        tar.extractall(base)


class WavRecorder:
    def __init__(self, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS):
        self.sample_rate = sample_rate
        self.channels = channels
        self._frames: list[bytes] = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()
        self._last_status_text = ""

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._frames = []
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=self._capture,
            )
            self._stream.start()

    def stop(self) -> Path:
        with self._lock:
            if self._stream is None:
                raise RuntimeError("当前没有录音")
            stream = self._stream
            self._stream = None

        stream.stop()
        stream.close()
        if self._last_status_text:
            debug_log(f"api_audio_status {self._last_status_text}")

        fd, path = tempfile.mkstemp(prefix="codex_voice_", suffix=".wav")
        os.close(fd)
        wav_path = Path(path)
        with wave.open(str(wav_path), "wb") as wav:
            wav.setnchannels(self.channels)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(b"".join(self._frames))
        return wav_path

    def _capture(self, indata, frames, time_info, status) -> None:
        if status:
            self._last_status_text = str(status)
            return
        self._frames.append(indata.tobytes())


class OfflineStreamingSession:
    def __init__(self, recognizer, events: queue.Queue, sample_rate: int = SAMPLE_RATE):
        self.recognizer = recognizer
        self.events = events
        self.sample_rate = sample_rate
        self.audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self.stop_event = threading.Event()
        self.reset_event = threading.Event()
        self.discard_result_event = threading.Event()
        self.stream = recognizer.create_stream()
        self.input_stream: Optional[sd.InputStream] = None
        self.worker = threading.Thread(target=self._decode_loop, daemon=True)
        self.mute_until = 0.0
        self.committed_text = ""
        self._last_status_text = ""

    def start(self) -> None:
        self.input_stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._capture,
        )
        self.input_stream.start()
        self.worker.start()

    def stop(self, discard_result: bool = False) -> None:
        if discard_result:
            self.discard_result_event.set()
        self.stop_event.set()
        if discard_result:
            self._drain_audio_queue()
        if self.input_stream is not None:
            self.input_stream.stop()
            self.input_stream.close()
            self.input_stream = None
        if self._last_status_text:
            debug_log(f"offline_audio_status {self._last_status_text}")

    def reset(self) -> None:
        self.reset_event.set()

    def mute_for(self, seconds: float) -> None:
        self.mute_until = max(self.mute_until, time.monotonic() + seconds)
        self.reset()

    def _capture(self, indata, frames, time_info, status) -> None:
        if self.stop_event.is_set():
            return
        if status:
            self._last_status_text = str(status)
        if time.monotonic() < self.mute_until:
            return
        mono = np.asarray(indata[:, 0], dtype=np.float32).copy()
        self.audio_queue.put(mono)

    def _drain_audio_queue(self) -> None:
        while True:
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                return

    def _decode_ready(self) -> bool:
        decoded = False
        while self.recognizer.is_ready(self.stream):
            self.recognizer.decode_stream(self.stream)
            decoded = True
        return decoded

    def _decode_loop(self) -> None:
        last_text = ""
        stream_has_audio = False
        stream_has_decoded = False
        try:
            while not self.stop_event.is_set() or (
                not self.discard_result_event.is_set() and not self.audio_queue.empty()
            ):
                if self.stop_event.is_set() and self.discard_result_event.is_set():
                    self._drain_audio_queue()
                    return
                if self.reset_event.is_set():
                    self._drain_audio_queue()
                    self.recognizer.reset(self.stream)
                    last_text = ""
                    self.committed_text = ""
                    stream_has_audio = False
                    stream_has_decoded = False
                    self.reset_event.clear()
                    self.events.put(("offline_reset", self))
                    continue

                try:
                    samples = self.audio_queue.get(timeout=0.05)
                except queue.Empty:
                    samples = None

                if self.stop_event.is_set() and self.discard_result_event.is_set():
                    self._drain_audio_queue()
                    return

                if samples is not None:
                    self.stream.accept_waveform(self.sample_rate, samples)
                    stream_has_audio = True

                if self._decode_ready():
                    stream_has_decoded = True
                if not stream_has_audio or not stream_has_decoded:
                    continue
                segment_text = safe_online_result(self.recognizer, self.stream)
                text = join_transcript_parts(self.committed_text, segment_text)
                if text and text != last_text:
                    last_text = text
                    if not self.discard_result_event.is_set():
                        self.events.put(("partial", (self, text)))

                if self.recognizer.is_endpoint(self.stream):
                    if segment_text:
                        self.committed_text = text
                    self.recognizer.reset(self.stream)
                    last_text = self.committed_text
                    stream_has_audio = False
                    stream_has_decoded = False
                    if segment_text:
                        debug_log(f"offline_endpoint committed_len={len(self.committed_text)}")
                    if segment_text and not self.discard_result_event.is_set() and self.committed_text:
                        self.events.put(("partial", (self, self.committed_text)))
                    if segment_text and not self.discard_result_event.is_set():
                        self.events.put(("utterance_endpoint", self))

            if self.discard_result_event.is_set():
                return

            tail = np.zeros(int(0.5 * self.sample_rate), dtype=np.float32)
            self.stream.accept_waveform(self.sample_rate, tail)
            self.stream.input_finished()
            self._decode_ready()
            final_text = join_transcript_parts(
                self.committed_text, safe_online_result(self.recognizer, self.stream)
            )
            self.events.put(("transcript", (self, TranscriptResult(final_text, source="offline"))))
        except Exception as exc:
            debug_log_exception("offline_decode_failed", exc)
            self.events.put(("error", exc))


class VoiceInputApp(tk.Tk):
    def __init__(self):
        hide_own_console_window()
        super().__init__()
        self.title("Codex 中文语音输入")
        self.geometry(PET_COLLAPSED_GEOMETRY)
        self.minsize(96, 96)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        if os.name == "nt":
            try:
                self.wm_attributes("-transparentcolor", PET_TRANSPARENT_COLOR)
            except tk.TclError:
                pass

        self.api_recorder = WavRecorder()
        self.offline_recognizer = None
        self.offline_session: Optional[OfflineStreamingSession] = None
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()

        self.active_mode: Optional[str] = None
        self.busy = False
        self.hotkey_pressed = False
        self.pressed_hotkey_tokens: set[str] = set()
        self.listener: Optional[keyboard.Listener] = None
        self.mouse_listener: Optional[mouse.Listener] = None
        self.mouse_hotkey_pressed = False
        self.speech_lock = threading.Lock()
        self.speech_generation = 0
        self.last_external_hwnd: Optional[int] = None
        self.paste_target_hwnd: Optional[int] = None

        self.user_settings = load_user_settings()
        saved_mode = settings_text(self.user_settings, "mode", "")
        default_mode = saved_mode if saved_mode in {MODE_OFFLINE, MODE_API} else (MODE_OFFLINE if offline_model_ready() else MODE_API)
        self.mode_var = tk.StringVar(value=default_mode)
        self.api_key_var = tk.StringVar(value=os.environ.get("OPENAI_API_KEY", ""))
        self.api_model_var = tk.StringVar(value=settings_text(self.user_settings, "api_model", DEFAULT_API_MODEL))
        self.plain_mode_var = tk.BooleanVar(value=settings_bool(self.user_settings, "plain_mode", False))
        self.voice_feedback_var = tk.BooleanVar(value=settings_bool(self.user_settings, "voice_feedback", True))
        self.sound_effects_var = tk.BooleanVar(value=settings_bool(self.user_settings, "sound_effects", False))
        self.laugh_sound_var = tk.BooleanVar(value=settings_bool(self.user_settings, "laugh_sound", False))
        self.sound_volume_var = tk.DoubleVar(
            value=settings_number(self.user_settings, "sound_volume", 70, 0, 100)
        )
        self.sound_volume_label_var = tk.StringVar(value=f"{round(self.sound_volume_var.get())}%")
        self.sound_cache: dict[tuple[Path, int], Path] = {}
        self.laugh_sound_until = 0.0
        self.auto_start_var = tk.BooleanVar(value=settings_bool(self.user_settings, "auto_start", False))
        self.mouse_hotkey_var = tk.BooleanVar(value=settings_bool(self.user_settings, "mouse_hotkey", False))
        saved_hotkey = settings_text(self.user_settings, "hotkey", DEFAULT_HOTKEY)
        self.hotkey_tokens = parse_hotkey(saved_hotkey) or parse_hotkey(DEFAULT_HOTKEY) or frozenset({"ctrl", "alt", "space"})
        self.hotkey_var = tk.StringVar(value=format_hotkey(self.hotkey_tokens))
        saved_mouse_button = settings_text(self.user_settings, "mouse_button", DEFAULT_MOUSE_BUTTON)
        if saved_mouse_button not in MOUSE_BUTTON_OPTIONS:
            saved_mouse_button = DEFAULT_MOUSE_BUTTON
        self.mouse_button_var = tk.StringVar(value=saved_mouse_button)
        self.mouse_hotkey_enabled = self.mouse_hotkey_var.get()
        self.mouse_hotkey_button = mouse_button_from_setting(saved_mouse_button)
        self.shortcut_status_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value=f"准备就绪。快捷键：{format_hotkey(self.hotkey_tokens)}")
        self.timer_var = tk.StringVar(value="00:00")
        self.partial_var = tk.StringVar(value="")
        self.candidates_text: Optional[tk.Text] = None
        self.partial_text: Optional[tk.Text] = None
        self.offline_model_var = tk.StringVar(value="")
        self.started_at: Optional[float] = None
        self.live_inserted_text = ""
        self.last_live_update_at = 0.0
        self.voice_submit_var = tk.BooleanVar(value=settings_bool(self.user_settings, "voice_submit", True))
        self.wake_command_var = tk.BooleanVar(value=settings_bool(self.user_settings, "wake_command", True))
        self.voice_submit_triggered = False
        self.offline_reset_pending = False
        self.ignore_partial_until = 0.0
        self.pending_target_hwnd: Optional[int] = None
        self.pending_target_title = ""
        self.pending_target_ready = False
        self.open_candidate_query: Optional[str] = None
        self.open_candidate_text = ""
        self.open_candidate_at = 0.0
        self.window_candidates: list[WindowInfo] = []
        self.window_candidate_query = ""
        self.window_candidate_at = 0.0
        self.last_window_lookup_ambiguous = False
        self.controls_visible = False
        self.settings_visible = False
        self.drag_start: Optional[tuple[int, int]] = None
        self.drag_origin: Optional[tuple[int, int]] = None
        self.pet_sprite_sheet: Optional[tk.PhotoImage] = None
        self.pet_frames: dict[str, list[tk.PhotoImage]] = {}
        self.pet_mood = "idle"
        self.pet_frame_index = 0

        self._build_ui()
        self._apply_no_activate_style()
        self._install_settings_traces()
        self._apply_shortcut_settings(show_status=False)
        self._sync_controls()
        self._start_hotkey_listener()
        debug_log(
            f"app_init version={APP_VERSION} "
            f"auto_start={self.auto_start_var.get()} "
            f"direct_input={self._plain_mode_enabled()} "
            f"hotkey={format_hotkey(self.hotkey_tokens)}"
        )
        self.after(100, self._poll_events)
        self.after(250, self._tick_timer)
        self.after(300, self._remember_external_window)
        self.after(700, self._auto_start_if_ready)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Product.TButton", padding=(8, 4), font=("Microsoft YaHei UI", 9))
        style.configure("Product.TLabelframe.Label", font=("Microsoft YaHei UI", 9, "bold"))
        self.configure(bg=PET_TRANSPARENT_COLOR)
        self.pet_frame = tk.Frame(self, bg=PET_TRANSPARENT_COLOR, padx=10, pady=10)
        self.pet_frame.pack(fill=tk.BOTH, expand=True)
        self.pet_frame.columnconfigure(1, weight=1)

        self._load_pet_frames()
        self.pet_label = tk.Label(
            self.pet_frame,
            image=self._current_pet_frame(),
            bg=PET_TRANSPARENT_COLOR,
            width=PET_FRAME_SIZE,
            height=PET_FRAME_SIZE,
            bd=0,
            highlightthickness=0,
        )
        self.pet_label.grid(row=0, column=0, rowspan=3, sticky="nw")
        self.pet_label.bind("<ButtonPress-1>", self._start_drag)
        self.pet_label.bind("<B1-Motion>", self._drag_window)
        self.pet_label.bind("<ButtonRelease-1>", self._pet_click_release)

        actions = tk.Frame(self.pet_frame, bg="#F6FBF7")
        actions.grid(row=0, column=1, sticky="ew")
        self.record_button = ttk.Button(actions, text="开始", width=7, style="Product.TButton", command=self.toggle_recording)
        self.record_button.pack(side=tk.LEFT)
        ttk.Button(actions, text="输入", width=7, style="Product.TButton", command=self.paste_text).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(actions, text="试听", width=7, style="Product.TButton", command=self.test_voice_feedback).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(actions, text="设置", width=7, style="Product.TButton", command=self._toggle_settings).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(actions, text="关闭", width=7, style="Product.TButton", command=self._on_close).pack(side=tk.RIGHT)
        self.controls_frame = actions

        self.status_label = tk.Label(
            self.pet_frame,
            textvariable=self.status_var,
            bg="#F6FBF7",
            fg="#38564A",
            font=("Microsoft YaHei UI", 9),
            width=52,
            height=2,
            anchor="nw",
            wraplength=390,
            justify=tk.LEFT,
        )
        self.status_label.grid(row=1, column=1, sticky="ew", pady=(5, 0))
        self.candidates_label = tk.Frame(
            self.pet_frame,
            bg="#F6FBF7",
        )
        self.candidates_label.grid(row=2, column=1, sticky="ew", pady=(4, 0))
        self.candidates_text = tk.Text(
            self.candidates_label,
            bg="#F6FBF7",
            fg="#1F332C",
            font=("Microsoft YaHei UI", 8),
            width=62,
            height=7,
            wrap=tk.WORD,
            bd=0,
            highlightthickness=0,
            relief=tk.FLAT,
            cursor="arrow",
        )
        self.candidates_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        candidates_scroll = ttk.Scrollbar(self.candidates_label, orient=tk.VERTICAL, command=self.candidates_text.yview)
        candidates_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.candidates_text.configure(yscrollcommand=candidates_scroll.set, state=tk.DISABLED)

        self.partial_label = tk.Frame(
            self.pet_frame,
            bg="#F6FBF7",
        )
        self.partial_label.grid(row=3, column=1, sticky="ew", pady=(2, 0))
        self.partial_text = tk.Text(
            self.partial_label,
            bg="#F6FBF7",
            fg="#6A7771",
            font=("Microsoft YaHei UI", 8),
            width=40,
            height=3,
            wrap=tk.WORD,
            bd=0,
            highlightthickness=0,
            relief=tk.FLAT,
            cursor="arrow",
        )
        self.partial_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        partial_scroll = ttk.Scrollbar(self.partial_label, orient=tk.VERTICAL, command=self.partial_text.yview)
        partial_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.partial_text.configure(yscrollcommand=partial_scroll.set, state=tk.DISABLED)

        self.settings_frame = ttk.Frame(self.pet_frame, padding=(4, 0, 4, 4))
        self.settings_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.settings_frame.columnconfigure(0, weight=1)

        recognition_frame = ttk.LabelFrame(self.settings_frame, text="识别与输入", style="Product.TLabelframe", padding=10)
        recognition_frame.grid(row=0, column=0, sticky="ew")
        recognition_frame.columnconfigure(1, weight=1)
        self.mode_box = ttk.Combobox(
            recognition_frame,
            textvariable=self.mode_var,
            values=(MODE_OFFLINE, MODE_API),
            state="readonly",
            width=12,
        )
        ttk.Label(recognition_frame, text="识别引擎").grid(row=0, column=0, sticky="w")
        self.mode_box.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.mode_box.bind("<<ComboboxSelected>>", self._on_mode_changed)
        self.download_button = ttk.Button(recognition_frame, text="安装模型", command=self.install_offline_model)
        self.download_button.grid(row=0, column=2, padx=(6, 0))

        ttk.Checkbutton(
            recognition_frame,
            text="直接输入当前窗口",
            variable=self.plain_mode_var,
            command=self._apply_plain_mode_settings,
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(recognition_frame, text="离线模式会边说边输入").grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
        ttk.Checkbutton(recognition_frame, text="说“发送”后回车", variable=self.voice_submit_var).grid(row=1, column=2, sticky="w", padx=(6, 0), pady=(6, 0))
        self.wake_check = ttk.Checkbutton(recognition_frame, text="语音选择目标窗口", variable=self.wake_command_var)
        self.wake_check.grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Checkbutton(recognition_frame, text="语音状态反馈", variable=self.voice_feedback_var).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
        ttk.Checkbutton(recognition_frame, text="启动后自动听", variable=self.auto_start_var).grid(row=2, column=2, sticky="w", padx=(6, 0), pady=(6, 0))
        ttk.Checkbutton(recognition_frame, text="宠物动作音效", variable=self.sound_effects_var).grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Button(recognition_frame, text="试听音效", command=self.test_pet_sound).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
        ttk.Checkbutton(recognition_frame, text="快捷键切换笑声", variable=self.laugh_sound_var).grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Button(recognition_frame, text="试听笑声", command=self.test_laugh_sound).grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
        ttk.Label(recognition_frame, text="音效音量").grid(row=5, column=0, sticky="w", pady=(7, 0))
        ttk.Scale(
            recognition_frame,
            from_=0,
            to=100,
            variable=self.sound_volume_var,
            command=self._on_sound_volume_changed,
        ).grid(row=5, column=1, sticky="ew", padx=(8, 6), pady=(7, 0))
        ttk.Label(recognition_frame, textvariable=self.sound_volume_label_var, width=5).grid(row=5, column=2, sticky="w", pady=(7, 0))

        shortcut_frame = ttk.LabelFrame(self.settings_frame, text="启动快捷键", style="Product.TLabelframe", padding=10)
        shortcut_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        shortcut_frame.columnconfigure(1, weight=1)
        ttk.Label(shortcut_frame, text="键盘").grid(row=0, column=0, sticky="w")
        self.hotkey_entry = ttk.Entry(shortcut_frame, textvariable=self.hotkey_var)
        self.hotkey_entry.grid(row=0, column=1, sticky="ew", padx=(8, 6))
        ttk.Button(shortcut_frame, text="应用", command=self._apply_shortcut_settings).grid(row=0, column=2)
        ttk.Checkbutton(
            shortcut_frame,
            text="启用鼠标侧键",
            variable=self.mouse_hotkey_var,
            command=lambda: self._apply_shortcut_settings(show_status=False),
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.mouse_button_box = ttk.Combobox(
            shortcut_frame,
            textvariable=self.mouse_button_var,
            values=MOUSE_BUTTON_OPTIONS,
            state="readonly",
            width=18,
        )
        self.mouse_button_box.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
        self.mouse_button_box.bind("<<ComboboxSelected>>", lambda event: self._apply_shortcut_settings(show_status=False))
        ttk.Label(shortcut_frame, textvariable=self.shortcut_status_var, foreground="#5A6B63").grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(5, 0)
        )

        service_frame = ttk.LabelFrame(self.settings_frame, text="模型与 API", style="Product.TLabelframe", padding=10)
        service_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        service_frame.columnconfigure(1, weight=1)
        ttk.Label(service_frame, text="API Key").grid(row=0, column=0, sticky="w")
        self.key_entry = ttk.Entry(service_frame, textvariable=self.api_key_var, show="*", width=18)
        self.key_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.model_box = ttk.Combobox(
            service_frame,
            textvariable=self.api_model_var,
            values=("gpt-4o-mini-transcribe", "gpt-4o-transcribe", "whisper-1"),
            width=18,
        )
        ttk.Label(service_frame, text="转写模型").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.model_box.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
        self.offline_status = ttk.Label(service_frame, textvariable=self.offline_model_var, wraplength=540)
        self.offline_status.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        history_frame = ttk.LabelFrame(self.settings_frame, text="最近识别文本", style="Product.TLabelframe", padding=10)
        history_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        history_frame.columnconfigure(0, weight=1)
        self.text = tk.Text(history_frame, wrap=tk.WORD, undo=True, font=("Microsoft YaHei UI", 9), height=5)
        self.text.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Button(history_frame, text="输入到当前窗口", command=self.paste_text).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(history_frame, text="清空", command=lambda: self.text.delete("1.0", tk.END)).grid(row=1, column=1, sticky="e", pady=(6, 0))
        ttk.Label(
            self.settings_frame,
            text=f"Codex 中文语音输入 v{APP_VERSION} · MIT License",
            foreground="#68756F",
        ).grid(row=4, column=0, sticky="e", pady=(8, 0))

        self.settings_frame.grid_remove()
        self._set_controls_visible(False)
        self._animate_pet()

    def _plain_mode_enabled(self) -> bool:
        return self.plain_mode_var.get()

    def _settings_snapshot(self) -> dict[str, object]:
        return {
            "mode": self.mode_var.get(),
            "api_model": self.api_model_var.get(),
            "plain_mode": self.plain_mode_var.get(),
            "voice_feedback": self.voice_feedback_var.get(),
            "sound_effects": self.sound_effects_var.get(),
            "laugh_sound": self.laugh_sound_var.get(),
            "sound_volume": round(self.sound_volume_var.get()),
            "auto_start": self.auto_start_var.get(),
            "voice_submit": self.voice_submit_var.get(),
            "wake_command": self.wake_command_var.get(),
            "mouse_hotkey": self.mouse_hotkey_var.get(),
            "mouse_button": self.mouse_button_var.get(),
            "hotkey": format_hotkey(self.hotkey_tokens),
        }

    def _save_user_settings(self, *_args) -> None:
        try:
            USER_SETTINGS_PATH.write_text(
                json.dumps(self._settings_snapshot(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            debug_log(f"save_settings_failed {exc!r}")

    def _install_settings_traces(self) -> None:
        variables = (
            self.mode_var,
            self.api_model_var,
            self.plain_mode_var,
            self.voice_feedback_var,
            self.sound_effects_var,
            self.laugh_sound_var,
            self.sound_volume_var,
            self.auto_start_var,
            self.voice_submit_var,
            self.wake_command_var,
        )
        for variable in variables:
            variable.trace_add("write", self._save_user_settings)

    def _apply_plain_mode_settings(self) -> None:
        if self._plain_mode_enabled():
            self.wake_command_var.set(False)
            self.window_candidates = []
            self._set_candidates_text("")
            self._set_status("直接输入：先点目标输入框，再开始说话。", "listen", speak=False)
        else:
            if self.mode_var.get() == MODE_API:
                self.mode_var.set(MODE_OFFLINE)
            self.wake_command_var.set(True)
            self._set_status("语音选窗口：说“打开 Codex 输入”。", "listen", speak=False)
        self._sync_controls()
        self._save_user_settings()

    def _on_mode_changed(self, _event=None) -> None:
        if self.mode_var.get() == MODE_API and not self._plain_mode_enabled():
            self.plain_mode_var.set(True)
            self.wake_command_var.set(False)
            self._set_status("API 模式使用直接输入：先点目标输入框。", "target")
        self._sync_controls()
        self._save_user_settings()

    def _apply_shortcut_settings(self, show_status: bool = True) -> bool:
        self.mouse_hotkey_enabled = self.mouse_hotkey_var.get()
        self.mouse_hotkey_button = mouse_button_from_setting(self.mouse_button_var.get())
        if hasattr(self, "mouse_button_box"):
            self.mouse_button_box.configure(state="readonly" if self.mouse_hotkey_enabled else tk.DISABLED)
        tokens = parse_hotkey(self.hotkey_var.get())
        if tokens is None:
            self.shortcut_status_var.set("格式无效。示例：Ctrl+Alt+Space、Ctrl+Shift+M 或 F8")
            self._save_user_settings()
            if show_status:
                self._set_status("快捷键格式无效。", "error")
            return False

        self.hotkey_tokens = tokens
        self.hotkey_var.set(format_hotkey(tokens))
        mouse_note = f"；{self.mouse_button_var.get()}" if self.mouse_hotkey_enabled else ""
        self.shortcut_status_var.set(f"当前：{format_hotkey(tokens)}{mouse_note}")
        self._save_user_settings()
        if show_status:
            self._set_status(f"快捷键已更新：{format_hotkey(tokens)}", "idle")
        return True

    def _sync_controls(self) -> None:
        ready = offline_model_ready()
        direct_mode = self._plain_mode_enabled()
        api_mode = self.mode_var.get() == MODE_API

        if direct_mode:
            self.wake_command_var.set(False)
        if api_mode:
            self.wake_command_var.set(False)

        self.offline_model_var.set(
            f"离线模型已安装：{DEFAULT_OFFLINE_MODEL_DIR.name}"
            if ready
            else "离线模型未安装；API 模式可直接使用。"
        )

        if api_mode:
            self.key_entry.configure(state=tk.NORMAL)
            self.model_box.configure(state="readonly")
        else:
            self.key_entry.configure(state=tk.DISABLED)
            self.model_box.configure(state=tk.DISABLED)

        self.wake_check.configure(state=tk.NORMAL if not direct_mode and not api_mode else tk.DISABLED)
        self.mouse_button_box.configure(state="readonly" if self.mouse_hotkey_var.get() else tk.DISABLED)

        self.download_button.configure(state=tk.DISABLED if ready or self.busy else tk.NORMAL)
        self.mode_box.configure(state=tk.DISABLED if self.active_mode or self.busy else "readonly")

    def _load_pet_frames(self) -> None:
        self.pet_frames = {}
        try:
            for mood in PET_STATES:
                paths = sorted((PET_ASSET_DIR / mood).glob("*.png"))
                if paths:
                    self.pet_frames[mood] = [tk.PhotoImage(file=str(path)) for path in paths]
            if self.pet_frames.get("idle"):
                idle_frames = self.pet_frames["idle"]
                for mood in PET_STATES:
                    self.pet_frames.setdefault(mood, idle_frames)
                return
        except Exception as exc:
            debug_log(f"pet_asset_load_failed {exc!r}")
            self.pet_frames = {}

        if not PET_SPRITE_PATH.exists():
            fallback = tk.PhotoImage(width=PET_FRAME_SIZE, height=PET_FRAME_SIZE)
            fallback.put("#73D7A7", to=(32, 32, 128, 128))
            self.pet_frames["idle"] = [fallback]
            return

        try:
            sprite_data = base64.b64encode(PET_SPRITE_PATH.read_bytes()).decode("ascii")
            self.pet_sprite_sheet = tk.PhotoImage(data=sprite_data, format="gif")
            for mood, sprites in LEGACY_PET_SPRITE_SETS.items():
                frames: list[tk.PhotoImage] = []
                for sprite_x, sprite_y in sprites:
                    frames.append(self._crop_pet_frame(sprite_x, sprite_y))
                self.pet_frames[mood] = frames
        except Exception:
            fallback = tk.PhotoImage(width=PET_FRAME_SIZE, height=PET_FRAME_SIZE)
            fallback.put("#73D7A7", to=(32, 32, 128, 128))
            self.pet_frames["idle"] = [fallback]

    def _crop_pet_frame(self, sprite_x: int, sprite_y: int) -> tk.PhotoImage:
        if self.pet_sprite_sheet is None:
            return tk.PhotoImage(width=LEGACY_SPRITE_FRAME_SIZE * LEGACY_SPRITE_SCALE, height=LEGACY_SPRITE_FRAME_SIZE * LEGACY_SPRITE_SCALE)

        source_x = abs(sprite_x) * LEGACY_SPRITE_FRAME_SIZE
        source_y = abs(sprite_y) * LEGACY_SPRITE_FRAME_SIZE
        frame = self.pet_sprite_sheet.copy(
            from_coords=(source_x, source_y, source_x + LEGACY_SPRITE_FRAME_SIZE, source_y + LEGACY_SPRITE_FRAME_SIZE)
        )
        return frame.copy(zoom=LEGACY_SPRITE_SCALE, subsample=1)

    def _current_pet_frame(self) -> tk.PhotoImage:
        frames = self.pet_frames.get(self.pet_mood) or self.pet_frames.get("idle")
        if not frames:
            fallback = tk.PhotoImage(width=PET_FRAME_SIZE, height=PET_FRAME_SIZE)
            self.pet_frames["idle"] = [fallback]
            frames = self.pet_frames["idle"]
        return frames[self.pet_frame_index % len(frames)]

    def _set_pet_mood(self, mood: str) -> None:
        if mood not in self.pet_frames:
            mood = "idle"
        if mood == self.pet_mood:
            return
        self.pet_mood = mood
        self.pet_frame_index = 0
        self._play_pet_sound(mood)
        if hasattr(self, "pet_label"):
            self.pet_label.configure(image=self._current_pet_frame())

    def _on_sound_volume_changed(self, _value=None) -> None:
        self.sound_volume_label_var.set(f"{round(self.sound_volume_var.get())}%")

    def _sound_path_at_current_volume(self, source: Path) -> Optional[Path]:
        volume = max(0, min(100, round(self.sound_volume_var.get())))
        if volume <= 0:
            return None
        if volume >= 100:
            return source
        key = (source, volume)
        cached = self.sound_cache.get(key)
        if cached is not None and cached.exists():
            return cached

        output_dir = Path(tempfile.gettempdir()) / "codex_voice_pet_sounds"
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / f"{source.stem}_{volume}.wav"
        try:
            with wave.open(str(source), "rb") as input_wave:
                params = input_wave.getparams()
                if params.sampwidth != 2:
                    return source
                samples = np.frombuffer(input_wave.readframes(params.nframes), dtype=np.int16)
            scaled = np.clip(samples.astype(np.float32) * (volume / 100), -32768, 32767).astype(np.int16)
            with wave.open(str(output), "wb") as output_wave:
                output_wave.setparams(params)
                output_wave.writeframes(scaled.tobytes())
            self.sound_cache[key] = output
            return output
        except (OSError, wave.Error) as exc:
            debug_log(f"pet_sound_volume_failed {exc!r}")
            return source

    def _play_pet_sound(self, mood: str, force: bool = False) -> None:
        if winsound is None or (not force and not self.sound_effects_var.get()):
            return
        if not force and time.monotonic() < self.laugh_sound_until:
            return
        path = PET_SOUND_PATHS.get(mood)
        if path is None or not path.exists():
            return
        path = self._sound_path_at_current_volume(path)
        if path is None:
            return
        try:
            winsound.PlaySound(
                str(path),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        except RuntimeError as exc:
            debug_log(f"pet_sound_failed {exc!r}")

    def test_pet_sound(self) -> None:
        previous_mood = self.pet_mood
        self._set_status("正在试听宠物动作音效。", "target")
        if not self.sound_effects_var.get() or previous_mood == "target":
            self._play_pet_sound("target", force=True)

    def _play_laugh_sound(self, force: bool = False) -> None:
        if winsound is None or (not force and not self.laugh_sound_var.get()) or not PET_LAUGH_SOUND_PATH.exists():
            return
        path = self._sound_path_at_current_volume(PET_LAUGH_SOUND_PATH)
        if path is None:
            return
        try:
            winsound.PlaySound(
                str(path),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
            self.laugh_sound_until = time.monotonic() + 1.8
        except RuntimeError as exc:
            debug_log(f"pet_laugh_sound_failed {exc!r}")

    def test_laugh_sound(self) -> None:
        previous_mood = self.pet_mood
        self._set_status("正在试听快捷键切换笑声。", "target")
        if not self.laugh_sound_var.get() or previous_mood == "target":
            self._play_laugh_sound(force=True)

    def _animate_pet(self) -> None:
        if hasattr(self, "pet_label"):
            self.pet_frame_index += 1
            self.pet_label.configure(image=self._current_pet_frame())
        self.after(PET_ANIMATION_INTERVAL_MS, self._animate_pet)

    def _apply_no_activate_style(self) -> None:
        if os.name != "nt":
            return
        self.update_idletasks()
        try:
            set_window_no_activate(int(self.winfo_id()))
        except Exception:
            return

    def _allow_settings_activation(self) -> None:
        if os.name != "nt":
            return
        self.update_idletasks()
        try:
            set_window_activation(int(self.winfo_id()), allow_activation=True)
            self.lift()
        except Exception:
            return

    def _set_text_widget(self, widget: Optional[tk.Text], text: str) -> None:
        if widget is None:
            return
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        if text:
            widget.insert(tk.END, text)
        widget.see(tk.END)
        widget.configure(state=tk.DISABLED)

    def _set_partial_text(self, text: str) -> None:
        self.partial_var.set(text)
        self._set_text_widget(self.partial_text, text)
        self._refresh_panel_layout()

    def _set_candidates_text(self, text: str) -> None:
        self._set_text_widget(self.candidates_text, text)
        self._refresh_panel_layout()

    def _refresh_panel_layout(self) -> None:
        if not getattr(self, "controls_visible", False) or not hasattr(self, "candidates_label"):
            return
        candidates_visible = bool(self.candidates_text and self.candidates_text.get("1.0", tk.END).strip())
        partial_visible = bool(self.partial_var.get().strip())
        if candidates_visible:
            self.candidates_label.grid()
        else:
            self.candidates_label.grid_remove()
        if partial_visible:
            self.partial_label.grid()
        else:
            self.partial_label.grid_remove()
        if self.settings_visible:
            self.geometry(PET_SETTINGS_GEOMETRY)
        elif candidates_visible or partial_visible:
            self.geometry(PET_DETAIL_GEOMETRY)
        else:
            self.geometry(PET_EXPANDED_GEOMETRY)

    def _set_status(
        self,
        text: str,
        mood: str = "idle",
        speak: bool = False,
        speak_ignore_seconds: float = 2.8,
        speak_reset_recognizer: bool = True,
    ) -> None:
        display_text = text
        if len(display_text) > 34:
            display_text = display_text[:33] + "…"
        self.status_var.set(display_text)
        self._set_pet_mood(mood)
        if speak:
            self._speak(
                text,
                ignore_seconds=speak_ignore_seconds,
                reset_recognizer=speak_reset_recognizer,
            )

    def _speak(
        self,
        text: str,
        ignore_seconds: float = 2.8,
        reset_recognizer: bool = True,
        force: bool = False,
    ) -> None:
        if (not force and not self.voice_feedback_var.get()) or not text:
            return
        self.ignore_partial_until = max(self.ignore_partial_until, time.monotonic() + ignore_seconds)
        if reset_recognizer and self.active_mode == MODE_OFFLINE and self.offline_session is not None:
            self.offline_session.mute_for(ignore_seconds)
        self.speech_generation += 1
        generation = self.speech_generation
        threading.Thread(target=self._speak_thread, args=(text, generation), daemon=True).start()

    def _speak_thread(self, text: str, generation: int) -> None:
        powershell = shutil.which("powershell") or shutil.which("powershell.exe")
        if not powershell:
            return
        text_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        script = VOICE_FEEDBACK_SCRIPT_TEMPLATE.format(text_b64=text_b64)
        encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        try:
            with self.speech_lock:
                if generation != self.speech_generation:
                    return
                subprocess.run(
                    [powershell, "-NoProfile", "-WindowStyle", "Hidden", "-EncodedCommand", encoded_script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW,
                    timeout=20,
                    check=False,
                )
        except Exception as exc:
            debug_log(f"voice_feedback_failed {exc!r}")

    def test_voice_feedback(self) -> None:
        self._set_status("正在试听语音反馈。", "listen")
        self._speak("语音反馈正常。", force=True, reset_recognizer=False)

    def _set_controls_visible(self, visible: bool) -> None:
        self.controls_visible = visible
        if visible:
            self.controls_frame.grid()
            self.status_label.grid()
            if self.settings_visible:
                self.settings_frame.grid()
            else:
                self.settings_frame.grid_remove()
            self._refresh_panel_layout()
        else:
            self.settings_visible = False
            self.controls_frame.grid_remove()
            self.status_label.grid_remove()
            self.candidates_label.grid_remove()
            self.partial_label.grid_remove()
            self.settings_frame.grid_remove()
            self.geometry(PET_COLLAPSED_GEOMETRY)
            self._apply_no_activate_style()

    def _pet_click_release(self, event) -> None:
        if self.drag_origin is None:
            return
        origin_x, origin_y = self.drag_origin
        moved = abs(event.x_root - origin_x) + abs(event.y_root - origin_y)
        self.drag_origin = None
        if moved <= 6:
            self._set_controls_visible(not self.controls_visible)

    def _toggle_settings(self) -> None:
        if not self.controls_visible:
            self._set_controls_visible(True)
            return
        self.settings_visible = not self.settings_visible
        if self.settings_visible:
            self.settings_frame.grid()
            self.geometry(PET_SETTINGS_GEOMETRY)
            self._allow_settings_activation()
        else:
            self.settings_frame.grid_remove()
            self.geometry(PET_EXPANDED_GEOMETRY)
            self._apply_no_activate_style()

    def _start_drag(self, event) -> None:
        self.drag_start = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())
        self.drag_origin = (event.x_root, event.y_root)

    def _drag_window(self, event) -> None:
        if self.drag_start is None:
            return
        offset_x, offset_y = self.drag_start
        self.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")

    def _auto_start_if_ready(self) -> None:
        debug_log(
            "auto_start_check "
            f"enabled={self.auto_start_var.get()} active_mode={self.active_mode} busy={self.busy}"
        )
        if not self.auto_start_var.get() or self.active_mode is not None or self.busy:
            return
        if self.mode_var.get() == MODE_OFFLINE and not offline_model_ready():
            self._set_status("自动听未启动：请先安装离线模型。", "error")
            return
        if self.mode_var.get() == MODE_API and not self.api_key_var.get().strip():
            self._set_status("自动听未启动：API 模式需要 API Key。", "error")
            return
        self.toggle_recording()

    def _start_hotkey_listener(self) -> None:
        def on_press(key):
            token = keyboard_event_token(key)
            if token:
                self.pressed_hotkey_tokens.add(token)
            if self.hotkey_tokens.issubset(self.pressed_hotkey_tokens) and not self.hotkey_pressed:
                self.hotkey_pressed = True
                self.events.put(("toggle", "keyboard"))

        def on_release(key):
            token = keyboard_event_token(key)
            if token:
                self.pressed_hotkey_tokens.discard(token)
            if not self.hotkey_tokens.issubset(self.pressed_hotkey_tokens):
                self.hotkey_pressed = False

        def on_click(_x, _y, button, pressed):
            if button != self.mouse_hotkey_button:
                return
            if pressed:
                if self.mouse_hotkey_enabled and not self.mouse_hotkey_pressed:
                    self.mouse_hotkey_pressed = True
                    debug_log(f"mouse_hotkey_toggle button={button}")
                    self.events.put(("toggle", "mouse"))
            else:
                self.mouse_hotkey_pressed = False

        errors: list[str] = []
        try:
            self.listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self.listener.daemon = True
            self.listener.start()
        except Exception as exc:
            errors.append(f"键盘快捷键：{exc}")

        try:
            self.mouse_listener = mouse.Listener(on_click=on_click)
            self.mouse_listener.daemon = True
            self.mouse_listener.start()
        except Exception as exc:
            errors.append(f"鼠标侧键：{exc}")

        if errors:
            self.status_var.set("快捷键启动失败：" + "；".join(errors))

    def _is_external_window(self, hwnd: Optional[int]) -> bool:
        window = window_info_from_hwnd(hwnd)
        return bool(window and is_allowed_code_target_window(window))

    def _remember_external_window(self) -> None:
        hwnd = get_foreground_hwnd()
        if self._is_external_window(hwnd):
            self.last_external_hwnd = hwnd
            if self._plain_mode_enabled():
                self.paste_target_hwnd = hwnd
        self.after(300, self._remember_external_window)

    def _select_paste_target(self) -> Optional[int]:
        hwnd = get_foreground_hwnd()
        if self._is_external_window(hwnd):
            return hwnd
        if self._is_external_window(self.last_external_hwnd):
            return self.last_external_hwnd
        return None

    def _window_matches(self, target_query: str, limit: int = WINDOW_CANDIDATE_LIMIT) -> list[tuple[int, WindowInfo]]:
        if is_generic_window_query(target_query):
            windows = visible_code_windows()
            windows.sort(key=lambda window: window.title.lower())
            return [(100, window) for window in windows[:limit]]

        matches: list[tuple[int, WindowInfo]] = []
        for window in enum_windows():
            score = score_window_match(window, target_query)
            if score:
                matches.append((score, window))
        matches.sort(key=lambda item: item[0], reverse=True)
        return matches[:limit]

    def _set_window_candidate_matches(self, target_query: str, matches: list[tuple[int, WindowInfo]]) -> None:
        self.window_candidates = [window for _, window in matches]
        self.window_candidate_query = target_query
        self.window_candidate_at = time.monotonic()
        lines = [f"{index}. {window.title}" for index, window in enumerate(self.window_candidates, start=1)]
        self._set_candidates_text("\n".join(lines))
        self._set_controls_visible(True)

    def _show_window_candidates(self, target_query: str) -> bool:
        matches = self._window_matches(target_query)
        debug_log(
            "show_window_candidates "
            f"query={target_query!r} matches={len(matches)} "
            f"visible={[window.title for window in visible_code_windows()]!r}"
        )
        if not matches:
            self.window_candidates = []
            self.window_candidate_query = ""
            self._set_candidates_text("")
            self._set_controls_visible(True)
            self._set_status("正在识别窗口，没找到可输入窗口。", "error", speak=True)
            return False

        self._set_window_candidate_matches(target_query, matches)
        spoken_windows = []
        for index, window in enumerate(self.window_candidates, start=1):
            number = WINDOW_NUMBER_WORDS[index - 1] if index <= len(WINDOW_NUMBER_WORDS) else str(index)
            spoken_windows.append(f"窗口{number}，{speech_window_title(window)}")
        speech = "正在识别窗口。" + "。".join(spoken_windows) + "。请说几号。"
        self._set_status("正在识别窗口，请说几号。", "target")
        self._speak(speech, ignore_seconds=max(3.0, min(8.0, len(speech) * 0.16)), reset_recognizer=True)
        return True

    def _open_window_candidate_for_input(self, number: int) -> bool:
        if number < 1 or number > len(self.window_candidates):
            self._set_status("没有这个窗口编号", "error", speak=True)
            return False
        window = self.window_candidates[number - 1]
        return self._open_window_for_input(window)

    def _find_window_by_query(self, target_query: str) -> Optional[WindowInfo]:
        self.last_window_lookup_ambiguous = False
        debug_log(f"find_window_by_query query={target_query!r}")
        if is_current_target_query(target_query):
            target = self._select_paste_target()
            if self._is_external_window(target):
                pid = window_process_id(target)
                return WindowInfo(
                    hwnd=int(target),
                    title=window_title(target),
                    process=process_basename(pid),
                    class_name=window_class_name(target),
                )
            return None

        def best_match() -> Optional[WindowInfo]:
            matches = self._window_matches(target_query)
            debug_log(
                "window_matches "
                f"query={target_query!r} "
                f"matches={[(score, window.title) for score, window in matches]!r}"
            )
            if not matches:
                return None

            if is_simple_app_query(target_query) and len(matches) > 1 and matches[1][0] >= matches[0][0] - 15:
                self.last_window_lookup_ambiguous = True
                self._set_window_candidate_matches(target_query, matches)
                self._set_status("找到多个匹配窗口，请说窗口编号。", "target", speak=True)
                return None
            if len(matches) > 1 and matches[0][0] >= 80 and matches[1][0] >= matches[0][0] - 20:
                self.last_window_lookup_ambiguous = True
                self._set_window_candidate_matches(target_query, matches)
                self._set_status("找到几个相近窗口，请说窗口编号。", "target", speak=True)
                return None

            return matches[0][1]

        match = best_match()
        if match is not None:
            return match
        if self.last_window_lookup_ambiguous:
            return None

        if not launch_target_application(target_query):
            return None

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            time.sleep(0.25)
            match = best_match()
            if match is not None:
                return match

        return None

    def _wake_window_available(self, target_query: str) -> bool:
        if is_current_target_query(target_query):
            return self._is_external_window(self._select_paste_target())

        matches: list[tuple[int, WindowInfo]] = []
        for window in enum_windows():
            score = score_window_match(window, target_query)
            if score:
                matches.append((score, window))
        return bool(matches or launch_candidates(target_query))

    def _reset_offline_utterance(self, status: Optional[str] = None, ignore_seconds: float = 0.75) -> None:
        self._reset_live_input_state()
        self._set_partial_text("")
        self.offline_reset_pending = True
        self.ignore_partial_until = max(self.ignore_partial_until, time.monotonic() + ignore_seconds)
        if status:
            self._set_status(status, "listen")
        if self.active_mode == MODE_OFFLINE and self.offline_session is not None:
            self.offline_session.mute_for(ignore_seconds)
        else:
            self.offline_reset_pending = False

    def _clear_pending_target(self) -> None:
        self.pending_target_hwnd = None
        self.pending_target_title = ""
        self.pending_target_ready = False

    def _open_window_for_input(self, window: WindowInfo) -> bool:
        debug_log(f"open_window_for_input hwnd={window.hwnd} title={window.title!r}")
        if is_ignored_window_metadata(window.process, window.class_name, window.title):
            self._clear_pending_target()
            self._set_status("这个窗口不能作为输入目标", "error", speak=True)
            return False

        if not focus_window(window.hwnd):
            self._clear_pending_target()
            self._set_status("窗口切换失败", "error", speak=True)
            return False

        target_ready = self._paste_to_window(window.hwnd, click_input=True, hide_pet=True)
        self.pending_target_hwnd = window.hwnd
        self.pending_target_title = window.title
        self.pending_target_ready = target_ready
        self.paste_target_hwnd = window.hwnd
        self.last_external_hwnd = window.hwnd
        self.window_candidates = []
        self.window_candidate_query = ""
        self._set_candidates_text("")
        self._reset_live_input_state()
        self._set_status(
            "窗口已打开等待输入",
            "target",
            speak=True,
            speak_ignore_seconds=2.4,
            speak_reset_recognizer=True,
        )
        self._reset_offline_utterance(ignore_seconds=2.4)
        return True

    def _open_target_for_input(self, target_query: str, direct: bool = False) -> bool:
        debug_log(f"open_target_for_input query={target_query!r} direct={direct}")
        if not direct and not is_simple_app_query(target_query):
            if self._show_window_candidates(target_query):
                return False

        window = self._find_window_by_query(target_query)
        if window is None:
            self._clear_pending_target()
            if not self.last_window_lookup_ambiguous:
                self._set_status(f"没找到 {target_query}，你可以先手动打开一次。", "error", speak=True)
            return False

        return self._open_window_for_input(window)

    def _execute_wake_command(self, command: WakeCommand) -> bool:
        debug_log(
            "execute_wake_command "
            f"target={command.target_query!r} text_len={len(command.text)} submit={command.submit}"
        )
        window = self._find_window_by_query(command.target_query)
        if window is None:
            if not self.last_window_lookup_ambiguous:
                self._set_status(f"没找到目标窗口：{command.target_query}", "error", speak=True)
            return False

        self.paste_target_hwnd = window.hwnd
        self.last_external_hwnd = window.hwnd
        if not self._paste_to_window(window.hwnd, command.text, press_enter=command.submit):
            self._set_status(f"找到了窗口，但没有输入进去：{window.title}", "error", speak=True)
            return False

        self.text.insert(tk.END, command.text + "\n")
        self.text.see(tk.END)
        action = "并发送" if command.submit else "但未发送"
        self._set_status(f"已切到 {window.title}，输入{action}，继续待命。", "listen", speak=True)
        return True

    def _with_pet_hidden(self, action) -> bool:
        try:
            self.withdraw()
            self.update_idletasks()
            time.sleep(0.08)
            return bool(action())
        finally:
            self.deiconify()
            self.attributes("-topmost", True)
            self._apply_no_activate_style()

    def _paste_to_window(
        self,
        hwnd: Optional[int],
        text: str = "",
        press_enter: bool = False,
        click_input: bool = False,
        hide_pet: bool = False,
    ) -> bool:
        if not self._is_external_window(hwnd):
            return False
        debug_log(
            "paste_to_window "
            f"hwnd={hwnd} text_len={len(text)} press_enter={press_enter} click_input={click_input}"
        )

        def action() -> bool:
            if get_foreground_hwnd() != hwnd and not focus_window(hwnd):
                return False
            if click_input:
                click_likely_input_area(hwnd)
            if text:
                if not send_unicode_text(text):
                    return False
            if press_enter:
                pyautogui.press("enter")
            return True

        if hide_pet:
            return self._with_pet_hidden(action)
        return bool(action())

    def _apply_pending_text_to_target(self, raw_text: str, force: bool = False) -> tuple[bool, bool]:
        raw_text = strip_voice_feedback_echo(raw_text)
        if not raw_text or looks_like_voice_feedback_echo(raw_text):
            self._reset_live_input_state()
            return False, False
        if self.wake_command_var.get() and parse_window_number_command(raw_text) is not None:
            return False, False

        target = self.pending_target_hwnd
        if not self._is_external_window(target):
            self._clear_pending_target()
            self._reset_live_input_state()
            self._set_status("目标窗口不在了，请重新说“打开 Codex 输入”。", "error", speak=True)
            return False, False

        if self.offline_reset_pending or time.monotonic() < self.ignore_partial_until:
            return False, False

        command = resolve_live_voice_command(raw_text, self.live_inserted_text, self.voice_submit_var.get())
        text = command.text
        if not text and not command.submit and not force:
            return False, False

        now = time.monotonic()
        if not force and not command.submit and now - self.last_live_update_at < 0.18:
            return False, False

        old_text = self.live_inserted_text
        if text != old_text:
            edit = build_live_edit(old_text, text)
            if edit.delete_count:
                if not self._paste_to_window(target, "", press_enter=False):
                    self._set_status(f"目标窗口暂时切不过去：{self.pending_target_title}", "error", speak=True)
                    return False, False
                pyautogui.press("backspace", presses=edit.delete_count, interval=0.001)
            if edit.suffix and not self._paste_to_window(target, edit.suffix, press_enter=False):
                self._set_status(f"目标窗口暂时切不过去：{self.pending_target_title}", "error", speak=True)
                return False, False
            self.live_inserted_text = text
            self._set_status(f"正在输入到 {self.pending_target_title}", "busy")

        self.last_live_update_at = now

        if command.submit and not self.voice_submit_triggered:
            self.voice_submit_triggered = True
            if not self._paste_to_window(target, "", press_enter=True):
                self._set_status(f"目标窗口暂时切不过去：{self.pending_target_title}", "error", speak=True)
                return False, False
            if text:
                self.text.insert(tk.END, text + "\n")
                self.text.see(tk.END)
            self._clear_pending_target()
            self._set_status("已发送，继续待命。", "listen", speak=True)
            self._reset_offline_utterance(ignore_seconds=1.25)
            return True, True

        if text and text != old_text:
            self._set_status(f"正在输入到 {self.pending_target_title}，说“发送”结束。", "busy")
        return True, False

    def _maybe_execute_open_candidate(self) -> None:
        if (
            not self.open_candidate_query
            or self.pending_target_hwnd is not None
            or self.offline_reset_pending
            or time.monotonic() < self.ignore_partial_until
        ):
            return
        if not is_simple_app_query(self.open_candidate_query):
            return
        if time.monotonic() - self.open_candidate_at < 0.9:
            return

        target_query = self.open_candidate_query
        self.open_candidate_query = None
        self.open_candidate_text = ""
        self.open_candidate_at = 0.0
        opened = self._open_target_for_input(target_query)
        self._reset_offline_utterance(ignore_seconds=1.25)
        if not opened and not self.last_window_lookup_ambiguous:
            self._set_status(f"没能打开 {target_query}，继续待命。", "error", speak=True)

    def _paste_text_to_target(self, text: str) -> bool:
        target = self.paste_target_hwnd
        if not self._is_external_window(target):
            target = self.last_external_hwnd
        return self._paste_to_window(target, text, press_enter=False)

    def _reset_live_input_state(self) -> None:
        self.live_inserted_text = ""
        self.last_live_update_at = 0.0
        self.voice_submit_triggered = False
        self.open_candidate_query = None
        self.open_candidate_text = ""
        self.open_candidate_at = 0.0

    def _apply_live_text_to_target(self, text: str, force: bool = False) -> bool:
        if self.window_candidates:
            return False
        text = strip_voice_feedback_echo(text)
        if not text or looks_like_voice_feedback_echo(text):
            self._reset_live_input_state()
            return False
        if self.wake_command_var.get() and parse_window_number_command(text) is not None:
            return False
        if self.offline_reset_pending or time.monotonic() < self.ignore_partial_until:
            return False
        if self.wake_command_var.get() and looks_like_wake_command_prefix(text):
            preview_command = parse_wake_command(text, require_submit=False)
            if preview_command is None or self._wake_window_available(preview_command.target_query):
                return False

        command = resolve_live_voice_command(text, self.live_inserted_text, self.voice_submit_var.get())
        text = command.text
        if not text and not command.submit and not force:
            return False

        now = time.monotonic()
        if not force and now - self.last_live_update_at < 0.18:
            return False

        target = self.paste_target_hwnd
        if self._plain_mode_enabled() and not self._is_external_window(target):
            target = self._select_paste_target()
            if self._is_external_window(target):
                self.paste_target_hwnd = target

        if not self._is_external_window(target):
            if self._plain_mode_enabled():
                self._set_status("直接输入：先点一下目标输入窗口。", "target")
            return False

        old_text = self.live_inserted_text
        if text == old_text:
            self.last_live_update_at = now
            if command.submit and not self.voice_submit_triggered:
                self.voice_submit_triggered = True
                if self._paste_to_window(target, "", press_enter=True):
                    self.events.put(("voice_submit", None))
            return True

        edit = build_live_edit(old_text, text)

        if edit.delete_count:
            if not self._paste_to_window(target, "", press_enter=False):
                return False
            pyautogui.press("backspace", presses=edit.delete_count, interval=0.001)
        if edit.suffix and not self._paste_to_window(target, edit.suffix, press_enter=False):
            return False

        self.live_inserted_text = text
        self.last_live_update_at = now
        self._set_status(f"正在输入到 {window_title(target) or '目标窗口'}", "busy")

        if command.submit and not self.voice_submit_triggered:
            self.voice_submit_triggered = True
            if self._paste_to_window(target, "", press_enter=True):
                self.events.put(("voice_submit", None))

        return True

    def _handle_offline_partial(self, partial_text: str) -> None:
        debug_log(f"offline_partial text_len={len(partial_text)}")
        if self.wake_command_var.get() and self.window_candidates:
            window_number = find_window_number_command(partial_text)
            if window_number is not None:
                self._set_partial_text(partial_text)
                opened = self._open_window_candidate_for_input(window_number)
                if not opened:
                    self._set_status("窗口打开失败", "error", speak=True)
            return

        if self.offline_reset_pending or time.monotonic() < self.ignore_partial_until:
            return

        self._set_partial_text(partial_text)

        if self.pending_target_hwnd is not None:
            self._apply_pending_text_to_target(partial_text)
            return

        if self.open_candidate_query and partial_text != self.open_candidate_text:
            self.open_candidate_query = None
            self.open_candidate_text = ""
            self.open_candidate_at = 0.0

        if self.wake_command_var.get():
            if parse_show_window_candidates_command(partial_text):
                self._show_window_candidates("窗口")
                return

            wake_command = parse_wake_command(partial_text, require_submit=True)
            if wake_command is not None:
                self._execute_wake_command(wake_command)
                self._reset_offline_utterance(ignore_seconds=1.25)
                return

            open_query = parse_open_target_command(partial_text)
            if open_query is not None:
                self.open_candidate_query = open_query
                self.open_candidate_text = partial_text
                self.open_candidate_at = time.monotonic()
                if open_target_command_requests_input(partial_text):
                    opened = self._open_target_for_input(open_query)
                    self._reset_offline_utterance(ignore_seconds=1.25)
                    if not opened and not self.last_window_lookup_ambiguous:
                        if self.window_candidates:
                            self._set_status("请说打开窗口编号", "target", speak=True)
                        else:
                            self._set_status(f"没能打开 {open_query}，继续待命。", "error", speak=True)
                    return

                if not is_simple_app_query(open_query):
                    self._show_window_candidates(open_query)
                else:
                    self._set_status(f"听到打开 {open_query}，正在确认。", "target")
                return

        if self.wake_command_var.get() and looks_like_wake_command_prefix(partial_text):
            preview_command = parse_wake_command(partial_text, require_submit=False)
            if preview_command is None:
                self._set_status("正在听唤醒指令。说“打开 Codex 输入”。", "target")
                return

            if not self._wake_window_available(preview_command.target_query):
                if self.active_mode == MODE_OFFLINE and self._plain_mode_enabled():
                    self._apply_live_text_to_target(partial_text)
            else:
                self._set_status("正在听唤醒指令。说完内容后说“发送”。", "target")
            return

        if self.active_mode == MODE_OFFLINE and self._plain_mode_enabled():
            self._apply_live_text_to_target(partial_text)

    def toggle_recording(self) -> None:
        debug_log(f"toggle_recording active_mode={self.active_mode} busy={self.busy}")
        if self.busy:
            return

        if self.active_mode == MODE_API:
            self._stop_api_recording()
            return
        if self.active_mode == MODE_OFFLINE:
            self._stop_offline_recording()
            return

        if self.mode_var.get() == MODE_API:
            self._start_api_recording()
        else:
            self._start_offline_recording()

    def _start_api_recording(self) -> None:
        self.paste_target_hwnd = self._select_paste_target()
        if self._plain_mode_enabled() and not self._is_external_window(self.paste_target_hwnd):
            self._set_status("请先点一下 Codex 或编辑器的输入框。", "error")
            return
        self._reset_live_input_state()
        try:
            self.api_recorder.start()
        except Exception as exc:
            messagebox.showerror("录音失败", str(exc))
            return

        self.active_mode = MODE_API
        self.started_at = time.monotonic()
        self._set_partial_text("")
        self.record_button.configure(text="停止")
        self._set_status("API 模式录音中，再按一次结束。", "listen", speak=True)
        self._sync_controls()

    def _stop_api_recording(self) -> None:
        api_key = self.api_key_var.get().strip()
        api_model = self.api_model_var.get().strip() or DEFAULT_API_MODEL
        self.busy = True
        self.started_at = None
        self.record_button.configure(text="转写中", state=tk.DISABLED)
        self._set_status("正在调用 OpenAI 转写，请稍等。", "busy")
        self._sync_controls()
        threading.Thread(
            target=self._stop_and_transcribe_api,
            args=(api_key, api_model),
            daemon=True,
        ).start()

    def _stop_and_transcribe_api(self, api_key: str, api_model: str) -> None:
        try:
            audio_path = self.api_recorder.stop()
            text = self._transcribe_api(audio_path, api_key, api_model)
            self.events.put(("transcript", TranscriptResult(text=text, audio_path=audio_path, source="api")))
        except Exception as exc:
            debug_log_exception("api_transcribe_failed", exc)
            self.events.put(("error", exc))

    def _transcribe_api(self, audio_path: Path, api_key: str, api_model: str) -> str:
        if not api_key:
            raise RuntimeError("请先设置 OPENAI_API_KEY，或在窗口里填写 API Key。")

        client = OpenAI(api_key=api_key)
        with audio_path.open("rb") as audio:
            result = client.audio.transcriptions.create(
                model=api_model,
                file=audio,
                prompt=DEFAULT_API_PROMPT,
            )

        if isinstance(result, str):
            return clean_transcript(result)
        return clean_transcript(getattr(result, "text", ""))

    def _start_offline_recording(self) -> None:
        debug_log("start_offline_recording")
        if not offline_model_ready():
            messagebox.showinfo("需要离线模型", "先点击“下载离线模型”，或切换到 OpenAI API 模式。")
            return

        self.paste_target_hwnd = self._select_paste_target()
        self._reset_live_input_state()
        self._clear_pending_target()
        self.busy = True
        self._set_partial_text("")
        self.record_button.configure(text="加载中", state=tk.DISABLED)
        self._set_status("正在加载离线识别模型。首次加载会慢一点。", "busy")
        self._sync_controls()
        threading.Thread(target=self._start_offline_session, daemon=True).start()

    def _start_offline_session(self) -> None:
        try:
            recognizer = self._get_offline_recognizer()
            session = OfflineStreamingSession(recognizer=recognizer, events=self.events)
            session.start()
            self.events.put(("offline_started", session))
        except Exception as exc:
            debug_log_exception("offline_start_failed", exc)
            self.events.put(("error", exc))

    def _get_offline_recognizer(self):
        if self.offline_recognizer is not None:
            return self.offline_recognizer

        import sherpa_onnx

        model_dir = Path("models") / DEFAULT_OFFLINE_MODEL_NAME
        self.offline_recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(model_dir / "tokens.txt"),
            encoder=str(model_dir / "encoder.int8.onnx"),
            decoder=str(model_dir / "decoder.onnx"),
            joiner=str(model_dir / "joiner.int8.onnx"),
            num_threads=max(2, min(4, (os.cpu_count() or 2))),
            sample_rate=SAMPLE_RATE,
            decoding_method="greedy_search",
            enable_endpoint_detection=True,
            model_type="zipformer2",
            modeling_unit="bpe",
            bpe_vocab=str(model_dir / "bpe.model"),
        )
        return self.offline_recognizer

    def _stop_offline_recording(self) -> None:
        session = self.offline_session
        if session is None:
            return

        self.started_at = None
        self.offline_reset_pending = False
        self.ignore_partial_until = 0.0
        self._set_partial_text("")
        try:
            session.stop(discard_result=True)
        except Exception as exc:
            debug_log(f"offline_quick_stop_failed {exc!r}")
        self._finish_recording_ui()
        self._set_status("已停止。", "idle")

    def install_offline_model(self) -> None:
        if offline_model_ready() or self.busy:
            self._sync_controls()
            return

        self.busy = True
        self.record_button.configure(state=tk.DISABLED)
        self._set_status("正在下载离线模型，约 128 MB。", "busy")
        self._sync_controls()
        threading.Thread(target=self._install_offline_model_thread, daemon=True).start()

    def _install_offline_model_thread(self) -> None:
        try:
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            archive = MODELS_DIR / f"{DEFAULT_OFFLINE_MODEL_NAME}.tar.bz2"
            if not archive.exists():
                request = urllib.request.Request(DEFAULT_OFFLINE_MODEL_URL, headers={"User-Agent": "CodexVoiceInput"})
                with urllib.request.urlopen(request) as response, archive.open("wb") as file:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        file.write(chunk)

            if not DEFAULT_OFFLINE_MODEL_DIR.exists():
                safe_extract_tar(archive, MODELS_DIR)

            self.events.put(("model_installed", str(DEFAULT_OFFLINE_MODEL_DIR)))
        except Exception as exc:
            debug_log_exception("offline_model_install_failed", exc)
            self.events.put(("error", exc))

    def _handle_transcript(self, result: TranscriptResult) -> None:
        if result.source == "offline" and self.voice_submit_triggered:
            self._set_status("已按语音命令发送。", "listen")
            return

        text = clean_transcript(result.text)
        command = parse_voice_command(text) if result.source == "offline" and self.voice_submit_var.get() else VoiceCommand(text)
        stored_text = command.text if command.submit else text
        if not text:
            self._set_status("没有识别到文字。", "idle")
            return
        if result.source == "offline" and self.wake_command_var.get() and looks_like_window_candidate_selection(text):
            window_number = find_window_number_command(text)
            if self.window_candidates and window_number is not None:
                self._open_window_candidate_for_input(window_number)
            else:
                self._set_status("已忽略窗口选择指令。", "idle")
            return

        if stored_text:
            self.text.insert(tk.END, stored_text + "\n")
            self.text.see(tk.END)

        live_mode = result.source == "offline" and self._plain_mode_enabled()
        direct_result_mode = self._plain_mode_enabled() and not live_mode
        if live_mode:
            pasted = self._apply_live_text_to_target(text, force=True)
        elif direct_result_mode:
            pasted = self._paste_text_to_target(stored_text or text)
        else:
            pasted = False

        source = "离线实时" if result.source == "offline" else "API"
        if live_mode:
            paste_note = "已实时输入到目标窗口。" if pasted else "实时输入目标窗口不可用。"
        elif direct_result_mode:
            paste_note = "已输入到目标窗口。" if pasted else "目标窗口不可用，文字已保留在工具中。"
        else:
            paste_note = ""
        self._set_status(f"{source}转写完成。{paste_note}", "idle")

    def _finish_recording_ui(self) -> None:
        self.active_mode = None
        self.busy = False
        self.offline_session = None
        self.record_button.configure(text="开始", state=tk.NORMAL)
        self.timer_var.set("00:00")
        self._sync_controls()

    def paste_text(self) -> None:
        content = self.text.get("1.0", tk.END).strip()
        if content:
            if self._paste_text_to_target(content):
                self._set_status("已输入到目标窗口。", "idle")
            else:
                self._set_status("未找到可输入的目标窗口。", "error")

    def _poll_events(self) -> None:
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break

            if kind == "toggle":
                starting = self.active_mode is None and not self.busy
                self.toggle_recording()
                if starting and payload in {"keyboard", "mouse"} and (self.busy or self.active_mode is not None):
                    self._play_laugh_sound()
            elif kind == "offline_started":
                debug_log("event_offline_started")
                self.offline_session = payload
                self.active_mode = MODE_OFFLINE
                self.busy = False
                self.started_at = time.monotonic()
                self.record_button.configure(text="停止", state=tk.NORMAL)
                if self._plain_mode_enabled():
                    self._set_status("直接输入：点目标窗口后开始说话。", "listen")
                elif self.wake_command_var.get():
                    self._set_status("我在听。请说“打开 Codex 输入”。", "listen")
                else:
                    self._set_status("仅转写模式：识别结果保留在工具中。", "listen")
                self._sync_controls()
            elif kind == "partial":
                partial_session = None
                partial_text = payload
                if isinstance(payload, tuple) and len(payload) == 2:
                    partial_session, partial_text = payload
                if partial_session is not None and partial_session is not self.offline_session:
                    continue
                if self.active_mode == MODE_OFFLINE and self.offline_session is not None:
                    self._handle_offline_partial(str(partial_text))
            elif kind == "voice_submit":
                if self.active_mode == MODE_OFFLINE and self.offline_session is not None:
                    self._reset_offline_utterance("已按语音命令发送，继续待命。")
            elif kind == "offline_reset":
                if payload is not None and payload is not self.offline_session:
                    continue
                self.offline_reset_pending = False
                self._set_partial_text("")
            elif kind == "utterance_endpoint":
                if payload is not self.offline_session or self.active_mode != MODE_OFFLINE:
                    continue
                if not self.voice_submit_triggered:
                    self._set_status("我在听，继续说话。", "listen")
            elif kind == "transcript":
                transcript_session = None
                result = payload
                if isinstance(payload, tuple) and len(payload) == 2:
                    transcript_session, result = payload
                if isinstance(result, TranscriptResult) and result.source == "offline":
                    if transcript_session is not None and transcript_session is not self.offline_session:
                        continue
                    if self.active_mode != MODE_OFFLINE:
                        continue
                self._set_partial_text("")
                self._finish_recording_ui()
                self._handle_transcript(result)
            elif kind == "model_installed":
                self.busy = False
                self.record_button.configure(state=tk.NORMAL)
                self._set_status("离线模型安装完成，可以使用离线实时模式。", "idle", speak=True)
                self._sync_controls()
            elif kind == "error":
                self._set_partial_text("")
                self.started_at = None
                self.active_mode = None
                self.busy = False
                self.offline_session = None
                self.record_button.configure(text="开始", state=tk.NORMAL)
                self.timer_var.set("00:00")
                self._sync_controls()
                messagebox.showerror("出错了", str(payload))
                self._set_status("出错了，请看提示。", "error")

        self._maybe_execute_open_candidate()
        self.after(100, self._poll_events)

    def _tick_timer(self) -> None:
        if self.started_at is not None:
            elapsed = int(time.monotonic() - self.started_at)
            minutes, seconds = divmod(elapsed, 60)
            self.timer_var.set(f"{minutes:02d}:{seconds:02d}")
        self.after(250, self._tick_timer)

    def _on_close(self) -> None:
        self._save_user_settings()
        if self.listener is not None:
            self.listener.stop()
        if self.mouse_listener is not None:
            self.mouse_listener.stop()
        if self.api_recorder.is_recording:
            try:
                self.api_recorder.stop()
            except Exception:
                pass
        if self.offline_session is not None:
            try:
                self.offline_session.stop(discard_result=True)
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    instance_mutex = acquire_single_instance_mutex()
    if instance_mutex != 0:
        app = VoiceInputApp()
        try:
            app.mainloop()
        finally:
            if instance_mutex and KERNEL32 is not None:
                KERNEL32.CloseHandle(instance_mutex)
