"""
Stage 3 — Minimal VFS with subdirectory path support

Features:
- Load VFS from a real directory into memory (--vfs)
- Print motd if present
- GUI REPL with commands: ls, cd, exit
- Support nested paths for ls and cd (e.g. ls a/b, cd a/b)
- Relative and absolute paths inside VFS (/ as separator)

Run:
    python stage3_minimal_subdir.py --vfs "C:/path/to/vfs_test"

"""

import os
import sys
import argparse
import shlex
import tkinter as tk
from tkinter import scrolledtext
from typing import Dict, Optional

# ---------- args ----------
parser = argparse.ArgumentParser()
parser.add_argument('--vfs', required=True, help='Path to VFS source directory')
parser.add_argument('--script', default=None, help='Optional startup script')
args = parser.parse_args()

# ---------- VFS node ----------
class VFSNode:
    def __init__(self, name: str, is_dir: bool):
        self.name = name
        self.is_dir = is_dir
        self.children: Dict[str, VFSNode] = {}
        self.content: str = ''
        self.parent: Optional[VFSNode] = None

    def add_child(self, node: 'VFSNode'):
        node.parent = self
        self.children[node.name] = node

# ---------- build VFS ----------
def build_vfs_from_disk(path: str) -> VFSNode:
    if not os.path.isdir(path):
        raise FileNotFoundError(f'VFS source directory not found: {path}')

    root = VFSNode('/', True)

    def _walk(disk_path: str, node: VFSNode):
        try:
            for entry in sorted(os.listdir(disk_path)):
                full = os.path.join(disk_path, entry)
                if os.path.isdir(full):
                    child = VFSNode(entry, True)
                    node.add_child(child)
                    _walk(full, child)
                else:
                    child = VFSNode(entry, False)
                    try:
                        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                            child.content = f.read()
                    except Exception:
                        child.content = ''
                    node.add_child(child)
        except PermissionError:
            pass

    _walk(path, root)
    return root

# ---------- path helpers ----------

def split_vfs_path(p: str):
    p = p.replace('\\', '/')
    if p == '' or p == '/':
        return []
    return [part for part in p.split('/') if part != '']


def resolve_vfs_path(cwd: VFSNode, path: str) -> Optional[VFSNode]:
    # absolute path
    if path.startswith('/'):
        # go to root
        node = cwd
        while node.parent is not None:
            node = node.parent
    else:
        node = cwd

    parts = split_vfs_path(path)
    for part in parts:
        if part == '.':
            continue
        if part == '..':
            if node.parent is not None:
                node = node.parent
            continue
        if not node.is_dir:
            return None
        if part not in node.children:
            return None
        node = node.children[part]
    return node

# ---------- GUI ----------
PROMPT_TEMPLATE = 'vfs:{cwd}> '

