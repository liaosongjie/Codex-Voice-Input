import copy
import numpy as np
from pathlib import Path
import queue
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

import app_targets as targets
import voice_input as voice
from target_settings import TargetSettings


def fixture_apps():
    return [{
        'id': 'codex', 'name': 'Codex', 'aliases': ['口袋', 'context'],
        'launch': 'codex://', 'processes': ['chatgpt.exe'], 'window_title': '',
        'input_name': 'Message', 'input_id': '', 'input_hotkey': '',
        'projects': [
            {'id': 'hunter', 'name': 'AI交易猎人', 'aliases': ['交易猎人'],
             'launch': '', 'window_title': '', 'ui_name': 'AI交易猎人', 'ui_id': ''},
            {'id': 'voice', 'name': '中文语音输入', 'aliases': [], 'launch': '',
             'window_title': '语音输入', 'ui_name': '', 'ui_id': ''},
        ],
    }, {'id': 'workbuddy', 'name': 'WorkBuddy', 'aliases': ['工作伙伴'],
        'launch': 'workbuddy://', 'processes': ['workbuddy.exe'], 'window_title': '',
        'input_name': '', 'input_id': '', 'input_hotkey': '', 'projects': []}]


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.apps = fixture_apps()

    def test_program_alias_and_whitespace(self):
        for command in ('打开 Codex', '切换到codex', '打开口袋', '请打开 context。', '打开 Codex 输入'):
            self.assertEqual(targets.resolve_command(command, self.apps).app['id'], 'codex')
        self.assertEqual(targets.resolve_command('\u6253\u5f00 Codex', self.apps).action, 'open')
        self.assertEqual(targets.resolve_command('\u5207\u6362\u5230 Codex', self.apps).action, 'switch')

    def test_project_in_same_or_following_command(self):
        for command in ('切换到 Codex 的 AI交易猎人项目', '打开 Codex 然后切换到 AI交易猎人',
                        '切到项目交易猎人', '切换到 AI交易猎人', '切换到Codex的AI交易项目'):
            self.assertEqual(targets.resolve_command(command, self.apps, 'codex').project['id'], 'hunter', command)
        self.assertEqual(targets.resolve_command('切换到中文语音输入', self.apps).project['id'], 'voice')

    def test_no_embedded_commands_or_unknown_fallback(self):
        self.assertIsNone(targets.resolve_command('我想让你打开 Codex', self.apps))
        self.assertIsNone(targets.resolve_command('打开记事本', self.apps))
        self.assertTrue(targets.resolve_command('打开Codex不存在项目', self.apps).error)
        self.assertTrue(targets.resolve_command('切换到项目不存在', self.apps).error)

    def test_payload_is_not_project_name(self):
        result = targets.resolve_command('打开 WorkBuddy 然后输入帮我检查项目发送', self.apps)
        self.assertEqual(result.app['id'], 'workbuddy')
        self.assertEqual(result.text, '帮我检查项目发送')

    def test_simple_app_uses_dynamic_dialog_query(self):
        result = targets.resolve_command('打开 WorkBuddy 日常', self.apps)
        self.assertEqual(result.app['id'], 'workbuddy')
        self.assertEqual(result.dynamic_query, '日常')

    def test_find_without_program_uses_last_bound_app(self):
        result = targets.resolve_command('找到金额计算', self.apps, 'workbuddy')
        self.assertEqual(result.app['id'], 'workbuddy')
        self.assertEqual(result.dynamic_query, '金额计算')

    def test_ambiguous_project_is_not_chosen(self):
        extra = copy.deepcopy(self.apps[0]['projects'][0])
        extra.update(id='research', name='AI交易研究', aliases=[], ui_name='AI交易研究')
        self.apps[0]['projects'].append(extra)
        self.assertTrue(targets.resolve_command('切换到AI交易', self.apps).error)
        self.assertEqual(targets.resolve_command('切换到AI交易猎人', self.apps).project['id'], 'hunter')

    def test_last_app_context(self):
        self.apps[1]['projects'] = copy.deepcopy(self.apps[0]['projects'])
        self.assertTrue(targets.resolve_command('切换到交易猎人', self.apps).error)
        self.assertEqual(targets.resolve_command('切换到交易猎人', self.apps, 'workbuddy').app['id'], 'workbuddy')

    def test_process_and_title_scope(self):
        windows = [voice.WindowInfo(1, 'ChatGPT', 'chatgpt.exe', 'Chrome_WidgetWin_1'),
                   voice.WindowInfo(2, 'Codex', 'chrome.exe', 'Chrome_WidgetWin_1'),
                   voice.WindowInfo(3, '语音输入', 'chatgpt.exe', 'Chrome_WidgetWin_1')]
        self.assertEqual([w.hwnd for w in targets.matching_windows(windows, self.apps[0])], [1, 3])
        self.assertEqual([w.hwnd for w in targets.matching_windows(windows, self.apps[0], self.apps[0]['projects'][1])], [3])

    def test_atomic_save_roundtrip_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'apps.json'
            expected = targets.save_apps(path, self.apps)
            self.assertEqual(targets.load_apps(path), expected)
            before = path.read_bytes()
            invalid = copy.deepcopy(self.apps)
            invalid[1]['aliases'] = ['codex']
            with self.assertRaises(ValueError):
                targets.save_apps(path, invalid)
            self.assertEqual(path.read_bytes(), before)

    def test_launch_validation_and_no_shell(self):
        for value in ('powershell -Command test', 'javascript:alert(1)', 'file:///C:/x.exe', 'x\n.exe'):
            with self.assertRaises(ValueError):
                targets.launch_address(value)
        with patch('app_targets.os.startfile') as start:
            targets.launch('codex://projects/abc?name=project%20one')
            start.assert_called_once_with('codex://projects/abc?name=project%20one')

    def test_browsers_can_use_dynamic_window_selection(self):
        self.apps[0]['processes'] = ['chrome.exe']
        validated = targets.validate_apps(self.apps)
        self.assertEqual(validated[0]['window_title'], '')

    def test_target_mode_migrates_legacy_settings(self):
        self.assertEqual(voice.saved_target_mode({'plain_mode': True, 'wake_command': False}), voice.TARGET_MODE_CURRENT)
        self.assertEqual(voice.saved_target_mode({'plain_mode': False, 'wake_command': True}), voice.TARGET_MODE_CONFIGURED)
        self.assertEqual(voice.saved_target_mode({'target_mode': '打开/切换窗口'}), voice.TARGET_MODE_CONFIGURED)
        self.assertEqual(voice.saved_target_mode({'target_mode': voice.TARGET_MODE_CODEX}), voice.TARGET_MODE_CODEX)
        self.assertEqual(voice.target_command_action('\u6253\u5f00 Codex'), 'open')
        self.assertEqual(voice.target_command_action('\u5207\u6362\u5230 Codex'), 'switch')

    def test_custom_routing_words_and_submit_aliases(self):
        normalized = voice.normalize_routing_words(
            '请启动豆包然后写帮我写一段代码', '启动', '定位', '写'
        )
        self.assertEqual(normalized, '请打开豆包然后输入帮我写一段代码')
        command = voice.parse_voice_command('内容完成', ('完成',))
        self.assertEqual(command.text, '内容')
        self.assertTrue(command.submit)


