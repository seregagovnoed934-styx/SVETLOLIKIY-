#!/usr/bin/env python3
"""
stage4.py — VFS Shell Emulator (Stage 4)

Запуск:
    python stage4.py --vfs "C:\path\to\vfs_test" [--script start_script.txt]

Команды в REPL:
    ls [path]         - показать содержимое (поддерживает nested/path)
    cd [path]         - сменить каталог (поддерживает nested/path, .., /)
    history           - показать историю команд в этой сессии (нумерованно)
    date              - вывести текущую дату и время
    cal               - вывести календарь текущего месяца (ASCII)
    help              - краткая помощь
    exit              - выйти из эмулятора

Примечания:
- Все операции с файловой системой выполняются в памяти (VFS загружается из реальной директории).
- motd (в корне VFS) выводится при старте, если существет.
"""
from __future__ import annotations

import os
import sys
import shlex
import argparse
import re
import calendar
from datetime import datetime
import tkinter as tk
from tkinter import scrolledtext
from typing import Dict, Optional

# -------------------- Command-line args --------------------
parser = argparse.ArgumentParser(description="VFS Shell Emulator — Stage 4")
parser.add_argument("--vfs", required=True, help="Путь к директории-источнику VFS")
parser.add_argument("--script", default=None, help="Стартовый скрипт (опционально)")
args = parser.parse_args()

# -------------------- Utilities: env var expansion --------------------
_var_pattern = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def expand_vars(text: str) -> str:
    """Заменяет $VAR на значение из os.environ если есть, иначе оставляет $VAR."""
    def repl(m):
        name = m.group(1)
        return os.environ.get(name, f"${name}")
    return _var_pattern.sub(repl, text)


# -------------------- VFS Node --------------------
class VFSNode:
    def __init__(self, name: str, is_dir: bool):
        self.name = name
        self.is_dir = is_dir
        self.children: Dict[str, VFSNode] = {}  # only for directories
        self.content: str = ""  # only for files
        self.parent: Optional[VFSNode] = None

    def add_child(self, node: "VFSNode"):
        node.parent = self
        self.children[node.name] = node

    def path_from_root(self) -> str:
        node = self
        parts = []
        while node.parent is not None:
            parts.append(node.name)
            node = node.parent
        if not parts:
            return "/"
        return "/" + "/".join(reversed(parts))


# -------------------- Build VFS from disk into memory --------------------
def build_vfs_from_disk(src_path: str) -> VFSNode:
    if not os.path.isdir(src_path):
        raise FileNotFoundError(f"VFS source directory not found: {src_path}")

    root = VFSNode("/", True)

    def _walk(disk_path: str, vfs_node: VFSNode):
        try:
            for entry in sorted(os.listdir(disk_path)):
                full = os.path.join(disk_path, entry)
                if os.path.isdir(full):
                    child = VFSNode(entry, True)
                    vfs_node.add_child(child)
                    _walk(full, child)
                else:
                    child = VFSNode(entry, False)
                    try:
                        with open(full, "r", encoding="utf-8", errors="ignore") as f:
                            child.content = f.read()
                    except Exception:
                        child.content = ""
                    vfs_node.add_child(child)
        except PermissionError:
            # пропускаем папки без прав
            pass

    _walk(src_path, root)
    return root


# -------------------- Path helpers --------------------
def _split_vfs_path(p: str):
    p = p.replace("\\", "/")
    if p == "" or p == "/":
        return []
    return [part for part in p.split("/") if part != ""]


def resolve_vfs_path(cwd: VFSNode, path: str) -> Optional[VFSNode]:
    """
    Resolve path relative to cwd. Supports absolute (/a/b), relative (c/d), . and ..
    Returns None if not found or invalid (e.g. path goes into file).
    """
    if path.startswith("/"):
        # go to root
        node = cwd
        while node.parent is not None:
            node = node.parent
    else:
        node = cwd

    parts = _split_vfs_path(path)
    for part in parts:
        if part == ".":
            continue
        if part == "..":
            if node.parent is not None:
                node = node.parent
            continue
        if not node.is_dir:
            return None
        if part not in node.children:
            return None
        node = node.children[part]
    return node