class ShellGUI(tk.Tk):
    def __init__(self, vfs_root: VFSNode, vfs_path: str, script: Optional[str]=None):
        super().__init__()
        self.vfs_root = vfs_root
        self.cwd = vfs_root
        self.vfs_path = vfs_path
        self.title(f'VFS Minimal — {os.path.basename(vfs_path)}')
        self.geometry('820x480')

        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED)
        self.output.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        frm = tk.Frame(self)
        frm.pack(fill=tk.X, padx=6, pady=(0,6))
        self.prompt_label = tk.Label(frm, text=self.prompt_text())
        self.prompt_label.pack(side=tk.LEFT)
        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(frm, textvariable=self.entry_var)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind('<Return>', self.on_enter)
        self.entry.focus()

        # history
        self.history = []
        self.hist_index = None
        self.entry.bind('<Up>', self.on_up)
        self.entry.bind('<Down>', self.on_down)

        # motd
        if 'motd' in self.vfs_root.children and not self.vfs_root.children['motd'].is_dir:
            self.print_output(self.vfs_root.children['motd'].content + '\n')

        self.print_output(f'[debug] VFS loaded from: {vfs_path}\n')
        self.print_output(f'[debug] entries: {list(self.vfs_root.children.keys())}\n\n')

        if script:
            self.run_script(script)

    def prompt_text(self):
        name = self.cwd.name if self.cwd.parent is not None else '/'
        return PROMPT_TEMPLATE.format(cwd=name)

    def print_output(self, text: str):
        self.output.config(state=tk.NORMAL)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.config(state=tk.DISABLED)
        self.prompt_label.config(text=self.prompt_text())

    def on_up(self, event=None):
        if not self.history:
            return
        if self.hist_index is None:
            self.hist_index = len(self.history)-1
        else:
            self.hist_index = max(0, self.hist_index-1)
        self.entry_var.set(self.history[self.hist_index])
        return 'break'

    def on_down(self, event=None):
        if not self.history or self.hist_index is None:
            return
        self.hist_index = min(len(self.history)-1, self.hist_index+1)
        self.entry_var.set(self.history[self.hist_index])
        return 'break'

    def on_enter(self, event=None):
        line = self.entry_var.get()
        if not line.strip():
            self.print_output(self.prompt_text() + '\n')
            self.entry_var.set('')
            return
        self.print_output(self.prompt_text() + line + '\n')
        self.history.append(line)
        self.hist_index = None
        self.execute(line)
        self.entry_var.set('')

    def run_script(self, filename: str):
        if not os.path.exists(filename):
            self.print_output(f'[error] Script not found: {filename}\n')
            return
        self.print_output(f'[script] Running {filename}\n')
        with open(filename, 'r', encoding='utf-8') as f:
            for raw in f:
                cmd = raw.strip()
                if not cmd:
                    continue
                self.print_output(self.prompt_text() + cmd + '\n')
                try:
                    self.execute(cmd)
                except Exception as e:
                    self.print_output(f'[script error] {e}\n')

    def execute(self, line: str):
        try:
            tokens = shlex.split(line)
        except Exception as e:
            self.print_output(f'parse error: {e}\n')
            return
        if not tokens:
            return
        cmd, *args = tokens
        if cmd == 'exit':
            return self.cmd_exit(args)
        elif cmd == 'ls':
            return self.cmd_ls(args)
        elif cmd == 'cd':
            return self.cmd_cd(args)
        else:
            self.print_output(f'Unknown command: {cmd}\n')

    # --- commands ---
    def cmd_exit(self, args):
        if args:
            self.print_output('exit: unexpected args\n')
            return
        self.print_output('Exiting...\n')
        self.after(200, self.destroy)

    def cmd_ls(self, args):
        target = None
        if not args:
            node = self.cwd
        else:
            target = args[0]
            node = resolve_vfs_path(self.cwd, target)
        if node is None:
            self.print_output(f'ls: cannot access "{target}": No such file or directory\n')
            return
        if not node.is_dir:
            self.print_output(node.name + '\n')
            return
        names = sorted(node.children.keys())
        for n in names:
            child = node.children[n]
            suffix = '/' if child.is_dir else ''
            self.print_output(n + suffix + '\n')

    def cmd_cd(self, args):
        if len(args) > 1:
            self.print_output('cd: too many arguments\n')
            return
        target = args[0] if args else '/'
        node = resolve_vfs_path(self.cwd, target)
        if node is None:
            self.print_output(f'cd: no such file or directory: {target}\n')
            return
        if not node.is_dir:
            self.print_output(f'cd: not a directory: {target}\n')
            return
        self.cwd = node
        self.print_output('')

# ---------- main ----------
if __name__ == '__main__':
    try:
        vfs_root = build_vfs_from_disk(args.vfs)
    except Exception as e:
        print(f'Failed to build VFS: {e}')
        sys.exit(1)

    app = ShellGUI(vfs_root, args.vfs, script=args.script)
    app.mainloop()
"""
Stage 3 — Minimal VFS with subdirectory path support

Features:
- Load VFS from a real directory into memory (--vfs)
- Print motd if present
- GUI REPL with commands: ls, cd, exit
- Support nested paths for ls and cd (e.g. ls a/b, cd a/b)
- Relative and absolute paths inside VFS (/ as separator)

Run:
    python stage3_minimal_subdir.py --vfs "C:/path/to/vfs_test"

"""

import os
import sys
import argparse
import shlex
import tkinter as tk
from tkinter import scrolledtext
from typing import Dict, Optional

# ---------- args ----------
parser = argparse.ArgumentParser()
parser.add_argument('--vfs', required=True, help='Path to VFS source directory')
parser.add_argument('--script', default=None, help='Optional startup script')
args = parser.parse_args()

# ---------- VFS node ----------
class VFSNode:
    def __init__(self, name: str, is_dir: bool):
        self.name = name
        self.is_dir = is_dir
        self.children: Dict[str, VFSNode] = {}
        self.content: str = ''
        self.parent: Optional[VFSNode] = None

    def add_child(self, node: 'VFSNode'):
        node.parent = self
        self.children[node.name] = node

