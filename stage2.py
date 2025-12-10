"""
VFS Shell Emulator — Stage 2
Добавлено:
- Параметры командной строки: --vfs <путь>, --script <файл>, --auto <команды>
- Выполнение стартового скрипта: команды выполняются как ввод пользователя
- Автоматическое выполнение команд через --auto
- Ошибочные строки в скрипте пропускаются, но показываются в выводе
- Отладочный вывод параметров

Запуск:
    python stage2.py --vfs=./myvfs --script=start.txt --auto="ls;cd /home"
"""

import os
import re

def expand_vars(text):
    pattern = re.compile(r'\$([A-Za-z_][A-Za-z0-9_]*)')
    def repl(match):
        var = match.group(1)
        return os.environ.get(var, f"${var}")
    return pattern.sub(repl, text)

import shlex
import sys
import argparse
import tkinter as tk
from tkinter import scrolledtext

PROMPT = "VFS> "

# ---------------- ПАРАМЕТРЫ КОМАНДНОЙ СТРОКИ ----------------
parser = argparse.ArgumentParser()
parser.add_argument("--vfs", type=str, default=None, help="Путь к директории-VFS")
parser.add_argument("--script", type=str, default=None, help="Стартовый скрипт")
parser.add_argument("--auto", type=str, default="", help="Автовыполнение команд через ;")
args = parser.parse_args()

# ---------------- GUI SHELL ----------------
class ShellGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"VFS Emulator (Stage 2)")
        self.geometry("900x500")

        # вывод
        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED)
        self.output.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ввод
        self.entry_var = tk.StringVar()
        frame = tk.Frame(self)
        frame.pack(fill=tk.X, padx=6, pady=6)
        self.label = tk.Label(frame, text=PROMPT)
        self.label.pack(side=tk.LEFT)
        self.entry = tk.Entry(frame, textvariable=self.entry_var)
        self.entry.pack(fill=tk.X, expand=True, side=tk.LEFT)
        self.entry.bind("<Return>", self.on_enter)
        self.entry.focus()

        # история
        self.history = []
        self.hist_index = None
        self.entry.bind('<Up>', self.on_up)
        self.entry.bind('<Down>', self.on_down)

        # стартовые сообщения
        self.print_output("Stage 2 emulator ready.\n")
        self.print_output(f"[debug] VFS path: {args.vfs}\n")
        self.print_output(f"[debug] Script: {args.script}\n")
        if args.auto:
            self.print_output(f"[debug] Auto commands: {args.auto}\n")
        self.print_output("\n")

        # выполнить стартовый скрипт
        if args.script:
            self.run_script(args.script)

        # выполнить автоматические команды
        if args.auto:
            self.print_output(f"\n[auto] Выполнение команд: {args.auto}\n")
            for cmd in args.auto.split(';'):
                cmd = cmd.strip()
                if cmd:
                    self.print_output(PROMPT + cmd + "\n")
                    self.execute_command(cmd)
            self.print_output("\n[auto] Все команды выполнены!\n")

    # ---------- Вывод ----
    def print_output(self, text):
        self.output.config(state=tk.NORMAL)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.config(state=tk.DISABLED)

    # ---------- История ----------
    def on_up(self, e):
        if not self.history:
            return
        if self.hist_index is None:
            self.hist_index = len(self.history) - 1
        else:
            self.hist_index = max(0, self.hist_index - 1)
        self.entry_var.set(self.history[self.hist_index])
        return 'break'

    def on_down(self, e):
        if not self.history or self.hist_index is None:
            return
        self.hist_index = min(len(self.history)-1, self.hist_index+1)
        self.entry_var.set(self.history[self.hist_index])
        return 'break'

    # ---------- Обработка ввода ----------
    def on_enter(self, event=None):
        line = self.entry_var.get()
        if line.strip() == "":
            self.print_output(PROMPT + "\n")
            self.entry_var.set("")
            return

        self.print_output(PROMPT + line + "\n")
        self.history.append(line)
        self.hist_index = None
        self.execute_command(line)
        self.entry_var.set("")

    # ---------- Выполнение скрипта ----------
    def run_script(self, filename):
        if not os.path.exists(filename):
            self.print_output(f"[error] Script not found: {filename}\n")
            return

        self.print_output(f"[script] Running {filename}\n\n")
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                cmd = line.strip()
                if not cmd:
                    continue
                self.print_output(PROMPT + cmd + "\n")
                try:
                    self.execute_command(cmd)
                except Exception as e:
                    self.print_output(f"[script error] {e}\n")

    # ---------- Парсер + диспетчер ----------
    def execute_command(self, line):
        expanded = expand_vars(line)
        try:
            tokens = shlex.split(expanded)
        except Exception as e:
            self.print_output(f"parse error: {e}\n")
            return
        if not tokens:
            return

        cmd, *args_cmd = tokens

        if cmd == "exit":
            return self.cmd_exit(args_cmd)
        elif cmd == "ls":
            return self.cmd_ls(args_cmd)
        elif cmd == "cd":
            return self.cmd_cd(args_cmd)
        else:
            self.print_output(f"Unknown command: {cmd}\n")

    # ---------- Команды ----------
    def cmd_exit(self, args):
        if args:
            self.print_output("exit: no args expected\n")
            return
        self.print_output("Exiting...\n")
        self.after(200, self.destroy)

    def cmd_ls(self, args):
        self.print_output(f"[stub] ls args={args}\n")

    def cmd_cd(self, args):
        if len(args) > 1:
            self.print_output("cd: too many args\n")
            return
        target = args[0] if args else os.path.expanduser("~")
        self.print_output(f"[stub] cd -> {target}\n")


# ---------------- ЗАПУСК ----------------
if __name__ == "__main__":
    app = ShellGUI()
    app.mainloop()