class Preview(voice.VoiceInputApp):
    def _start_hotkey_listener(self): pass
    def _auto_start_if_ready(self): pass
    def _remember_external_window(self): pass
    def _show_first_run_setup(self): pass
    def _install_settings_traces(self): pass
    def _save_user_settings(self): pass
    def _speak(self, *args, **kwargs): pass
    def _play_pet_sound(self, *args, **kwargs): pass
    def _apply_shortcut_settings(self, *args, **kwargs): pass


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.app = Preview()
        self.app.configured_apps = fixture_apps()
        self.app.target_mode_var.set(voice.TARGET_MODE_CONFIGURED)
        self.app._sync_target_mode_compatibility()
        self.app.ignore_partial_until = 0
        self.app.offline_reset_pending = False

    def tearDown(self):
        self.app.configured_route_generation += 1
        self.app.destroy()

    def test_partial_commands_wait_for_endpoint_and_can_interrupt_target(self):
        self.app.pending_target_hwnd = 91
        with patch.object(self.app, '_apply_pending_text_to_target') as insert, patch.object(self.app, '_begin_configured_route') as begin:
            self.app._handle_offline_partial('打开 Codex')
            self.app._handle_offline_partial('打开 Codex 然后切换到 AI交易猎人')
            self.assertEqual(self.app.configured_command_text, '打开 Codex 然后切换到 AI交易猎人')
            begin.assert_not_called()
            insert.assert_not_called()
            self.app.active_mode = voice.MODE_OFFLINE
            self.app.offline_session = object()
            self.app.events.put(('utterance_endpoint', self.app.offline_session))
            self.app._poll_events()
            begin.assert_called_once()
            self.assertEqual(begin.call_args.args[0].project['id'], 'hunter')

    def test_current_window_mode_does_not_route_codex_command(self):
        self.app.target_mode_var.set(voice.TARGET_MODE_CURRENT)
        self.app._sync_target_mode_compatibility()
        self.app.active_mode = voice.MODE_OFFLINE
        with patch.object(self.app, '_apply_live_text_to_target') as live, patch.object(self.app, '_open_target_for_input') as route:
            self.app._handle_offline_partial('打开 Codex')
            live.assert_called_once_with('打开 Codex')
            route.assert_not_called()

    def test_current_window_mode_accepts_any_non_ignored_foreground_window(self):
        self.app.target_mode_var.set(voice.TARGET_MODE_CURRENT)
        self.app._sync_target_mode_compatibility()
        window = voice.WindowInfo(77, 'WeChat Chat', 'WeChat.exe', 'Chrome_WidgetWin_1')
        with patch('voice_input.get_foreground_hwnd', return_value=77), patch('voice_input.window_info_from_hwnd', return_value=window):
            self.assertEqual(self.app._select_paste_target(), 77)

    def test_codex_mode_directly_inputs_without_routing(self):
        self.app.target_mode_var.set(voice.TARGET_MODE_CODEX)
        self.app._sync_target_mode_compatibility()
        self.app.active_mode = voice.MODE_OFFLINE
        with patch.object(self.app, '_apply_live_text_to_target') as live, patch.object(self.app, '_open_target_for_input') as route:
            self.app._handle_offline_partial('打开 Codex 输入')
            live.assert_called_once_with('打开 Codex 输入')
            route.assert_not_called()

    def test_codex_mode_does_not_auto_locate(self):
        self.app.target_mode_var.set(voice.TARGET_MODE_CODEX)
        self.app._sync_target_mode_compatibility()
        self.app.active_mode = voice.MODE_OFFLINE
        with patch.object(self.app, '_open_target_for_input') as route:
            self.assertEqual(self.app._target_mode(), voice.TARGET_MODE_CODEX)
            route.assert_not_called()

    def test_codex_mode_prepares_code_window_before_recording(self):
        self.app.target_mode_var.set(voice.TARGET_MODE_CODEX)
        self.app._sync_target_mode_compatibility()
        window = voice.WindowInfo(21, 'codex语音输入 - Visual Studio Code', 'Code.exe', 'Chrome_WidgetWin_1')
        with patch('voice_input.get_foreground_hwnd', return_value=0), \
             patch.object(self.app, '_is_external_window', side_effect=lambda hwnd: hwnd == 21), \
             patch('voice_input.enum_windows', return_value=[window]), \
             patch('voice_input.focus_window', return_value=True), \
             patch.object(self.app, '_paste_to_window', return_value=True) as paste:
            self.assertTrue(self.app._prepare_codex_input_target())
        self.assertEqual(self.app.paste_target_hwnd, 21)
        self.assertEqual(self.app.last_external_hwnd, 21)
        paste.assert_called_once_with(21, click_input=True, hide_pet=True)

    def test_configured_route_accepts_non_code_window_after_scan(self):
        request = targets.RouteRequest(self.app.configured_apps[1], action='open')
        window = voice.WindowInfo(22, '豆包', 'doubao.exe', 'Chrome_WidgetWin_1')
        with patch.object(self.app, '_is_routable_window', return_value=True), \
             patch('voice_input.get_foreground_hwnd', return_value=22):
            self.app._finish_configured_route((0, 'select', request, (window, [])))
        self.assertIs(self.app.pending_dialog_request, request)
        self.assertEqual(self.app.pending_dialog_hwnd, 22)

    def test_configured_app_query_resolves_saved_launch_binding(self):
        app = self.app._configured_app_for_query('WorkBuddy')
        self.assertEqual(app['id'], 'workbuddy')
        self.assertEqual(app['launch'], 'workbuddy://')

    def test_dynamic_task_uses_ocr_when_electron_has_no_uia_nodes(self):
        window = voice.WindowInfo(23, '豆包', 'doubao.exe', 'Chrome_WidgetWin_1')

        class FakeScreenshot:
            def save(self, _path):
                return None

        with patch('voice_input.window_screen_rect', return_value=(10, 20, 800, 600)), \
             patch('voice_input.pyautogui.size', return_value=(1920, 1080)), \
             patch('voice_input.pyautogui.screenshot', return_value=FakeScreenshot()), \
             patch('voice_input.app_targets.query_ocr', return_value={
                 'ok': True,
                 'lines': [{'text': '交 易 金 额 计 算', 'words': [
                     {'text': '交', 'left': 100, 'top': 120, 'width': 20, 'height': 20},
                     {'text': '算', 'left': 160, 'top': 120, 'width': 20, 'height': 20},
                 ]}],
             }), \
             patch('voice_input.pyautogui.click') as click:
            self.assertTrue(self.app._click_screen_text_fallback(window, '金额计算'))
        click.assert_called_once_with(150, 150)

    def test_screen_keyword_match_accepts_partial_and_asr_extended_names(self):
        self.assertTrue(voice.screen_keyword_match('金额计算', '交易金额计算'))
        self.assertTrue(voice.screen_keyword_match('金额计算助手', '交易金额计算'))
        self.assertFalse(voice.screen_keyword_match('会议总结', '交易金额计算'))

    def test_input_placeholder_is_ocr_calibrated_and_reused(self):
        window = voice.WindowInfo(23, '豆包', 'doubao.exe', 'Chrome_WidgetWin_1')

        class FakeScreenshot:
            def save(self, _path):
                return None

        ocr = {'ok': True, 'lines': [{'text': '发消息或按住空格说话...', 'words': [
            {'text': '发消息或按住空格说话...', 'left': 300, 'top': 500, 'width': 180, 'height': 24},
        ]}]}
        with patch('voice_input.window_screen_rect', return_value=(10, 20, 800, 600)), \
             patch('voice_input.pyautogui.size', return_value=(1920, 1080)), \
             patch('voice_input.pyautogui.screenshot', return_value=FakeScreenshot()), \
             patch('voice_input.app_targets.query_ocr', return_value=ocr) as query_ocr, \
             patch('voice_input.pyautogui.click') as click:
            self.assertTrue(self.app._click_configured_input_area(window))
            self.assertTrue(self.app._click_configured_input_area(window))
        query_ocr.assert_called_once()
        self.assertEqual(click.call_count, 2)
        self.assertEqual(click.call_args_list[0].args, (320, 532))
        self.assertEqual(click.call_args_list[1].args, (320, 532))

    def test_missing_ocr_placeholder_does_not_guess_a_bottom_coordinate(self):
        window = voice.WindowInfo(23, '豆包', 'doubao.exe', 'Chrome_WidgetWin_1')
        with patch.object(self.app, '_capture_window_ocr', return_value=(
            {'ok': True, 'lines': []}, 10, 20, 10, 20, 800, 600
        )), patch('voice_input.click_likely_input_area') as fallback:
            self.assertFalse(self.app._click_configured_input_area(window))
        fallback.assert_not_called()

    def test_dynamic_task_query_removes_spoken_command_prefix(self):
        self.assertEqual(voice.clean_dialog_target_query('输入 交易金额计算'), '交易金额计算')
        self.assertEqual(voice.clean_dialog_target_query('请打开对话框 交易金额计算'), '交易金额计算')

    def test_dynamic_task_name_is_routed_once_without_waiting_for_endpoint(self):
        request = targets.RouteRequest(self.app.configured_apps[1], action='open')
        window = voice.WindowInfo(24, 'WorkBuddy', 'workbuddy.exe', 'Chrome_WidgetWin_1')
        self.app.pending_dialog_request = request
        self.app.pending_dialog_hwnd = window.hwnd
        self.app.pending_dialog_text = '输入 交易金额计算'
        with patch('voice_input.window_info_from_hwnd', return_value=window), \
             patch.object(self.app, '_begin_configured_route') as begin:
            self.assertTrue(self.app._route_pending_dialog_name())
            self.assertFalse(self.app._route_pending_dialog_name())
        routed = begin.call_args.args[0]
        self.assertEqual(routed.dynamic_query, '交易金额计算')
        self.assertEqual(routed.action, 'switch')
        self.assertIs(self.app.pending_dialog_request, request)
        self.assertEqual(self.app.pending_dialog_hwnd, window.hwnd)

    def test_failed_dialog_lookup_keeps_waiting_for_retry_keywords(self):
        request = targets.RouteRequest(self.app.configured_apps[1], action='open')
        window = voice.WindowInfo(24, 'WorkBuddy', 'workbuddy.exe', 'Chrome_WidgetWin_1')
        self.app.pending_dialog_request = request
        self.app.pending_dialog_hwnd = window.hwnd
        self.app.configured_route_busy = True
        failed = targets.RouteRequest(app=request.app, action='switch', dynamic_query='第一次说错')
        with patch.object(self.app, '_set_status') as status, \
             patch.object(self.app, '_reset_offline_utterance'):
            self.app._finish_configured_route((0, 'error', failed, '没有找到'))
        self.assertFalse(self.app.configured_route_busy)
        self.assertIs(self.app.pending_dialog_request, request)
        self.assertEqual(self.app.pending_dialog_hwnd, window.hwnd)
        status.assert_called_once()
        with patch('voice_input.window_info_from_hwnd', return_value=window), \
             patch.object(self.app, '_begin_configured_route') as begin:
            self.app._handle_offline_partial('金额计算')
            self.assertEqual(self.app.pending_dialog_text, '金额计算')
            self.assertTrue(self.app._route_pending_dialog_name())
        self.assertEqual(begin.call_args.args[0].dynamic_query, '金额计算')

    def test_dialog_partial_does_not_click_before_endpoint(self):
        request = targets.RouteRequest(self.app.configured_apps[1], action='open')
        self.app.pending_dialog_request = request
        with patch.object(self.app, '_route_pending_dialog_name') as route:
            self.app._handle_offline_partial('交易金额')
        route.assert_not_called()
        self.assertEqual(self.app.pending_dialog_text, '交易金额')

    def test_dialog_ignores_feedback_echo(self):
        request = targets.RouteRequest(self.app.configured_apps[1], action='open')
        self.app.pending_dialog_request = request
        self.app.last_feedback_text = '已打开豆包，请说对话框名称'
        self.app.feedback_echo_until = time.monotonic() + 30
        self.app._handle_offline_partial('豆包')
        self.assertEqual(self.app.pending_dialog_text, '')
        self.app._handle_offline_partial('稍后')
        self.assertEqual(self.app.pending_dialog_text, '')

    def test_input_device_options_exclude_output_loopback(self):
        with patch('voice_input.sd.query_devices', return_value=[
            {'name': '内置麦克风', 'max_input_channels': 1},
            {'name': 'Stereo Mix (Realtek)', 'max_input_channels': 2},
            {'name': 'USB 麦克风', 'max_input_channels': 1},
            {'name': '扬声器 (Loopback)', 'max_input_channels': 2},
        ]):
            self.assertEqual(voice.input_device_options(), ['系统默认麦克风', '内置麦克风', 'USB 麦克风'])

    def test_input_device_options_exclude_windows_mapper_even_when_localized(self):
        with patch('voice_input.sd.query_devices', return_value=[
            {'name': 'Microsoft Sound Mapper - Input', 'max_input_channels': 2},
            {'name': 'Realtek 麦克风', 'max_input_channels': 2},
        ]):
            self.assertEqual(voice.input_device_options(), ['系统默认麦克风', 'Realtek 麦克风'])

    def test_audio_queue_is_bounded_and_drops_oldest_chunk(self):
        class FakeRecognizer:
            def create_stream(self):
                return object()

        session = voice.OfflineStreamingSession(FakeRecognizer(), queue.Queue())
        session.audio_queue = queue.Queue(maxsize=2)
        session._capture(np.ones((160, 1), dtype=np.float32), 160, None, None)
        session._capture(np.ones((160, 1), dtype=np.float32) * 2, 160, None, None)
        session._capture(np.ones((160, 1), dtype=np.float32) * 3, 160, None, None)
        self.assertEqual(session.audio_queue.qsize(), 2)
        self.assertEqual(session.dropped_audio_chunks, 1)
        session.stop_event.set()

    def test_input_device_options_exclude_chinese_virtual_audio(self):
        with patch('voice_input.sd.query_devices', return_value=[
            {'name': '麦克风阵列（网易虚拟音频设备）', 'max_input_channels': 2},
            {'name': '麦克风 (Realtek)', 'max_input_channels': 2},
        ]):
            self.assertEqual(voice.input_device_options(), ['系统默认麦克风', '麦克风 (Realtek)'])

    def test_virtual_default_skips_mapper_and_prefers_physical_capture(self):
        devices = [
            {'name': 'Microsoft Sound Mapper - Input', 'max_input_channels': 2},
            {'name': 'ToDesk Virtual Audio', 'max_input_channels': 2},
            {'name': 'Realtek 麦克风', 'max_input_channels': 2},
        ]
        with patch('voice_input.sd.query_devices', return_value=devices), \
             patch('voice_input._default_input_device_index', return_value=1):
            self.assertEqual(voice._input_device_candidates(None), [2])

    def test_chinese_virtual_microphone_is_not_selected_as_physical_fallback(self):
        devices = [
            {'name': '麦克风阵列（网易虚拟音频设备）', 'max_input_channels': 2},
            {'name': '麦克风 (Realtek(R) Audio)', 'max_input_channels': 2},
        ]
        with patch('voice_input.sd.query_devices', return_value=devices), \
             patch('voice_input._default_input_device_index', return_value=0):
            self.assertEqual(voice._input_device_candidates(None), [1])

    def test_failed_capture_stream_is_closed_before_physical_fallback(self):
        devices = [
            {'name': 'Realtek 麦克风 1', 'max_input_channels': 2},
            {'name': 'Realtek 麦克风 2', 'max_input_channels': 2},
        ]

        class FakeStream:
            def __init__(self, device):
                self.device = device
                self.closed = False

            def start(self):
                if self.device == 0:
                    raise RuntimeError('stale capture device')

            def close(self):
                self.closed = True

            def stop(self):
                self.closed = True

        streams = []

        def make_stream(*, device, **_kwargs):
            stream = FakeStream(device)
            streams.append(stream)
            return stream

        with patch('voice_input.sd.query_devices', return_value=devices), \
             patch('voice_input.sd.InputStream', side_effect=make_stream):
            stream, selected = voice.open_input_stream(
                sample_rate=voice.SAMPLE_RATE,
                channels=1,
                dtype='float32',
                device=0,
                callback=lambda *_args: None,
            )

        self.assertEqual(selected, 1)
        self.assertTrue(streams[0].closed)
        self.assertIs(stream, streams[1])

    def test_feedback_echo_filter_catches_waiting_status(self):
        self.assertTrue(voice.looks_like_voice_feedback_echo('稍后'))
        self.assertTrue(voice.looks_like_voice_feedback_echo('正在打开豆包，请稍候'))
        self.assertTrue(voice.looks_like_voice_feedback_echo('没有找到稍后'))
        self.assertTrue(voice.matches_recent_feedback('豆包', '已打开豆包，请说对话框名称'))
        self.assertFalse(voice.matches_recent_feedback('交易金额', '已打开豆包，请说对话框名称'))

    def test_dynamic_worker_uses_screen_scan_before_input_focus(self):
        window = voice.WindowInfo(26, 'WorkBuddy', 'workbuddy.exe', 'Chrome_WidgetWin_1')
        request = targets.RouteRequest(self.app.configured_apps[1], action='switch', dynamic_query='交易金额计算')
        with patch('voice_input.enum_windows', return_value=[window]), \
             patch('voice_input.focus_window', return_value=True), \
             patch.object(self.app, '_select_screen_dialog', return_value=True) as scan, \
             patch('app_targets.query_ui') as uia, \
             patch('voice_input.get_foreground_hwnd', return_value=26):
            self.app._configured_route_worker(self.app.configured_route_generation, request, None)
        scan.assert_called_once()
        uia.assert_not_called()
        self.assertEqual(self.app.events.get_nowait()[1][1], 'ready')

    def test_transcript_cleanup_does_not_cancel_route_started_at_endpoint(self):
        generation = self.app.configured_route_generation
        self.app.configured_route_busy = True
        self.app._finish_recording_ui()
        self.assertEqual(self.app.configured_route_generation, generation)

    def test_first_routed_text_refocuses_and_clicks_input_area(self):
        self.app.configured_ready_hwnd = 27
        with patch.object(self.app, '_is_input_target_window', return_value=True), \
             patch.object(self.app, '_with_pet_hidden', side_effect=lambda action: action()), \
             patch('voice_input.window_info_from_hwnd', return_value=voice.WindowInfo(27, 'WorkBuddy', 'workbuddy.exe', 'Chrome_WidgetWin_1')), \
             patch('voice_input.focus_window', return_value=True) as focus, \
             patch.object(self.app, '_click_configured_input_area', return_value=True) as click:
            self.assertTrue(self.app._focus_configured_input(27))
        focus.assert_called_once_with(27)
        click.assert_called_once()

    def test_routed_text_reclicks_input_after_pet_reclaims_focus(self):
        self.app.configured_ready_hwnd = 27
        configured = self.app.configured_apps[1]
        window = voice.WindowInfo(27, 'WorkBuddy', 'workbuddy.exe', 'Chrome_WidgetWin_1')
        with patch.object(self.app, '_is_input_target_window', return_value=True), \
             patch.object(self.app, '_configured_app_for_window', return_value=configured), \
             patch('voice_input.window_info_from_hwnd', return_value=window), \
             patch('voice_input.get_foreground_hwnd', return_value=99), \
             patch('voice_input.focus_window', return_value=True) as focus, \
             patch.object(self.app, '_click_configured_input_area', return_value=True) as click, \
             patch('voice_input.send_unicode_text', return_value=True) as send:
            self.assertTrue(self.app._paste_to_window(27, '你好'))
        focus.assert_called_once_with(27)
        click.assert_called_once()
        send.assert_called_once_with('你好')

    def test_doubao_uses_screen_task_picker_instead_of_empty_uia_scan(self):
        app = {'name': '豆包'}
        window = voice.WindowInfo(25, '豆包', 'doubao.exe', 'Chrome_WidgetWin_1')
        self.assertTrue(self.app._uses_screen_task_picker(app, window))

    def test_target_mode_can_switch_while_listening(self):
        self.app.active_mode = voice.MODE_OFFLINE
        self.app.busy = False
        self.app._sync_controls()
        self.assertEqual(str(self.app.target_mode_box.cget('state')), 'readonly')

        self.app.paste_target_hwnd = 123
        self.app.target_mode_var.set(voice.TARGET_MODE_CURRENT)
        self.app._on_target_mode_changed()
        self.assertIsNone(self.app.paste_target_hwnd)

    def test_target_mode_change_auto_starts_when_requested(self):
        self.app.active_mode = None
        self.app.busy = False
        with patch.object(self.app, 'toggle_recording') as toggle:
            self.app._auto_start_after_target_change()
        toggle.assert_called_once_with()

    def test_target_mode_change_does_not_restart_active_session(self):
        self.app.active_mode = voice.MODE_OFFLINE
        with patch.object(self.app, 'toggle_recording') as toggle:
            self.app._auto_start_after_target_change()
        toggle.assert_not_called()

    def test_worker_ambiguous_and_no_false_ready(self):
        window = voice.WindowInfo(11, 'WorkBuddy', 'workbuddy.exe', 'Chrome_WidgetWin_1')
        request = targets.RouteRequest(self.app.configured_apps[1])
        with patch('voice_input.enum_windows', return_value=[window, voice.WindowInfo(12, 'WorkBuddy 2', 'workbuddy.exe', 'Chrome_WidgetWin_1')]), patch('app_targets.query_ui') as ui:
            self.app._configured_route_worker(0, request, None)
            ui.assert_not_called()
            event = self.app.events.get_nowait()
            self.assertEqual(event[1][1], 'choices')
        with patch('voice_input.enum_windows', return_value=[window]), patch('voice_input.focus_window', return_value=False):
            self.app._configured_route_worker(0, request, None)
            self.assertEqual(self.app.events.get_nowait()[1][1], 'error')

    def test_worker_project_then_input_then_ready(self):
        window = voice.WindowInfo(11, 'ChatGPT', 'chatgpt.exe', 'Chrome_WidgetWin_1')
        request = targets.RouteRequest(self.app.configured_apps[0], self.app.configured_apps[0]['projects'][0])
        with patch('voice_input.enum_windows', return_value=[window]), patch('voice_input.focus_window', return_value=True), patch('voice_input.get_foreground_hwnd', return_value=11), patch('app_targets.query_ui', return_value={'ok': True}) as ui, patch('voice_input.time.sleep'):
            self.app._configured_route_worker(0, request, None)
            self.assertEqual([call.args[2] for call in ui.call_args_list], ['project', 'focus'])
            self.assertEqual(self.app.events.get_nowait()[1][1], 'ready')

    def test_simple_app_scans_internal_tasks_before_input(self):
        window = voice.WindowInfo(11, 'WorkBuddy', 'workbuddy.exe', 'Chrome_WidgetWin_1')
        request = targets.RouteRequest(self.app.configured_apps[1])
        with patch('voice_input.enum_windows', return_value=[window]), \
             patch('voice_input.focus_window', return_value=True), \
             patch('voice_input.get_foreground_hwnd', return_value=11), \
             patch('app_targets.query_ui', return_value={'ok': True, 'items': [{'name': '日常', 'role': 'ControlType.ListItem'}]}):
            self.app._configured_route_worker(0, request, None)
        event = self.app.events.get_nowait()[1]
        self.assertEqual(event[1], 'select')
        self.assertEqual(event[3][1][0]['name'], '日常')

    def test_open_unknown_app_tries_launch_before_window_scan(self):
        window = voice.WindowInfo(11, '豆包', 'doubao.exe', 'Chrome_WidgetWin_1')
        with patch.object(self.app, '_find_window_by_query', return_value=window) as find, \
             patch.object(self.app, '_open_window_for_input', return_value=True) as open_window, \
             patch.object(self.app, '_show_window_candidates') as candidates:
            self.assertTrue(self.app._open_target_for_input('豆包', launch_if_missing=True))
        find.assert_called_once_with('豆包', launch_if_missing=True)
        open_window.assert_called_once_with(window, action='open')
        candidates.assert_not_called()

    def test_find_only_does_not_launch_unknown_app(self):
        with patch.object(self.app, '_show_window_candidates', return_value=False) as candidates, \
             patch.object(self.app, '_find_window_by_query', return_value=None) as find:
            self.assertFalse(self.app._open_target_for_input('某个程序', launch_if_missing=False))
        candidates.assert_called_once_with('某个程序', action='switch')
        find.assert_called_once_with('某个程序', launch_if_missing=False)

    def test_explicit_non_code_window_can_match_automatic_target(self):
        window = voice.WindowInfo(11, '豆包', 'doubao.exe', 'Chrome_WidgetWin_1')
        self.assertGreater(voice.score_window_match(window, '豆包', allow_non_code=True), 0)

    def test_bound_non_code_app_remains_matchable_in_codex_mode(self):
        self.app.target_mode_var.set(voice.TARGET_MODE_CODEX)
        window = voice.WindowInfo(11, 'WorkBuddy', 'workbuddy.exe', 'Chrome_WidgetWin_1')
        with patch('voice_input.enum_windows', return_value=[window]):
            matches = self.app._window_matches('WorkBuddy')
            self.assertTrue(self.app._wake_window_available('WorkBuddy', launch_if_missing=False))
        self.assertEqual([item.hwnd for _, item in matches], [11])

    def test_failure_keeps_pending_clear(self):
        request = targets.RouteRequest(self.app.configured_apps[0])
        self.app.configured_route_busy = True
        self.app.pending_target_hwnd = 123
        self.app._finish_configured_route((0, 'error', request, 'input missing'))
        self.assertIsNone(self.app.pending_target_hwnd)
        self.assertFalse(self.app.configured_route_busy)
        self.assertNotIn('等待输入', self.app.status_var.get())

    def test_dialog_preserves_apps_projects_and_fields(self):
        saved = []
        dialog = TargetSettings(self.app, fixture_apps(), lambda value: saved.append(targets.validate_apps(value)) or saved[-1], lambda: [], voice.TARGET_UI_SCRIPT)
        self.app.update()
        dialog.vars['input_name'].set('Chat input')
        dialog.tree.selection_set('hunter')
        self.app.update()
        dialog.vars['ui_name'].set('Trading project')
        dialog.save()
        self.assertEqual(saved[0][0]['input_name'], 'Chat input')
        self.assertEqual(saved[0][0]['projects'][0]['ui_name'], 'Trading project')
        self.assertEqual(len(saved[0]), 2)
        self.app.update()
        dialog.vars['ui_name'].set('Updated twice')
        dialog.save()
        self.assertEqual(saved[1][0]['projects'][0]['ui_name'], 'Updated twice')
        dialog.destroy()

    def test_stop_invalidates_pending_route_completion(self):
        request = targets.RouteRequest(self.app.configured_apps[0])
        self.app.configured_route_busy = True
        self.app._stop_offline_recording()
        self.app._finish_configured_route((0, 'ready', request, voice.WindowInfo(11, 'ChatGPT', 'chatgpt.exe', 'Chrome_WidgetWin_1')))
        self.assertIsNone(self.app.pending_target_hwnd)
        self.assertFalse(self.app.configured_route_busy)

    def test_project_launch_waits_for_matching_window(self):
        window = voice.WindowInfo(11, 'ChatGPT', 'chatgpt.exe', 'Chrome_WidgetWin_1')
        request = targets.RouteRequest(self.app.configured_apps[0])
        with patch('voice_input.enum_windows', side_effect=[[], [], [window]]), patch('app_targets.launch') as launch, patch('voice_input.focus_window', return_value=True), patch('voice_input.get_foreground_hwnd', return_value=11), patch('app_targets.query_ui', return_value={'ok': True}):
            self.app._configured_route_worker(0, request, None)
            launch.assert_called_once_with('codex://')
            self.assertEqual(self.app.events.get_nowait()[1][1], 'ready')

    def test_switch_does_not_launch_missing_program(self):
        request = targets.RouteRequest(self.app.configured_apps[0], action='switch')
        with patch('voice_input.enum_windows', return_value=[]), patch('app_targets.launch') as launch:
            self.app._configured_route_worker(0, request, None)
            launch.assert_not_called()
            self.assertEqual(self.app.events.get_nowait()[1][1], 'error')

    def test_no_input_focus_never_marks_ready(self):
        window = voice.WindowInfo(11, 'ChatGPT', 'chatgpt.exe', 'Chrome_WidgetWin_1')
        request = targets.RouteRequest(self.app.configured_apps[0])
        with patch('voice_input.enum_windows', return_value=[window]), patch('voice_input.focus_window', return_value=True), patch('voice_input.get_foreground_hwnd', return_value=11), patch('app_targets.query_ui', return_value={'ok': False}), patch('voice_input.time.monotonic', side_effect=[0, 7]):
            self.app._configured_route_worker(0, request, None)
            self.assertEqual(self.app.events.get_nowait()[1][1], 'error')

    def test_project_link_has_priority_over_existing_app_window(self):
        window = voice.WindowInfo(11, 'ChatGPT', 'chatgpt.exe', 'Chrome_WidgetWin_1')
        project = self.app.configured_apps[0]['projects'][0]
        project['launch'] = 'codex://project/alpha'
        request = targets.RouteRequest(self.app.configured_apps[0], project)
        with patch('voice_input.enum_windows', return_value=[window]), patch('app_targets.launch') as launch, patch('voice_input.focus_window', return_value=True), patch('voice_input.get_foreground_hwnd', return_value=11), patch('app_targets.query_ui', return_value={'ok': True}), patch('voice_input.time.sleep'):
            self.app._configured_route_worker(0, request, None)
            launch.assert_called_once_with('codex://project/alpha')
            self.assertEqual(self.app.events.get_nowait()[1][1], 'ready')


if __name__ == '__main__':
    unittest.main()