# ---------- build VFS ----------
def build_vfs_from_disk(path: str) -> VFSNode:
    if not os.path.isdir(path):
        raise FileNotFoundError(f'VFS source directory not found: {path}')

    root = VFSNode('/', True)

    def _walk(disk_path: str, node: VFSNode):
        try:
            for entry in sorted(os.listdir(disk_path)):
                full = os.path.join(disk_path, entry)
                if os.path.isdir(full):
                    child = VFSNode(entry, True)
                    node.add_child(child)
                    _walk(full, child)
                else:
                    child = VFSNode(entry, False)
                    try:
                        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                            child.content = f.read()
                    except Exception:
                        child.content = ''
                    node.add_child(child)
        except PermissionError:
            pass

    _walk(path, root)
    return root

# ---------- path helpers ----------

def split_vfs_path(p: str):
    p = p.replace('\\', '/')
    if p == '' or p == '/':
        return []
    return [part for part in p.split('/') if part != '']


def resolve_vfs_path(cwd: VFSNode, path: str) -> Optional[VFSNode]:
    # absolute path
    if path.startswith('/'):
        # go to root
        node = cwd
        while node.parent is not None:
            node = node.parent
    else:
        node = cwd

    parts = split_vfs_path(path)
    for part in parts:
        if part == '.':
            continue
        if part == '..':
            if node.parent is not None:
                node = node.parent
            continue
        if not node.is_dir:
            return None
        if part not in node.children:
            return None
        node = node.children[part]
    return node

# ---------- GUI ----------
PROMPT_TEMPLATE = 'vfs:{cwd}> '

class ShellGUI(tk.Tk):
    def __init__(self, vfs_root: VFSNode, vfs_path: str, script: Optional[str]=None):
        super().__init__()
        self.vfs_root = vfs_root
        self.cwd = vfs_root
        self.vfs_path = vfs_path
        self.title(f'VFS Minimal — {os.path.basename(vfs_path)}')
        self.geometry('820x480')

        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED)
        self.output.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        frm = tk.Frame(self)
        frm.pack(fill=tk.X, padx=6, pady=(0,6))
        self.prompt_label = tk.Label(frm, text=self.prompt_text())
        self.prompt_label.pack(side=tk.LEFT)
        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(frm, textvariable=self.entry_var)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind('<Return>', self.on_enter)
        self.entry.focus()

        # history
        self.history = []
        self.hist_index = None
        self.entry.bind('<Up>', self.on_up)
        self.entry.bind('<Down>', self.on_down)

        # motd
        if 'motd' in self.vfs_root.children and not self.vfs_root.children['motd'].is_dir:
            self.print_output(self.vfs_root.children['motd'].content + '\n')

        self.print_output(f'[debug] VFS loaded from: {vfs_path}\n')
        self.print_output(f'[debug] entries: {list(self.vfs_root.children.keys())}\n\n')

        if script:
            self.run_script(script)

    def prompt_text(self):
        name = self.cwd.name if self.cwd.parent is not None else '/'
        return PROMPT_TEMPLATE.format(cwd=name)

    def print_output(self, text: str):
        self.output.config(state=tk.NORMAL)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.config(state=tk.DISABLED)
        self.prompt_label.config(text=self.prompt_text())

    def on_up(self, event=None):
        if not self.history:
            return
        if self.hist_index is None:
            self.hist_index = len(self.history)-1
        else:
            self.hist_index = max(0, self.hist_index-1)
        self.entry_var.set(self.history[self.hist_index])
        return 'break'

    def on_down(self, event=None):
        if not self.history or self.hist_index is None:
            return
        self.hist_index = min(len(self.history)-1, self.hist_index+1)
        self.entry_var.set(self.history[self.hist_index])
        return 'break'

    def on_enter(self, event=None):
        line = self.entry_var.get()
        if not line.strip():
            self.print_output(self.prompt_text() + '\n')
            self.entry_var.set('')
            return
        self.print_output(self.prompt_text() + line + '\n')
        self.history.append(line)
        self.hist_index = None
        self.execute(line)
        self.entry_var.set('')

    def run_script(self, filename: str):
        if not os.path.exists(filename):
            self.print_output(f'[error] Script not found: {filename}\n')
            return
        self.print_output(f'[script] Running {filename}\n')
        with open(filename, 'r', encoding='utf-8') as f:
            for raw in f:
                cmd = raw.strip()
                if not cmd:
                    continue
                self.print_output(self.prompt_text() + cmd + '\n')
                try:
                    self.execute(cmd)
                except Exception as e:
                    self.print_output(f'[script error] {e}\n')

    def execute(self, line: str):
        try:
            tokens = shlex.split(line)
        except Exception as e:
            self.print_output(f'parse error: {e}\n')
            return
        if not tokens:
            return
        cmd, *args = tokens
        if cmd == 'exit':
            return self.cmd_exit(args)
        elif cmd == 'ls':
            return self.cmd_ls(args)
        elif cmd == 'cd':
            return self.cmd_cd(args)
        else:
            self.print_output(f'Unknown command: {cmd}\n')

    # --- commands ---
    def cmd_exit(self, args):
        if args:
            self.print_output('exit: unexpected args\n')
            return
        self.print_output('Exiting...\n')
        self.after(200, self.destroy)

    def cmd_ls(self, args):
        target = None
        if not args:
            node = self.cwd
        else:
            target = args[0]
            node = resolve_vfs_path(self.cwd, target)
        if node is None:
            self.print_output(f'ls: cannot access "{target}": No such file or directory\n')
            return
        if not node.is_dir:
            self.print_output(node.name + '\n')
            return
        names = sorted(node.children.keys())
        for n in names:
            child = node.children[n]
            suffix = '/' if child.is_dir else ''
            self.print_output(n + suffix + '\n')

    def cmd_cd(self, args):
        if len(args) > 1:
            self.print_output('cd: too many arguments\n')
            return
        target = args[0] if args else '/'
        node = resolve_vfs_path(self.cwd, target)
        if node is None:
            self.print_output(f'cd: no such file or directory: {target}\n')
            return
        if not node.is_dir:
            self.print_output(f'cd: not a directory: {target}\n')
            return
        self.cwd = node
        self.print_output('')

