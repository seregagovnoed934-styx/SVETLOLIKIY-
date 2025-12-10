#!/usr/bin/env python3
"""
VFS Shell Emulator - Stage 4
Минимальный но работающий вариант по ТЗ
"""
import os
import sys
import tkinter as tk
from tkinter import scrolledtext, messagebox
from datetime import datetime
import calendar
import argparse

# ==================== Парсинг аргументов ====================
parser = argparse.ArgumentParser(description="VFS Shell - Stage 4")
parser.add_argument("--vfs", required=True, help="Путь к VFS директории")
parser.add_argument("--script", help="Стартовый скрипт для тестирования")
args = parser.parse_args()

# Проверка VFS директории
if not os.path.exists(args.vfs):
    print(f"ОШИБКА: Директория {args.vfs} не существует!")
    print("Создайте её и добавьте тестовые файлы.")
    sys.exit(1)

# ==================== Глобальные переменные ====================
current_path = args.vfs  # Текущая реальная директория
history = []  # История команд
vfs_root = args.vfs  # Корень VFS

# ==================== Функции для работы с файлами ====================
def get_files(path):
    """Получить список файлов в директории"""
    try:
        items = os.listdir(path)
        result = []
        for item in sorted(items):
            full_path = os.path.join(path, item)
            if os.path.isdir(full_path):
                result.append(item + "/")
            else:
                result.append(item)
        return result
    except Exception as e:
        return [f"Ошибка: {str(e)}"]

def change_dir(target):
    """Сменить директорию"""
    global current_path
    
    if not target or target == "/":
        current_path = vfs_root
        return True, "Перешел в корень"
    
    if target == "..":
        if current_path != vfs_root:
            current_path = os.path.dirname(current_path)
            if current_path == vfs_root or not current_path.startswith(vfs_root):
                current_path = vfs_root
        return True, "Перешел в родительскую директорию"
    
    new_path = os.path.join(current_path, target)
    if os.path.exists(new_path) and os.path.isdir(new_path):
        current_path = new_path
        return True, f"Перешел в {target}"
    else:
        return False, f"Директория {target} не существует"

