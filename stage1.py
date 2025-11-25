"""
VFS Shell Emulator — Stage 1 (REPL)

How to run:
    python vfs_shell_emulator_stage1.py

What this prototype provides (requirements for Stage 1):
1. GUI application using Tkinter.
2. Window title contains the VFS name (set by VFS_NAME variable or command-line).
3. Parser expands environment variables (supports $HOME and other env vars).
4. Reports execution errors (unknown command, bad args) into the console area.
5. Commands-stubs: ls, cd — they print their name and received arguments.
6. Command exit terminates the emulator.
7. REPL interaction is supported; example commands shown below.
8. Commit suggestion given at the end of the file.

Notes:
- This is a minimal prototype. Most filesystem operations are not performed — ls and cd are stubs that only print their invocation.
- The parser uses shlex.split for shell-like tokenizing and os.path.expandvars for environment variable expansion.

"""

import os
import shlex
import sys
import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime

# ---------- Configuration ----------
# Default VFS name (appears in window title). Can be overridden by command-line argument.
VFS_NAME = "MyVFS" if len(sys.argv) < 2 else os.path.basename(sys.argv[1])

PROMPT = f"{VFS_NAME}> "

# ---------- Frontend (GUI) ----------
class ShellGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"VFS: {VFS_NAME}")
        self.geometry("800x500")

        # Output area
        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED)
        self.output.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Input area
        self.entry_var = tk.StringVar()
        entry_frame = tk.Frame(self)
        entry_frame.pack(fill=tk.X, padx=6, pady=(0,6))
        self.prompt_label = tk.Label(entry_frame, text=PROMPT)
        self.prompt_label.pack(side=tk.LEFT)
        self.entry = tk.Entry(entry_frame, textvariable=self.entry_var)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind('<Return>', self.on_enter)
        self.entry.focus()

        # History
        self.history = []
        self.hist_index = None
        self.entry.bind('<Up>', self.on_history_up)
        self.entry.bind('<Down>', self.on_history_down)

        # Initial message
        self.print_output(f"{VFS_NAME} shell emulator (stage 1) — ready.\nType 'exit' to quit.\n")

    def print_output(self, text):
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    def on_enter(self, event=None):
        line = self.entry_var.get()
        if not line.strip():
            # empty line — just show prompt again
            self.print_output(PROMPT + "\n")
            self.entry_var.set("")
            return

        # echo the input line as in a terminal
        self.print_output(PROMPT + line + "\n")

        # add to history
        self.history.append(line)
        self.hist_index = None

        # process command
        try:
            self.process_line(line)
        except Exception as e:
            self.print_output(f"Error: {e}\n")

        self.entry_var.set("")

    def on_history_up(self, event=None):
        if not self.history:
            return
        if self.hist_index is None:
            self.hist_index = len(self.history) - 1
        else:
            self.hist_index = max(0, self.hist_index - 1)
        self.entry_var.set(self.history[self.hist_index])
        return 'break'

    def on_history_down(self, event=None):
        if not self.history or self.hist_index is None:
            return
        self.hist_index = min(len(self.history) - 1, self.hist_index + 1)
        self.entry_var.set(self.history[self.hist_index])
        return 'break'

    # ---------- Command processing ----------
    def process_line(self, line: str):
        # Expand environment variables (supports $VAR and ${VAR})
        expanded = os.path.expandvars(line)

        # Tokenize using shell-like rules
        try:
            tokens = shlex.split(expanded)
        except ValueError as e:
            self.print_output(f"Parse error: {e}\n")
            return

        if not tokens:
            return

        cmd = tokens[0]
        args = tokens[1:]

        # Dispatch
        if cmd == 'exit':
            self.cmd_exit(args)
        elif cmd == 'ls':
            self.cmd_ls(args)
        elif cmd == 'cd':
            self.cmd_cd(args)
        else:
            self.print_output(f"Unknown command: {cmd}\n")

    # ---------- Commands (stubs) ----------
    def cmd_exit(self, args):
        if args:
            self.print_output("exit: this command takes no arguments\n")
            return
        self.print_output("Exiting...\n")
        self.after(200, self.destroy)

    def cmd_ls(self, args):
        # Stub: just print command name and args
        self.print_output(f"[stub] ls called with args: {args}\n")

    def cmd_cd(self, args):
        # Stub: attempt to expand ~ and env vars to show behavior
        if len(args) > 1:
            self.print_output("cd: too many arguments\n")
            return
        target = args[0] if args else os.path.expanduser('~')
        expanded_target = os.path.expanduser(os.path.expandvars(target))
        # We do not change any real/current working directory — this is a stub.
        self.print_output(f"[stub] cd -> {expanded_target}\n")


# ---------- Run application ----------
if __name__ == '__main__':
    app = ShellGUI()
    app.mainloop()

# ---------- Example commands to try (interactive demo) ----------
# In the GUI input, try the following lines to demonstrate implemented behavior:
#   ls -la /tmp
#   cd $HOME
#   cd ~/projects
#   unknowncmd
#   exit
# Also try quoting and variable expansion:
#   echo "$HOME"
#   ls "some file with spaces"

# ---------- Commit suggestion ----------
# After verifying the prototype, save changes and commit to your git repository with:
#   git add vfs_shell_emulator_stage1.py
#   git commit -m "stage1: GUI REPL prototype — env var expansion, ls/cd stubs, exit, error reporting"