# -------------------- GUI Shell --------------------
PROMPT_TEMPLATE = "vfs:{cwd}> "


class ShellGUI(tk.Tk):
    def __init__(self, vfs_root: VFSNode, vfs_src_path: str, script: Optional[str] = None):
        super().__init__()
        self.vfs_root = vfs_root
        self.cwd = vfs_root
        self.vfs_src_path = vfs_src_path
        self.script = script

        self.history: list[str] = []

        self.title(f"VFS Stage4 — {os.path.basename(vfs_src_path)}")
        self.geometry("920x540")

        # output area
        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED)
        self.output.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # input area
        frm = tk.Frame(self)
        frm.pack(fill=tk.X, padx=6, pady=(0, 6))
        self.prompt_label = tk.Label(frm, text=self.prompt_text(), anchor="w")
        self.prompt_label.pack(side=tk.LEFT)
        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(frm, textvariable=self.entry_var)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", self.on_enter)
        self.entry.focus()

        # history navigation
        self.entry.bind("<Up>", self.on_history_up)
        self.entry.bind("<Down>", self.on_history_down)
        self.hist_index: Optional[int] = None

        # print motd if exists
        if "motd" in self.vfs_root.children and not self.vfs_root.children["motd"].is_dir:
            self.print_output(self.vfs_root.children["motd"].content + "\n")

        # debug header
        self.print_output(f"[debug] VFS loaded from: {vfs_src_path}\n")
        self.print_output(f"[debug] entries: {list(self.vfs_root.children.keys())}\n\n")

        # run startup script if provided
        if self.script:
            self.run_script(self.script)

    def prompt_text(self) -> str:
        name = self.cwd.name if self.cwd.parent is not None else "/"
        return PROMPT_TEMPLATE.format(cwd=name)

    def print_output(self, text: str):
        self.output.config(state=tk.NORMAL)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.config(state=tk.DISABLED)
        self.prompt_label.config(text=self.prompt_text())

    # ----------------- history navigation -----------------
    def on_history_up(self, event=None):
        if not self.history:
            return
        if self.hist_index is None:
            self.hist_index = len(self.history) - 1
        else:
            self.hist_index = max(0, self.hist_index - 1)
        self.entry_var.set(self.history[self.hist_index])
        return "break"

    def on_history_down(self, event=None):
        if not self.history or self.hist_index is None:
            return
        self.hist_index = min(len(self.history) - 1, self.hist_index + 1)
        self.entry_var.set(self.history[self.hist_index])
        return "break"

    # ----------------- input handling -----------------
    def on_enter(self, event=None):
        line = self.entry_var.get()
        if not line.strip():
            # just print prompt again
            self.print_output(self.prompt_text() + "\n")
            self.entry_var.set("")
            return
        # echo the command
        self.print_output(self.prompt_text() + line + "\n")
        # store history
        self.history.append(line)
        self.hist_index = None
        # execute
        try:
            self.execute_line(line)
        except Exception as e:
            self.print_output(f"[error] Exception during execution: {e}\n")
        self.entry_var.set("")

    def run_script(self, filename: str):
        if not os.path.exists(filename):
            self.print_output(f"[error] Script not found: {filename}\n")
            return
        self.print_output(f"[script] Running {filename}\n")
        try:
            with open(filename, "r", encoding="utf-8") as f:
                for raw in f:
                    cmd_line = raw.rstrip("\n")
                    if not cmd_line.strip():
                        continue
                    self.print_output(self.prompt_text() + cmd_line + "\n")
                    try:
                        self.history.append(cmd_line)
                        self.execute_line(cmd_line)
                    except Exception as e:
                        self.print_output(f"[script error] {e}\n")
        except Exception as e:
            self.print_output(f"[script error] Failed to read script: {e}\n")

    # ----------------- command execution -----------------
    def execute_line(self, line: str):
        # expand env vars first
        expanded = expand_vars(line)
        # tokenize
        try:
            tokens = shlex.split(expanded)
        except Exception as e:
            self.print_output(f"parse error: {e}\n")
            return
        if not tokens:
            return
        cmd, *args = tokens
        # dispatch
        if cmd == "exit":
            return self.cmd_exit(args)
        elif cmd == "ls":
            return self.cmd_ls(args)
        elif cmd == "cd":
            return self.cmd_cd(args)
        elif cmd == "history":
            return self.cmd_history(args)
        elif cmd == "date":
            return self.cmd_date(args)
        elif cmd == "cal":
            return self.cmd_cal(args)
        elif cmd == "help":
            return self.cmd_help(args)
        else:
            self.print_output(f"Unknown command: {cmd}\n")

    # ----------------- commands -----------------
    def cmd_exit(self, args):
        if args:
            self.print_output("exit: unexpected arguments\n")
            return
        self.print_output("Exiting...\n")
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
            # file: print name (like ls file)
            self.print_output(node.name + "\n")
            return
        # directory: list children sorted
        for name in sorted(node.children.keys()):
            child = node.children[name]
            suffix = "/" if child.is_dir else ""
            self.print_output(name + suffix + "\n")

    def cmd_cd(self, args):
        if len(args) > 1:
            self.print_output("cd: too many arguments\n")
            return
        target = args[0] if args else "/"
        node = resolve_vfs_path(self.cwd, target)
        if node is None:
            self.print_output(f'cd: no such file or directory: {target}\n')
            return
        if not node.is_dir:
            self.print_output(f'cd: not a directory: {target}\n')
            return
        self.cwd = node
        # print nothing (like typical shells) but update prompt
        self.print_output("")

    def cmd_history(self, args):
        if not self.history:
            self.print_output("No history\n")
            return
        for i, cmd in enumerate(self.history, start=1):
            self.print_output(f"{i}  {cmd}\n")

    def cmd_date(self, args):
        # print local datetime
        now = datetime.now()
        self.print_output(now.strftime("%Y-%m-%d %H:%M:%S") + "\n")

    def cmd_cal(self, args):
        # show calendar for current month, or for given year/month if provided: cal YYYY MM
        try:
            if len(args) == 0:
                today = datetime.today()
                year = today.year
                month = today.month
            elif len(args) == 1:
                # try parse month (1-12) in current year
                year = datetime.today().year
                month = int(args[0])
            elif len(args) == 2:
                year = int(args[0])
                month = int(args[1])
            else:
                self.print_output("cal: usage: cal [month] or cal [year month]\n")
                return
            if not (1 <= month <= 12):
                self.print_output("cal: invalid month\n")
                return
            cal_text = calendar.month(year, month)
            # print with each line
            for line in cal_text.splitlines():
                self.print_output(line + "\n")
        except Exception:
            self.print_output("cal: error parsing arguments\n")

    def cmd_help(self, args):
        self.print_output("Supported commands:\n")
        self.print_output("  ls [path]     - list directory or file\n")
        self.print_output("  cd [path]     - change directory\n")
        self.print_output("  history       - show command history\n")
        self.print_output("  date          - show current date/time\n")
        self.print_output("  cal [m] [y]   - show calendar\n")
        self.print_output("  help          - this help\n")
        self.print_output("  exit          - exit emulator\n")

# -------------------- main --------------------
if __name__ == "__main__":
    try:
        vfs_root = build_vfs_from_disk(args.vfs)
    except Exception as e:
        print(f"Failed to build VFS: {e}", file=sys.stderr)
        sys.exit(1)

    app = ShellGUI(vfs_root, args.vfs, script=args.script)
    app.mainloop()