# ---------- main ----------
if __name__ == '__main__':
    try:
        vfs_root = build_vfs_from_disk(args.vfs)
    except Exception as e:
        print(f'Failed to build VFS: {e}')
        sys.exit(1)

    app = ShellGUI(vfs_root, args.vfs, script=args.script)
    app.mainloop()
"""
Stage 3 — Minimal VFS-enabled shell emulator

Что делает (минимальный набор):
- Загружает VFS из реальной директории (в память)
- При старте печатает motd (если есть)
- Реализует команды: ls, cd, pwd, exit
- Поддерживает относительные и абсолютные пути внутри VFS (разделитель '/')

Запуск:
    python stage3_minimal.py --vfs "C:/путь/к/vfs_test"

Примеры в GUI:
    ls
    ls folder1
    cd folder2/subfolder
    pwd
    cd ..
    exit

Сделай коммит после проверки:
    git add stage3_minimal.py
    git commit -m "stage3: minimal VFS (ls, cd, pwd, motd, exit)"
"""

import os
import sys
import argparse
import shlex
import tkinter as tk
from tkinter import scrolledtext
from typing import Dict, Optional

# ------------ Аргументы -------------
parser = argparse.ArgumentParser()
parser.add_argument('--vfs', required=True, help='Путь к директории-источнику VFS')
args = parser.parse_args()

# ------------ VFS в памяти -------------
class VFSNode:
    def __init__(self, name: str, is_dir: bool):
        self.name = name
        self.is_dir = is_dir
        self.children: Dict[str, VFSNode] = {}
        self.content: str = ''
        self.parent: Optional[VFSNode] = None

    def add_child(self, node: 'VFSNode'):
        node.parent = self
        self.children[node.name] = node


def build_vfs_from_disk(path: str) -> VFSNode:
    if not os.path.isdir(path):
        raise FileNotFoundError(f'VFS source directory not found: {path}')

    root = VFSNode('/', True)

    def _walk(disk_path: str, node: VFSNode):
        try:
            for entry in sorted(os.listdir(disk_path)):
                full = os.path.join(disk_path, entry)
                if os.path.isdir(full):
                    child = VFSNode(entry, True)
                    node.add_child(child)
                    _walk(full, child)
                else:
                    child = VFSNode(entry, False)
                    try:
                        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                            child.content = f.read()
                    except Exception:
                        child.content = ''
                    node.add_child(child)
        except PermissionError:
            pass

    _walk(path, root)
    return root

# ------------ Путь и утилиты -------------

def split_vfs_path(p: str):
    p = p.replace('\\', '/')
    if p == '':
        return []
    return [part for part in p.split('/') if part != '']


def resolve_vfs_path(cwd: VFSNode, path: str) -> Optional[VFSNode]:
    # абсолютный
    if path.startswith('/'):
        node = cwd
        while node.parent is not None:
            node = node.parent
    else:
        node = cwd

    parts = split_vfs_path(path)
    for part in parts:
        if part == '.':
            continue
        if part == '..':
            if node.parent is not None:
                node = node.parent
            continue
        if not node.is_dir:
            return None
        if part not in node.children:
            return None
        node = node.children[part]
    return node

# ------------ GUI и команды -------------
PROMPT_TEMPLATE = 'vfs:{cwd}> '

