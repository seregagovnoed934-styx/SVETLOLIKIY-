#!/usr/bin/env python3
"""
stage5.py — VFS Shell Emulator (Stage 5)

Запуск:
    python stage5.py --vfs "C:\path\to\vfs_stage5" [--script start_script.txt]

Команды:
    ls [path]
    cd [path]
    mkdir <path>
    chmod <mode> <path>
    history
    date
    cal
    help
    exit

Важное:
- Все изменения (mkdir, chmod) производятся только в памяти (в VFS-дереве).
- Источник VFS — реальная папка: файлы и папки читаются в память при старте.
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

# ---------- CLI ----------
parser = argparse.ArgumentParser(description="VFS Shell Emulator — Stage 5")
parser.add_argument("--vfs", required=True, help="Path to VFS source directory")
parser.add_argument("--script", default=None, help="Optional startup script")
args = parser.parse_args()

# ---------- Utilities ----------
_var_pattern = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def expand_vars(text: str) -> str:
    def repl(m):
        name = m.group(1)
        return os.environ.get(name, f"${name}")
    return _var_pattern.sub(repl, text)


def format_mode(mode: int) -> str:
    """Return octal string like 0755 and rwx string (simple)."""
    try:
        octal = format(mode & 0o777, "03o")
    except Exception:
        octal = "???"
    # simple rwx
    perms = []
    for who in (mode >> 6, (mode >> 3) & 0b111, mode & 0b111):
        s = ""
        s += "r" if (who & 4) else "-"
        s += "w" if (who & 2) else "-"
        s += "x" if (who & 1) else "-"
        perms.append(s)
    return f"{octal} ({''.join(perms)})"


# ---------- VFS node ----------
class VFSNode:
    def __init__(self, name: str, is_dir: bool, mode: int = None):
        self.name = name
        self.is_dir = is_dir
        self.children: Dict[str, VFSNode] = {}
        self.content: str = ""
        self.parent: Optional[VFSNode] = None
        # mode only stored in memory; default 0o755 for dirs, 0o644 for files
        if mode is None:
            self.mode = 0o755 if is_dir else 0o644
        else:
            self.mode = mode

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


# ---------- Build VFS ----------
def build_vfs_from_disk(src_path: str) -> VFSNode:
    if not os.path.isdir(src_path):
        raise FileNotFoundError(f"VFS source directory not found: {src_path}")

    root = VFSNode("/", True)

    def _walk(disk_path: str, vfs_node: VFSNode):
        try:
            for entry in sorted(os.listdir(disk_path)):
                full = os.path.join(disk_path, entry)
                if os.path.isdir(full):
                    child = VFSNode(entry, True, mode=0o755)
                    vfs_node.add_child(child)
                    _walk(full, child)
                else:
                    child = VFSNode(entry, False, mode=0o644)
                    try:
                        with open(full, "r", encoding="utf-8", errors="ignore") as f:
                            child.content = f.read()
                    except Exception:
                        child.content = ""
                    vfs_node.add_child(child)
        except PermissionError:
            pass

    _walk(src_path, root)
    return root


# ---------- Path helpers ----------
def _split_vfs_path(p: str):
    p = p.replace("\\", "/")
    if p == "" or p == "/":
        return []
    return [part for part in p.split("/") if part != ""]


def resolve_vfs_path(cwd: VFSNode, path: str) -> Optional[VFSNode]:
    if path.startswith("/"):
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


def make_vfs_dir(cwd: VFSNode, path: str, mode: int = 0o755) -> Optional[VFSNode]:
    """
    Create directory at given path (relative or absolute). Returns created node or None on error.
    If intermediate directories do not exist — return None (we keep behavior simple).
    """
    # resolve parent
    parts = _split_vfs_path(path)
    if not parts:
        # trying to mkdir '/' — nothing to do
        return None
    # parent path parts
    parent_parts = parts[:-1]
    name = parts[-1]
    # find parent node
    parent_path = "/" + "/".join(parent_parts) if path.startswith("/") and parent_parts else "/".join(parent_parts)
    parent_node = resolve_vfs_path(cwd, parent_path) if parent_parts else (cwd if not path.startswith("/") else resolve_vfs_path(cwd, "/"))
    if parent_node is None or not parent_node.is_dir:
        return None
    if name in parent_node.children:
        # already exists
        return None
    new_dir = VFSNode(name, True, mode=mode)
    parent_node.add_child(new_dir)
    return new_dir


# ---------- GUI ----------
PROMPT_TEMPLATE = "vfs:{cwd}> "


class ShellGUI(tk.Tk):
    def __init__(self, vfs_root: VFSNode, vfs_src_path: str, script: Optional[str] = None):
        super().__init__()
        self.vfs_root = vfs_root
        self.cwd = vfs_root
        self.vfs_src_path = vfs_src_path
        self.script = script

        self.history: list[str] = []

        self.title(f"VFS Stage5 — {os.path.basename(vfs_src_path)}")
        self.geometry("920x560")

        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED)
        self.output.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        frm = tk.Frame(self)
        frm.pack(fill=tk.X, padx=6, pady=(0, 6))
        self.prompt_label = tk.Label(frm, text=self.prompt_text(), anchor="w")
        self.prompt_label.pack(side=tk.LEFT)
        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(frm, textvariable=self.entry_var)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", self.on_enter)
        self.entry.focus()

        self.entry.bind("<Up>", self.on_history_up)
        self.entry.bind("<Down>", self.on_history_down)
        self.hist_index: Optional[int] = None

        # motd
        if "motd" in self.vfs_root.children and not self.vfs_root.children["motd"].is_dir:
            self.print_output(self.vfs_root.children["motd"].content + "\n")

        self.print_output(f"[debug] VFS loaded from: {vfs_src_path}\n")
        self.print_output(f"[debug] entries: {list(self.vfs_root.children.keys())}\n\n")

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

    # history nav
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

    # input
    def on_enter(self, event=None):
        line = self.entry_var.get()
        if not line.strip():
            self.print_output(self.prompt_text() + "\n")
            self.entry_var.set("")
            return
        self.print_output(self.prompt_text() + line + "\n")
        self.history.append(line)
        self.hist_index = None
        try:
            self.execute_line(line)
        except Exception as e:
            self.print_output(f"[error] Exception: {e}\n")
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
                    self.history.append(cmd_line)
                    try:
                        self.execute_line(cmd_line)
                    except Exception as e:
                        self.print_output(f"[script error] {e}\n")
        except Exception as e:
            self.print_output(f"[script error] Failed to read script: {e}\n")

    # execution
    def execute_line(self, line: str):
        expanded = expand_vars(line)
        try:
            tokens = shlex.split(expanded)
        except Exception as e:
            self.print_output(f"parse error: {e}\n")
            return
        if not tokens:
            return
        cmd, *args = tokens
        if cmd == "exit":
            return self.cmd_exit(args)
        elif cmd == "ls":
            return self.cmd_ls(args)
        elif cmd == "cd":
            return self.cmd_cd(args)
        elif cmd == "mkdir":
            return self.cmd_mkdir(args)
        elif cmd == "chmod":
            return self.cmd_chmod(args)
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

    # commands
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
            self.print_output(node.name + "\n")
            return
        # list with mode for clarity
        for name in sorted(node.children.keys()):
            child = node.children[name]
            suffix = "/" if child.is_dir else ""
            self.print_output(f"{name}{suffix}\t{format_mode(child.mode)}\n")

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
        self.print_output("")

    def cmd_mkdir(self, args):
        if len(args) != 1:
            self.print_output("mkdir: usage: mkdir <path>\n")
            return
        path = args[0]
        # try create; do not create intermediate dirs
        created = make_vfs_dir(self.cwd, path, mode=0o755)
        if created is None:
            self.print_output(f"mkdir: cannot create '{path}': parent missing or already exists\n")
            return
        self.print_output(f"mkdir: created '{created.path_from_root()}'\n")

    def cmd_chmod(self, args):
        if len(args) != 2:
            self.print_output("chmod: usage: chmod <mode> <path>\n")
            return
        mode_str, path = args
        # parse mode (support octal like 755 or 0755)
        try:
            if mode_str.startswith("0"):
                mode = int(mode_str, 8)
            else:
                # allow 3-digit like 755 -> octal
                if all(c in "01234567" for c in mode_str):
                    mode = int(mode_str, 8)
                else:
                    mode = int(mode_str, 10)
        except Exception:
            self.print_output("chmod: invalid mode\n")
            return
        node = resolve_vfs_path(self.cwd, path)
        if node is None:
            self.print_output(f"chmod: no such file or directory: {path}\n")
            return
        node.mode = mode
        self.print_output(f"chmod: changed mode of '{node.path_from_root()}' to {format_mode(node.mode)}\n")

    def cmd_history(self, args):
        if not self.history:
            self.print_output("No history\n")
            return
        for i, cmd in enumerate(self.history, start=1):
            self.print_output(f"{i}  {cmd}\n")

    def cmd_date(self, args):
        now = datetime.now()
        self.print_output(now.strftime("%Y-%m-%d %H:%M:%S") + "\n")

    def cmd_cal(self, args):
        try:
            if len(args) == 0:
                today = datetime.today()
                year = today.year
                month = today.month
            elif len(args) == 1:
                year = datetime.today().year
                month = int(args[0])
            else:
                year = int(args[0])
                month = int(args[1])
            if not (1 <= month <= 12):
                self.print_output("cal: invalid month\n")
                return
            cal_text = calendar.month(year, month)
            for line in cal_text.splitlines():
                self.print_output(line + "\n")
        except Exception:
            self.print_output("cal: error parsing arguments\n")

    def cmd_help(self, args):
        self.print_output("Supported commands:\n")
        self.print_output("  ls [path]         - list directory or file (shows mode)\n")
        self.print_output("  cd [path]         - change directory\n")
        self.print_output("  mkdir <path>      - create directory in VFS (in-memory)\n")
        self.print_output("  chmod <mode> <p>  - change mode in VFS (e.g. 755)\n")
        self.print_output("  history           - show session history\n")
        self.print_output("  date              - show current date/time\n")
        self.print_output("  cal [m] [y]       - show calendar\n")
        self.print_output("  help              - this help\n")
        self.print_output("  exit              - exit emulator\n")


# ---------- main ----------
if __name__ == "__main__":
    try:
        vfs_root = build_vfs_from_disk(args.vfs)
    except Exception as e:
        print(f"Failed to build VFS: {e}", file=sys.stderr)
        sys.exit(1)

    app = ShellGUI(vfs_root, args.vfs, script=args.script)
    app.mainloop()
