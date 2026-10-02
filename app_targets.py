"""User-configured launch targets and deterministic voice routing."""
from __future__ import annotations

import json
import ntpath
import os
from pathlib import Path
import re
import subprocess
from dataclasses import dataclass
from urllib.parse import urlsplit
import uuid


def normalized(value: str) -> str:
    return re.sub(r"[\s，。！？、；：,.!?;:\-_]+", "", value).casefold()


def launch_address(value: str, check_files: bool = True) -> str:
    value = os.path.expandvars(value.strip().strip('"'))
    if not value or any(char in value for char in "\r\n\x00"):
        raise ValueError("请填写程序启动地址。")
    if ntpath.isabs(value):
        if Path(value).suffix.lower() not in {".exe", ".lnk"}:
            raise ValueError("启动文件请选择 .exe 或 .lnk 快捷方式。")
        if check_files and not Path(value).is_file():
            raise ValueError("启动文件不存在。")
    else:
        parsed = urlsplit(value)
        if not parsed.scheme or parsed.scheme.lower() in {"javascript", "data", "file", "vbscript"}:
            raise ValueError("请填写完整程序路径、快捷方式路径或软件跳转链接。")
        if parsed.scheme.lower() in {'http', 'https'} and not parsed.netloc:
            raise ValueError("网页链接缺少主机地址。")
    return value


def validate_apps(apps: list[dict], check_files: bool = True) -> list[dict]:
    if not isinstance(apps, list):
        raise ValueError("程序配置格式错误。")
    seen_ids, seen_aliases = set(), set()
    clean = []
    for source in apps:
        if not isinstance(source, dict) or any(not isinstance(source.get(key, []), list) for key in ('aliases', 'processes', 'projects')):
            raise ValueError("程序配置格式错误。")
        app = dict(source)
        app['id'] = str(app.get('id') or uuid.uuid4().hex)
        if app['id'] in seen_ids:
            raise ValueError("程序标识重复。")
        seen_ids.add(app['id'])
        for key in ('name', 'launch', 'window_title', 'input_name', 'input_id', 'input_hotkey'):
            app[key] = str(app.get(key, '')).strip()
        if not normalized(app['name']):
            raise ValueError("请填写程序名称。")
        app['launch'] = launch_address(app['launch'], check_files)
        app['aliases'] = [str(alias).strip() for alias in app.get('aliases', []) if str(alias).strip()]
        aliases = {normalized(alias) for alias in [app['name'], *app['aliases']]}
        if aliases & seen_aliases:
            raise ValueError("程序名称或语音别名重复。")
        seen_aliases.update(aliases)
        processes = [str(p).strip().lower() for p in app.get('processes', []) if str(p).strip()]
        if not processes or any(ntpath.basename(p) != p or not p.endswith('.exe') for p in processes):
            raise ValueError("请填写目标进程名，例如 Codex.exe，多项用逗号分隔。")
        app['processes'] = processes
        app['projects'] = []
        project_aliases = set()
        for item in source.get('projects', []):
            if not isinstance(item, dict) or not isinstance(item.get('aliases', []), list):
                raise ValueError("项目配置格式错误。")
            project = {key: str(item.get(key, '')).strip() for key in ('name', 'launch', 'window_title', 'ui_name', 'ui_id')}
            project['id'] = str(item.get('id') or uuid.uuid4().hex)
            if project['id'] in seen_ids:
                raise ValueError("项目标识重复。")
            seen_ids.add(project['id'])
            project['aliases'] = [str(a).strip() for a in item.get('aliases', []) if str(a).strip()]
            if not normalized(project['name']):
                raise ValueError("请填写项目名称。")
            aliases = {normalized(a) for a in [project['name'], *project['aliases']]}
            if aliases & project_aliases:
                raise ValueError("同一程序内的项目名称或别名重复。")
            project_aliases.update(aliases)
            if project['launch']:
                project['launch'] = launch_address(project['launch'], check_files)
            if not any(project[key] for key in ('window_title', 'ui_name', 'ui_id')):
                raise ValueError("项目至少填写窗口标题关键词或侧栏项目名称。")
            app['projects'].append(project)
        clean.append(app)
    return clean


def load_apps(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('apps'), list):
        raise ValueError("程序配置版本或格式错误。")
    # Missing executables must not discard the user's saved configuration.
    return validate_apps(data['apps'], check_files=False)


def save_apps(path: Path, apps: list[dict]) -> list[dict]:
    apps = validate_apps(apps)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'version': 1, 'apps': apps}, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
    return apps


def launch(value: str) -> None:
    value = launch_address(value)
    if ntpath.isabs(value) and value.lower().endswith('.exe'):
        subprocess.Popen([value], cwd=str(Path(value).parent), stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=0x08000000)
    else:
        os.startfile(value)