# ==================== GUI ====================
class ShellApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VFS Shell Emulator - Stage 4")
        self.root.geometry("800x600")
        
        # Выходная область
        self.output = scrolledtext.ScrolledText(
            self.root, 
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="black",
            fg="white"
        )
        self.output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Входная область
        input_frame = tk.Frame(self.root)
        input_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        self.prompt = tk.Label(
            input_frame, 
            text=self.get_prompt(),
            font=("Consolas", 10, "bold"),
            fg="green",
            width=20,
            anchor="w"
        )
        self.prompt.pack(side=tk.LEFT)
        
        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(
            input_frame,
            textvariable=self.entry_var,
            font=("Consolas", 10),
            bg="#222",
            fg="white",
            insertbackground="white"
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", self.on_enter)
        self.entry.focus()
        
        # Запуск
        self.startup()
    
    def get_prompt(self):
        """Получить текст промпта"""
        rel_path = os.path.relpath(current_path, vfs_root)
        if rel_path == ".":
            return "vfs:/> "
        return f"vfs:/{rel_path}> "
    
    def print(self, text, color="white"):
        """Вывод текста"""
        colors = {
            "white": "#FFFFFF",
            "green": "#00FF00",
            "red": "#FF0000",
            "yellow": "#FFFF00",
            "blue": "#00FFFF",
            "gray": "#888888"
        }
        
        self.output.config(state=tk.NORMAL)
        self.output.insert(tk.END, text, color)
        self.output.tag_config(color, foreground=colors.get(color, "#FFFFFF"))
        self.output.see(tk.END)
        self.output.config(state=tk.DISABLED)
        self.prompt.config(text=self.get_prompt())
    
    def startup(self):
        """Начальная инициализация"""
        self.print("="*60 + "\n", "blue")
        self.print("VFS Shell Emulator - Stage 4\n", "green")
        self.print("="*60 + "\n\n", "blue")
        
        # Вывод motd если есть
        motd_path = os.path.join(vfs_root, "motd")
        if os.path.exists(motd_path):
            try:
                with open(motd_path, "r", encoding="utf-8") as f:
                    self.print(f.read() + "\n\n", "yellow")
            except:
                pass
        
        self.print(f"VFS загружена из: {vfs_root}\n", "gray")
        self.print(f"Текущая директория: {current_path}\n\n", "gray")
        self.print("Введите 'help' для списка команд\n\n", "green")
        
        # Запуск скрипта если указан
        if args.script and os.path.exists(args.script):
            self.run_script(args.script)
    
    def run_script(self, script_path):
        """Запуск скрипта"""
        self.print(f"[ЗАПУСК СКРИПТА: {script_path}]\n\n", "blue")
        
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                for line in f:
                    cmd = line.strip()
                    if not cmd or cmd.startswith("#"):
                        continue
                    
                    # Эмуляция ввода команды
                    self.print(self.get_prompt() + cmd + "\n", "white")
                    self.execute_command(cmd)
        except Exception as e:
            self.print(f"Ошибка при выполнении скрипта: {e}\n", "red")
    
    def on_enter(self, event):
        """Обработка нажатия Enter"""
        cmd = self.entry_var.get().strip()
        if not cmd:
            return
        
        # Выводим команду
        self.print(self.get_prompt() + cmd + "\n", "white")
        
        # Сохраняем в историю
        history.append(cmd)
        
        # Выполняем
        self.execute_command(cmd)
        
        # Очищаем поле ввода
        self.entry_var.set("")
    
    def execute_command(self, cmd_line):
        """Выполнение команды"""
        parts = cmd_line.strip().split()
        if not parts:
            return
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        try:
            if cmd == "ls":
                self.cmd_ls(args)
            elif cmd == "cd":
                self.cmd_cd(args)
            elif cmd == "history":
                self.cmd_history(args)
            elif cmd == "date":
                self.cmd_date(args)
            elif cmd == "cal":
                self.cmd_cal(args)
            elif cmd == "help":
                self.cmd_help(args)
            elif cmd == "exit":
                self.root.quit()
            else:
                self.print(f"Неизвестная команда: {cmd}\n", "red")
        except Exception as e:
            self.print(f"Ошибка выполнения: {e}\n", "red")
    
    # ==================== КОМАНДЫ ====================
    def cmd_ls(self, args):
        """Команда ls"""
        target_path = current_path
        if args:
            target = args[0]
            if target.startswith("/"):
                target_path = os.path.join(vfs_root, target.lstrip("/"))
            else:
                target_path = os.path.join(current_path, target)
        
        if not os.path.exists(target_path):
            self.print(f"ls: нет такого файла или директории: {args[0] if args else ''}\n", "red")
            return
        
        if os.path.isfile(target_path):
            self.print(os.path.basename(target_path) + "\n", "white")
            return
        
        files = get_files(target_path)
        if not files:
            self.print("(пусто)\n", "gray")
        else:
            for f in files:
                if f.endswith("/"):
                    self.print(f + "\n", "blue")
                else:
                    self.print(f + "\n", "white")
    
    def cmd_cd(self, args):
        """Команда cd"""
        if len(args) > 1:
            self.print("cd: слишком много аргументов\n", "red")
            return
        
        target = args[0] if args else "/"
        success, msg = change_dir(target)
        
        if not success:
            self.print(f"cd: {msg}\n", "red")
    
    def cmd_history(self, args):
        """Команда history"""
        if args:
            self.print("history: неожиданные аргументы\n", "red")
            return
        
        if not history:
            self.print("История пуста\n", "gray")
            return
        
        for i, cmd in enumerate(history, 1):
            self.print(f"{i:3d}  {cmd}\n", "yellow")
    
    def cmd_date(self, args):
        """Команда date"""
        if args:
            self.print("date: неожиданные аргументы\n", "red")
            return
        
        now = datetime.now()
        self.print(now.strftime("%A, %d %B %Y %H:%M:%S\n"), "green")
    
    def cmd_cal(self, args):
        """Команда cal"""
        today = datetime.today()
        year = today.year
        month = today.month
        
        try:
            if len(args) == 1:
                # cal [month] или cal [year]
                try:
                    month = int(args[0])
                    if not 1 <= month <= 12:
                        raise ValueError
                except ValueError:
                    year = int(args[0])
                    month = None
            elif len(args) == 2:
                # cal [year] [month]
                year = int(args[0])
                month = int(args[1])
            elif len(args) > 2:
                self.print("cal: слишком много аргументов\n", "red")
                return
            
            if month is None:
                # Весь год
                self.print(calendar.calendar(year) + "\n", "white")
            else:
                if not 1 <= month <= 12:
                    self.print("cal: месяц должен быть от 1 до 12\n", "red")
                    return
                self.print(calendar.month(year, month) + "\n", "white")
                
        except ValueError:
            self.print("cal: неверные аргументы\n", "red")
            self.print("Использование: cal [год] [месяц] или cal [месяц]\n", "yellow")
    
    def cmd_help(self, args):
        """Команда help"""
        help_text = """
Доступные команды:
  ls [путь]      - список файлов и директорий
  cd [путь]      - смена директории (поддерживает /, ..)
  history        - история выполненных команд
  date           - текущая дата и время
  cal [год мес]  - календарь (текущий месяц по умолчанию)
  help           - эта справка
  exit           - выход из программы

Примеры:
  ls /etc
  cd home/user
  cd ..
  cal 2024 12
  cal 2024
"""
        self.print(help_text, "green")
    
    def run(self):
        """Запуск приложения"""
        self.root.mainloop()

# ==================== Создание тестового скрипта ====================
def create_test_script():
    """Создать тестовый скрипт если не существует"""
    script_content = """# Тестовый скрипт для VFS Shell - Stage 4
# Проверка всех команд

echo "=== Тест команды ls ==="
ls
ls /

echo "=== Тест команды cd ==="
cd etc
ls
cd ..
ls

echo "=== Тест команды history ==="
history

echo "=== Тест команды date ==="
date

echo "=== Тест команды cal ==="
cal
cal 12
cal 2024 12

echo "=== Тест обработки ошибок ==="
ls несуществующий_файл
cd несуществующая_директория
date лишний_аргумент
cal неправильные аргументы

echo "=== Возврат в корень и выход ==="git add .
cd /
ls
"""
    
    script_path = "test_script.txt"
    if not os.path.exists(script_path):
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        print(f"Создан тестовый скрипт: {script_path}")
    
    return script_path

# ==================== Запуск ====================
if __name__ == "__main__":
    # Создаем тестовый скрипт если нужно
    if not args.script:
        test_script = create_test_script()
        args.script = test_script
    
    # Запускаем приложение
    app = ShellApp()
    app.run()