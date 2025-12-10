"""
Stage 3 - VFS эмулятор
Требования:
1. Все операции в памяти (не модифицируем реальные файлы)
2. Источник VFS - директория на диске (--vfs)
3. Вывод notd при старте если существует
4. Команды: ls, cd, pwd, cat, exit
"""

import os
import argparse
import shlex
import tkinter as tk
from tkinter import scrolledtext

# ----------------- ПАРАМЕТРЫ -----------------
parser = argparse.ArgumentParser()
parser.add_argument("--vfs", required=True, help="Путь к директории-VFS")
parser.add_argument("--script", default=None, help="Стартовый скрипт")
args = parser.parse_args()

# ----------------- VFS В ПАМЯТИ -----------------
class VFS:
    def __init__(self, real_path):
        self.root = {"type": "dir", "children": {}}
        self.current_path = "/"
        self.real_path = real_path
        self.load_vfs(real_path)
    
    def load_vfs(self, real_path):
        """Загружаем структуру файлов в память"""
        if not os.path.exists(real_path):
            return
        
        for root, dirs, files in os.walk(real_path):
            vfs_path = "/" + os.path.relpath(root, real_path).replace("\\", "/")
            if vfs_path == "/.":
                vfs_path = "/"
            
            # Создаем путь в VFS
            parts = [p for p in vfs_path.split("/") if p]
            node = self.root
            for part in parts:
                if part not in node["children"]:
                    node["children"][part] = {"type": "dir", "children": {}}
                node = node["children"][part]
            
            # Добавляем файлы
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except:
                    content = ""
                
                node["children"][file] = {
                    "type": "file",
                    "content": content,
                    "children": {}
                }
    
    def resolve_path(self, path):
        """Преобразует путь VFS в узел"""
        if path.startswith("/"):
            parts = [p for p in path.split("/") if p]
            node = self.root
        else:
            parts = [p for p in path.split("/") if p]
            current_parts = [p for p in self.current_path.split("/") if p]
            parts = current_parts + parts
        
        node = self.root
        for part in parts:
            if part == "..":
                # Упрощенная реализация .. (возврат к родителю)
                pass  # Пропускаем для простоты
            elif part in node["children"]:
                node = node["children"][part]
            else:
                return None
        return node
    
    def list_files(self, path=None):
        """Список файлов в текущей или указанной директории"""
        node = self.resolve_path(path) if path else self.resolve_path(self.current_path)
        if not node or node["type"] != "dir":
            return []
        return sorted(node["children"].keys())
    
    def read_file(self, path):
        """Чтение файла"""
        node = self.resolve_path(path)
        if not node or node["type"] != "file":
            return None
        return node.get("content", "")
    
    def change_dir(self, path):
        """Смена директории"""
        if path == "/":
            self.current_path = "/"
            return True
        
        node = self.resolve_path(path)
        if not node or node["type"] != "dir":
            return False
        
        # Обновляем текущий путь
        if path.startswith("/"):
            self.current_path = path
        else:
            self.current_path = os.path.normpath(os.path.join(self.current_path, path)).replace("\\", "/")
        return True

# ----------------- GUI -----------------
class ShellGUI(tk.Tk):
    def __init__(self, vfs):
        super().__init__()
        self.vfs = vfs
        self.title(f"VFS Emulator - Stage 3")
        self.geometry("900x500")
        
        # Вывод
        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, state=tk.DISABLED)
        self.output.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        
        # Ввод
        self.entry_var = tk.StringVar()
        frame = tk.Frame(self)
        frame.pack(fill=tk.X, padx=6, pady=6)
        tk.Label(frame, text=f"VFS:{vfs.current_path}> ").pack(side=tk.LEFT)
        self.entry = tk.Entry(frame, textvariable=self.entry_var)
        self.entry.pack(fill=tk.X, expand=True, side=tk.LEFT)
        self.entry.bind("<Return>", self.on_enter)
        self.entry.focus()
        
        # Заголовок
        self.print_output("Stage 3 VFS Emulator\n")
        self.print_output(f"[debug] VFS loaded from: {args.vfs}\n")
        
        # Показываем notd если есть
        notd_content = self.vfs.read_file("/notd")
        if notd_content:
            self.print_output(f"[notd] {notd_content}\n")
        
        # Выполняем стартовый скрипт
        if args.script and os.path.exists(args.script):
            self.run_script(args.script)
    
    def print_output(self, text):
        self.output.config(state=tk.NORMAL)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.config(state=tk.DISABLED)
    
    def on_enter(self, event=None):
        cmd = self.entry_var.get().strip()
        if not cmd:
            return
        
        self.print_output(f"VFS:{self.vfs.current_path}> {cmd}\n")
        self.execute_command(cmd)
        self.entry_var.set("")
    
    def run_script(self, filename):
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                cmd = line.strip()
                if cmd:
                    self.print_output(f"VFS:{self.vfs.current_path}> {cmd}\n")
                    self.execute_command(cmd)
    
    def execute_command(self, line):
        try:
            tokens = shlex.split(line)
        except:
            self.print_output(f"Ошибка разбора команды\n")
            return
        
        if not tokens:
            return
        
        cmd = tokens[0]
        
        if cmd == "exit":
            self.print_output("Выход...\n")
            self.after(200, self.destroy)
        
        elif cmd == "ls":
            files = self.vfs.list_files()
            for f in files:
                self.print_output(f"{f}\n")
        
        elif cmd == "cd":
            if len(tokens) < 2:
                self.print_output("Использование: cd <путь>\n")
            else:
                if self.vfs.change_dir(tokens[1]):
                    self.print_output(f"Текущий путь: {self.vfs.current_path}\n")
                else:
                    self.print_output(f"Ошибка: директория не найдена\n")
        
        elif cmd == "pwd":
            self.print_output(f"{self.vfs.current_path}\n")
        
        elif cmd == "cat":
            if len(tokens) < 2:
                self.print_output("Использование: cat <файл>\n")
            else:
                content = self.vfs.read_file(tokens[1])
                if content is not None:
                    self.print_output(f"{content}\n")
                else:
                    self.print_output(f"Ошибка: файл не найден\n")
        
        else:
            self.print_output(f"Неизвестная команда: {cmd}\n")

# ----------------- ЗАПУСК -----------------
if __name__ == "__main__":
    vfs = VFS(args.vfs)
    app = ShellGUI(vfs)
    app.mainloop()