def matches_app(window, app: dict) -> bool:
    return (window.process.lower() in app.get('processes', [])
            and normalized(app.get('window_title', '')) in normalized(window.title))


def matching_windows(windows, app: dict, project: dict | None = None):
    matches = [w for w in windows if matches_app(w, app)]
    if project and project.get('window_title'):
        matches = [w for w in matches if normalized(project['window_title']) in normalized(w.title)]
    return matches


@dataclass
class RouteRequest:
    app: dict | None = None
    project: dict | None = None
    text: str = ''
    error: str = ''
    action: str = 'open'
    dynamic_query: str = ''


def resolve_command(text: str, apps: list[dict], last_app_id: str = '') -> RouteRequest | None:
    match = re.match(r'^\s*(?:请)?(?P<verb>打开|切换到|切到|进入|找到|查找)\s*(.+?)\s*[。！!，,]*$', text, re.I)
    if not match:
        return None
    verb = match.group('verb')
    action = 'open' if verb == '打开' else 'switch'
    find_in_current_app = verb in {'找到', '查找'}
    body = match.group(2)
    payload = ''
    split = re.split(r'(?:然后输入|并输入|开始输入|请输入)', body, maxsplit=1)
    if len(split) == 2:
        body, payload = split
    compact = normalized(body)
    app_matches = []
    for app in apps:
        for alias in [app['name'], *app.get('aliases', [])]:
            term = normalized(alias)
            if term and compact.startswith(term):
                app_matches.append((len(term), app, compact[len(term):]))
    if app_matches:
        _, app, remainder = max(app_matches, key=lambda row: row[0])
        if remainder in ('', '窗口', '输入', '对话框', '窗口输入'):
            return RouteRequest(app, text=payload, action=action)
        remainder = re.sub(r'^(?:(?:然后)?(?:切换到|切到|进入)|的|项目)+', '', remainder)
        remainder = re.sub(r'(?:项目|窗口|对话框)$', '', remainder)
        pairs = [(app, project) for project in app.get('projects', [])]
    else:
        remainder = re.sub(r'^项目', '', compact)
        remainder = re.sub(r'项目$', '', remainder)
        preferred = [app for app in apps if app['id'] == last_app_id]
        if find_in_current_app and preferred:
            remainder = re.sub(r'(?:对话框|聊天框|窗口|里面|里)$', '', remainder)
            if len(remainder) >= 2:
                return RouteRequest(
                    app=preferred[0],
                    action='switch',
                    dynamic_query=remainder,
                )
        pairs = [(app, p) for app in (preferred or apps) for p in app.get('projects', [])]
    exact, partial = [], []
    for app, project in pairs:
        aliases = [normalized(a) for a in [project['name'], *project.get('aliases', [])]]
        if remainder in aliases:
            exact.append((app, project))
        elif len(remainder) >= 2 and any(remainder in a for a in aliases):
            partial.append((app, project))
    matches = exact or partial
    if len(matches) == 1:
        return RouteRequest(*matches[0], text=payload, action=action)
    if matches:
        return RouteRequest(error='项目名称有多个匹配，请说完整名称：' + '、'.join(f"{a['name']} {p['name']}" for a, p in matches))
    if app_matches and not app.get('projects'):
        # A simple program binding does not require fixed project/window
        # metadata. The running app will be scanned after it opens, and the
        # spoken remainder selects a visible task or dialog dynamically.
        return RouteRequest(app=app, text=payload, action=action, dynamic_query=remainder)
    if app_matches or compact.startswith('项目'):
        return RouteRequest(error='没有找到这个项目配置，请先在程序与项目中添加。')
    return None


def query_ui(script: Path, hwnd: int, operation: str, **selectors) -> dict:
    request = {'hwnd': int(hwnd), 'operation': operation, **selectors}
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
        input=json.dumps(request, ensure_ascii=True), capture_output=True, encoding='utf-8',
        creationflags=0x08000000, timeout=12,
    )
    if result.returncode:
        raise RuntimeError('界面控件读取失败。')
    try:
        return json.loads(result.stdout.strip().lstrip('\ufeff'))
    except json.JSONDecodeError as exc:
        raise RuntimeError('界面控件返回格式错误。') from exc


def query_ocr(script: Path, image_path: Path) -> dict:
    request = {'path': str(image_path)}
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
        input=json.dumps(request, ensure_ascii=True), capture_output=True, encoding='utf-8',
        creationflags=0x08000000, timeout=15,
    )
    if result.returncode:
        raise RuntimeError('屏幕文字读取失败。')
    try:
        return json.loads(result.stdout.strip().lstrip('\ufeff'))
    except json.JSONDecodeError as exc:
        raise RuntimeError('屏幕文字读取返回格式错误。') from exc