class ShellGUI(tk.Tk):
    def __init__(self, vfs_root: VFSNode, vfs_path: str):
        super().__init__()
        self.vfs_root = vfs_root
        self.cwd = vfs_root
        self.vfs_path = vfs_path
        self.title(f'VFS Minimal — {os.path.basename(vfs_path)}')
        self.geometry('820x480')

        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED)
        self.output.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        frm = tk.Frame(self)
        frm.pack(fill=tk.X, padx=6, pady=(0,6))
        self.prompt = tk.Label(frm, text=self.prompt_text())
        self.prompt.pack(side=tk.LEFT)
        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(frm, textvariable=self.entry_var)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind('<Return>', self.on_enter)
        self.entry.focus()

        # history
        self.history = []
        self.hist_index = None
        self.entry.bind('<Up>', self.on_up)
        self.entry.bind('<Down>', self.on_down)

        # motd
        if 'motd' in self.vfs_root.children and not self.vfs_root.children['motd'].is_dir:
            self.print_output(self.vfs_root.children['motd'].content + '\n')

        self.print_output(f'[debug] VFS loaded from: {vfs_path}\n')
        self.print_output(f'[debug] entries: {list(self.vfs_root.children.keys())}\n\n')

    def prompt_text(self):
        name = self.cwd.name if self.cwd.parent is not None else '/'
        return PROMPT_TEMPLATE.format(cwd=name)

    def print_output(self, text: str):
        self.output.config(state=tk.NORMAL)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.config(state=tk.DISABLED)
        self.prompt.config(text=self.prompt_text())

    def on_up(self, event=None):
        if not self.history:
            return
        if self.hist_index is None:
            self.hist_index = len(self.history)-1
        else:
            self.hist_index = max(0, self.hist_index-1)
        self.entry_var.set(self.history[self.hist_index])
        return 'break'

    def on_down(self, event=None):
        if not self.history or self.hist_index is None:
            return
        self.hist_index = min(len(self.history)-1, self.hist_index+1)
        self.entry_var.set(self.history[self.hist_index])
        return 'break'

    def on_enter(self, event=None):
        line = self.entry_var.get()
        if not line.strip():
            self.print_output(self.prompt_text() + '\n')
            self.entry_var.set('')
            return
        self.print_output(self.prompt_text() + line + '\n')
        self.history.append(line)
        self.hist_index = None
        self.execute(line)
        self.entry_var.set('')

    def execute(self, line: str):
        try:
            tokens = shlex.split(line)
        except Exception as e:
            self.print_output(f'parse error: {e}\n')
            return
        if not tokens:
            return
        cmd, *args = tokens
        if cmd == 'exit':
            return self.cmd_exit(args)
        if cmd == 'ls':
            return self.cmd_ls(args)
        if cmd == 'cd':
            return self.cmd_cd(args)
        if cmd == 'pwd':
            return self.cmd_pwd(args)
        self.print_output(f'Unknown command: {cmd}\n')

    # commands
    def cmd_exit(self, args):
        if args:
            self.print_output('exit: unexpected args\n')
            return
        self.print_output('Exiting...\n')
        self.after(200, self.destroy)

    def cmd_ls(self, args):
        target = None
        if not args:
            node = self.cwd
        else:
            target = args[0]
            node = resolve_vfs_path(self.cwd, target)
        if node is None:
            self.print_output(f'ls: cannot access "{target}": No such file or directory\n')
            return
        if not node.is_dir:
            self.print_output(node.name + '\n')
            return
        names = sorted(node.children.keys())
        for n in names:
            child = node.children[n]
            suffix = '/' if child.is_dir else ''
            self.print_output(n + suffix + '\n')

    def cmd_cd(self, args):
        if len(args) > 1:
            self.print_output('cd: too many arguments\n')
            return
        target = args[0] if args else '/'
        node = resolve_vfs_path(self.cwd, target)
        if node is None:
            self.print_output(f'cd: no such file or directory: {target}\n')
            return
        if not node.is_dir:
            self.print_output(f'cd: not a directory: {target}\n')
            return
        self.cwd = node
        self.print_output('')

    def cmd_pwd(self, args):
        # build path from cwd
        node = self.cwd
        parts = []
        while node.parent is not None:
            parts.append(node.name)
            node = node.parent
        path = '/' + '/'.join(reversed(parts)) if parts else '/'
        self.print_output(path + '\n')

# ------------ Main ------------
if __name__ == '__main__':
    try:
        vfs_root = build_vfs_from_disk(args.vfs)
    except Exception as e:
        print(f'Failed to build VFS: {e}')
        sys.exit(1)

    app = ShellGUI(vfs_root, args.vfs)
    app.mainloop()

