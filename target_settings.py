"""Local application/project mappings editor."""
from __future__ import annotations

import copy
from pathlib import Path
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import uuid

from app_targets import matching_windows, query_ui


class TargetSettings(tk.Toplevel):
    def __init__(self, parent, apps, save, windows, ui_script, process_path=None, test_route=None,
                 foreground_window=None):
        super().__init__(parent)
        self.title('程序与项目')
        self.configure(bg='#292C31')
        self.geometry('820x620')
        self.minsize(740, 590)
        self.attributes('-topmost', True)
        self.transient(parent)
        style = ttk.Style(self)
        style.configure('Targets.TFrame', background='#292C31')
        style.configure('Targets.TLabel', background='#292C31', foreground='#F3F5F7')
        style.configure('Targets.Treeview', background='#30353D', fieldbackground='#30353D',
                        foreground='#F3F5F7', rowheight=25, font=('Microsoft YaHei UI', 9))
        style.map('Targets.Treeview', background=[('selected', '#496B7B')], foreground=[('selected', 'white')])
        style.configure('Targets.Treeview.Heading', background='#353A42', foreground='#F3F5F7')
        self.apps = copy.deepcopy(apps)
        self.save_callback = save
        self.windows = windows
        self.ui_script = ui_script
        self.process_path = process_path
        self.test_route = test_route
        self.foreground_window = foreground_window
        self._bind_results = []
        self._bind_pending = False
        self._bind_kind = 'app'
        self.selected = None
        self.vars = {name: tk.StringVar() for name in (
            'name', 'aliases', 'launch', 'processes', 'window_title', 'input_name', 'input_id', 'input_hotkey', 'ui_name', 'ui_id')}
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        left = ttk.Frame(self, padding=10, style='Targets.TFrame')
        left.grid(row=0, column=0, sticky='ns')
        left.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(left, show='tree', selectmode='browse', height=15, style='Targets.Treeview')
        self.tree.column('#0', width=185)
        self.tree.grid(row=0, column=0, columnspan=2, sticky='ns')
        tree_scroll = ttk.Scrollbar(left, orient='vertical', command=self.tree.yview)
        tree_scroll.grid(row=0, column=2, sticky='ns')
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.bind('<<TreeviewSelect>>', self.select)
        ttk.Button(left, text='添加程序', command=self.add_app).grid(row=1, column=0, columnspan=2, pady=8)
        ttk.Button(left, text='删除所选', command=self.delete).grid(row=2, column=0, columnspan=2, sticky='ew')
        form = ttk.Frame(self, padding=12, style='Targets.TFrame')
        form.grid(row=0, column=1, sticky='nsew')
        form.columnconfigure(1, weight=1)
        self.rows = {}
        # New bindings only need app identity. Window/task/input details are
        # discovered after launch and spoken selection, so keep those legacy
        # fields out of the normal editor surface.
        fields = [('name', '名称'), ('aliases', '语音别名'), ('launch', '启动地址'),
                  ('processes', '进程名')]
        for row, (key, label) in enumerate(fields):
            label_widget = ttk.Label(form, text=label, style='Targets.TLabel')
            label_widget.grid(row=row, column=0, sticky='w', pady=6)
            entry = ttk.Entry(form, textvariable=self.vars[key])
            entry.grid(row=row, column=1, sticky='ew', padx=(12, 0), pady=6)
            self.rows[key] = (label_widget, entry)
        self.vars['launch'].trace_add('write', self.infer_process)
        ttk.Button(form, text='选择程序或快捷方式', command=self.browse).grid(row=4, column=1, sticky='e', pady=8)
        ttk.Label(form, text='绑定程序即可；启动后会扫描软件窗口，等待你说出任务或对话框名称。',
                  style='Targets.TLabel', wraplength=430).grid(row=5, column=1, sticky='e', pady=(0, 8))
        self.bind_button = ttk.Button(form, text='一键绑定当前窗口', command=self.bind_current_window)
        self.bind_button.grid(row=6, column=1, sticky='e', pady=(8, 2))
        footer = ttk.Frame(self, padding=10, style='Targets.TFrame')
        footer.grid(row=1, column=0, columnspan=2, sticky='ew')
        self.status = tk.StringVar()
        ttk.Label(footer, textvariable=self.status, wraplength=530, style='Targets.TLabel').pack(side='left')
        ttk.Button(footer, text='保存', command=self.save).pack(side='right')
        if test_route:
            ttk.Button(footer, text='保存并测试打开', command=self.test).pack(side='right', padx=8)
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        self.rebuild()

    def infer_process(self, *_):
        if self.selected and not self.selected[1] and not self.vars['processes'].get():
            path = Path(self.vars['launch'].get().strip('"'))
            if path.suffix.lower() == '.exe':
                self.vars['processes'].set(path.name)

    def flush(self):
        if not self.selected:
            return
        app, project = self.selected
        item = project or app
        keys = ('name', 'launch', 'window_title', 'ui_name', 'ui_id') if project else (
            'name', 'launch', 'window_title', 'input_name', 'input_id', 'input_hotkey')
        for key in keys:
            item[key] = self.vars[key].get().strip()
        item['aliases'] = [v.strip() for v in re.split('[,，;；]', self.vars['aliases'].get()) if v.strip()]
        if not project:
            item['processes'] = [v.strip().lower() for v in re.split('[,，;；]', self.vars['processes'].get()) if v.strip()]
        self.tree.item(item['id'], text=item['name'] or '未命名')

    def rebuild(self, select_id=''):
        self.selected = None
        self.tree.delete(*self.tree.get_children())
        for app in self.apps:
            self.tree.insert('', 'end', iid=app['id'], text=app['name'], open=True)
            for project in app.get('projects', []):
                self.tree.insert(app['id'], 'end', iid=project['id'], text=project['name'])
        children = self.tree.get_children()
        if select_id or children:
            self.tree.selection_set(select_id or children[0])
        else:
            for var in self.vars.values():
                var.set('')

    def select(self, _event=None):
        ids = self.tree.selection()
        if not ids:
            return
        self.flush()
        for app in self.apps:
            items = [(app, None), *((app, p) for p in app.get('projects', []))]
            for pair in items:
                item = pair[1] or pair[0]
                if item['id'] != ids[0]:
                    continue
                self.selected = pair
                for key, var in self.vars.items():
                    value = item.get(key, '')
                    var.set(', '.join(value) if isinstance(value, list) else value)
                for key, widgets in self.rows.items():
                    visible = key in {'name', 'aliases', 'launch', 'processes'}
                    for widget in widgets:
                        widget.grid() if visible else widget.grid_remove()
                self.status.set('项目' if pair[1] else '程序')
                return

    def add_app(self):
        self.flush()
        app = {'id': uuid.uuid4().hex, 'name': '新程序', 'projects': [], 'aliases': [], 'processes': []}
        self.apps.append(app)
        self.rebuild(app['id'])

    def add_project(self):
        self.flush()
        if not self.selected:
            return
        app = self.selected[0]
        project = {'id': uuid.uuid4().hex, 'name': '新项目', 'aliases': []}
        app.setdefault('projects', []).append(project)
        self.rebuild(project['id'])

    def delete(self):
        if not self.selected:
            return
        app, project = self.selected
        if not messagebox.askyesno('删除配置', '删除所选配置？', parent=self):
            return
        (app['projects'] if project else self.apps).remove(project or app)
        self.selected = None
        self.rebuild()

    def browse(self):
        path = filedialog.askopenfilename(parent=self, title='选择启动文件',
                                         filetypes=[('程序与快捷方式', '*.exe *.lnk')])
        if path:
            self.vars['launch'].set(path)

    def save(self):
        self.flush()
        selected_id = (self.selected[1] or self.selected[0])['id'] if self.selected else ''
        try:
            self.apps = self.save_callback(self.apps)
        except (ValueError, OSError) as exc:
            messagebox.showerror('配置未保存', str(exc), parent=self)
            return False
        self.rebuild(selected_id)
        self.status.set('已保存')
        return True

    def test(self):
        if not self.selected:
            return
        app_id = self.selected[0]['id']
        project_id = self.selected[1]['id'] if self.selected[1] else ''
        if self.save():
            app = next(item for item in self.apps if item['id'] == app_id)
            project = next((item for item in app.get('projects', []) if item['id'] == project_id), None)
            self.destroy()
            self.test_route(app, project)

    def pick_running(self):
        if not self.selected or self.selected[1]:
            return
        app = self.selected[0]
        windows = self.windows()
        popup = tk.Toplevel(self)
        popup.configure(bg='#292C31')
        popup.title('选择运行中的程序')
        popup.geometry('620x300')
        popup.attributes('-topmost', True)
        popup.transient(self)
        tree = ttk.Treeview(popup, columns=('process', 'title'), show='headings', selectmode='browse', style='Targets.Treeview')
        tree.heading('process', text='进程')
        tree.heading('title', text='窗口')
        tree.column('process', width=180)
        tree.column('title', width=400)
        tree.pack(fill='both', expand=True, padx=10, pady=10)
        for index, window in enumerate(windows):
            tree.insert('', 'end', iid=str(index), values=(window.process, window.title))

        def use():
            selection = tree.selection()
            if not selection or self.selected != (app, None):
                return
            window = windows[int(selection[0])]
            self.vars['processes'].set(window.process)
            if not self.vars['launch'].get() and self.process_path:
                self.vars['launch'].set(self.process_path(window))
            if window.process.lower() in {'chrome.exe', 'msedge.exe', 'firefox.exe'}:
                self.vars['window_title'].set(window.title)
            popup.destroy()

        ttk.Button(popup, text='使用此程序', command=use).pack(anchor='e', padx=10, pady=(0, 10))

    def bind_current_window(self):
        if not self.selected:
            self.add_app()
        elif self.selected[1]:
            app = self.selected[0]
            self.tree.selection_set(app['id'])
            self.select()
        if not self.foreground_window or not self.process_path:
            messagebox.showerror('一键绑定', '当前版本没有可用的窗口绑定接口。', parent=self)
            return
        self.flush()
        self._start_binding('app')

    def bind_current_project(self):
        if not self.selected:
            self.add_app()
            self.add_project()
        elif not self.selected[1]:
            self.add_project()
        if not self.foreground_window or not self.process_path:
            messagebox.showerror('一键绑定', '当前版本没有可用的窗口绑定接口。', parent=self)
            return
        self.flush()
        self._start_binding('project')

    def _start_binding(self, kind):
        self._bind_kind = kind
        self.status.set('点击确定后，工具会隐藏 2.5 秒；请切到目标程序并点中输入框。')
        if kind == 'project':
            self.status.set('点击确定后，工具会隐藏 2.5 秒；请切到目标程序并点中任务名称。')
        if not messagebox.askokcancel(
                '一键绑定当前任务' if kind == 'project' else '一键绑定当前窗口',
                '点击“确定”后窗口会暂时隐藏。\n请在 2.5 秒内切到目标程序，并点一下任务名称。'
                if kind == 'project' else
                '点击“确定”后窗口会暂时隐藏。\n请在 2.5 秒内切到目标程序，并点一下要输入文字的位置。',
                parent=self):
            return
        self._bind_pending = True
        self.bind_button.configure(state=tk.DISABLED)
        self.withdraw()
        self.after(2500, self._capture_binding_window)

    def _capture_binding_window(self):
        if not self.winfo_exists() or not self._bind_pending:
            return
        window = self.foreground_window()
        if window is None or not window.process:
            self._finish_binding(None, '', {'ok': False, 'reason': 'window_missing'})
            return
        try:
            launch = str(self.process_path(window) or '').strip()
        except Exception:
            launch = ''
        if not launch:
            self._finish_binding(window, '', {'ok': False, 'reason': 'launch_missing'})
            return
        self._bind_results = []
        threading.Thread(
            target=self._bind_query_worker,
            args=(window, launch),
            daemon=True,
        ).start()
        self.after(100, self._poll_binding)

    def _bind_query_worker(self, window, launch):
        try:
            operation = 'bind_project' if self._bind_kind == 'project' else 'bind'
            result = query_ui(self.ui_script, window.hwnd, operation)
        except Exception as exc:
            result = {'ok': False, 'reason': str(exc)}
        self._bind_results.append((window, launch, result))

    def _poll_binding(self):
        if not self.winfo_exists() or not self._bind_pending:
            return
        if not self._bind_results:
            self.after(100, self._poll_binding)
            return
        window, launch, result = self._bind_results.pop(0)
        self._finish_binding(window, launch, result)

    def _finish_binding(self, window, launch, result):
        self._bind_pending = False
        if not self.winfo_exists():
            return
        self.deiconify()
        self.lift()
        self.bind_button.configure(state='normal')
        if window is None:
            self.status.set('没有捕获到目标窗口，请重试。')
            return
        app = self.selected[0] if self.selected and not self.selected[1] else None
        project = self.selected[1] if self.selected else None
        if app is None and project is None:
            self.status.set('程序选择已变化，请重试。')
            return
        if project is not None:
            app = self.selected[0]
            app['launch'] = launch
            app['processes'] = [window.process.lower()]
            if app.get('name', '').strip() in {'', '新程序'}:
                app['name'] = Path(window.process).stem or window.title or '新程序'
            items = result.get('items') if isinstance(result, dict) else None
            if not result.get('ok') or not items:
                self.status.set('未识别到任务名称，请点任务列表中的名称后重试。')
                return
            item = items[0]
            self.vars['name'].set(str(item.get('name') or project.get('name') or '新项目'))
            self.vars['ui_name'].set(str(item.get('name') or ''))
            self.vars['ui_id'].set(str(item.get('id') or ''))
            self.status.set('已识别任务，正在保存绑定。')
            self.save()
            return
        if app.get('name', '').strip() in {'', '新程序'}:
            app['name'] = Path(window.process).stem or window.title or '新程序'
            self.vars['name'].set(app['name'])
        self.vars['launch'].set(launch)
        self.vars['processes'].set(window.process)
        if window.process.lower() in {'chrome.exe', 'msedge.exe', 'firefox.exe'}:
            self.vars['window_title'].set(window.title)
        items = result.get('items') if isinstance(result, dict) else None
        if result.get('ok') and items:
            item = items[0]
            self.vars['input_name'].set(str(item.get('name') or ''))
            self.vars['input_id'].set(str(item.get('id') or ''))
            self.status.set('已识别输入框，正在保存绑定。')
        else:
            self.vars['input_name'].set('')
            self.vars['input_id'].set('')
            self.status.set('程序已识别，但输入框未自动读取；已保存程序绑定，可稍后读取控件。')
        self.save()

    def inspect(self):
        self.flush()
        if not self.selected:
            return
        app, project = self.selected
        windows = matching_windows(self.windows(), app)
        popup = tk.Toplevel(self)
        popup.configure(bg='#292C31')
        popup.title('窗口与控件')
        popup.geometry('680x460')
        popup.attributes('-topmost', True)
        popup.transient(self)
        popup.columnconfigure(0, weight=1)
        popup.rowconfigure(1, weight=1)
        pick = ttk.Combobox(popup, state='readonly', values=[f'{i + 1}. {w.title}' for i, w in enumerate(windows)])
        pick.grid(row=0, column=0, sticky='ew', padx=10, pady=10)
        tree = ttk.Treeview(popup, columns=('role', 'name', 'id'), show='headings', style='Targets.Treeview')
        for column, title in [('role', '类型'), ('name', '名称'), ('id', '控件 ID')]:
            tree.heading(column, text=title)
            tree.column(column, width=190)
        tree.grid(row=1, column=0, sticky='nsew', padx=10)
        scroll = ttk.Scrollbar(popup, command=tree.yview)
        scroll.grid(row=1, column=1, sticky='ns')
        tree.configure(yscrollcommand=scroll.set)
        status = tk.StringVar(value='未找到匹配进程的窗口' if not windows else '')
        ttk.Label(popup, textvariable=status, style='Targets.TLabel').grid(row=2, column=0, sticky='w', padx=10)
        results = []

        def load(_event=None):
            tree.delete(*tree.get_children())
            status.set('正在读取界面')
            index = pick.current()
            if index < 0:
                return
            def work():
                try:
                    result = query_ui(self.ui_script, windows[index].hwnd, 'inspect')
                except Exception as exc:
                    result = {'ok': False, 'reason': str(exc)}
                results.append((index, result))
            threading.Thread(target=work, daemon=True).start()

        def poll():
            if not popup.winfo_exists():
                return
            while results:
                index, result = results.pop(0)
                if index != pick.current():
                    continue
                tree.delete(*tree.get_children())
                for item in result.get('items', []):
                    tree.insert('', 'end', values=(item['role'], item['name'], item['id']))
                status.set('已读取' if result.get('ok') else '控件读取失败')
            popup.after(100, poll)

        def use():
            if self.selected != (app, project):
                return
            rows = tree.selection()
            if not rows:
                return
            _, name, identity = tree.item(rows[0], 'values')
            self.vars['ui_name' if project else 'input_name'].set(name)
            self.vars['ui_id' if project else 'input_id'].set(identity)
            popup.destroy()

        ttk.Button(popup, text='设为侧栏项目' if project else '设为输入框', command=use).grid(row=3, column=0, sticky='e', padx=10, pady=10)
        pick.bind('<<ComboboxSelected>>', load)
        if windows:
            pick.current(0)
            load()
        poll()
