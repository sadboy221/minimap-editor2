import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess
import os
import sys
import threading
import shutil

# --- НАСТРОЙКИ ---
# Имена инструментов. Если java не в PATH, укажи полный путь.
JAVA_EXE = "java"
FFDEC_JAR = "ffdec.jar"
SWFMILL_EXE = "swfmill.exe"

class MinimapEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Minimap .gfx Редактор (FFDec + swfmill)")
        self.root.geometry("1100x700")

        self.current_gfx_path = None
        self.current_xml_path = None
        self.export_dir = None

        self.create_widgets()

    def create_widgets(self):
        # --- Верхняя панель с кнопками ---
        top_frame = tk.Frame(self.root, pady=10)
        top_frame.pack(fill=tk.X)

        self.btn_open = tk.Button(top_frame, text="1. Открыть .gfx (swfmill -> XML)", command=self.open_gfx, width=35, height=2)
        self.btn_open.pack(side=tk.LEFT, padx=10)

        self.btn_export = tk.Button(top_frame, text="2. Экспорт ресурсов (FFDec)", command=self.export_resources, width=35, height=2, state=tk.DISABLED)
        self.btn_export.pack(side=tk.LEFT, padx=10)

        self.btn_import = tk.Button(top_frame, text="3. Импорт правок в .gfx", command=self.import_resources, width=35, height=2, state=tk.DISABLED)
        self.btn_import.pack(side=tk.LEFT, padx=10)

        # --- Основная область ---
        self.text_area = scrolledtext.ScrolledText(self.root, wrap=tk.NONE, font=("Consolas", 10))
        self.text_area.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0, 10))
        
        # Настраиваем теги для подсветки, чтобы XML был читаемым
        self.text_area.tag_config("tag", foreground="#569cd6")
        self.text_area.tag_config("attr", foreground="#9cdcfe")
        self.text_area.tag_config("string", foreground="#ce9178")

        # --- Статус бар ---
        self.status_var = tk.StringVar(value="Готов. Выберите .gfx файл.")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def check_tools(self):
        """Проверяет наличие нужных файлов рядом со скриптом"""
        missing = []
        if not os.path.exists(FFDEC_JAR):
            missing.append(FFDEC_JAR)
        if not os.path.exists(SWFMILL_EXE):
            missing.append(SWFMILL_EXE)
        if missing:
            messagebox.showerror("Ошибка", f"Не найдены файлы:\n{', '.join(missing)}\n\nПоложи их в папку с программой.")
            return False
        return True

    def run_command(self, cmd):
        """Запускает команду и возвращает результат"""
        try:
            # creationflags чтобы скрыть окно консоли на Windows
            kwargs = {}
            if sys.platform == "win32":
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, **kwargs)
            return result
        except Exception as e:
            return None

    def open_gfx(self):
        if not self.check_tools(): return

        file_path = filedialog.askopenfilename(title="Выберите .gfx файл", filetypes=[("Scaleform GFx", "*.gfx"), ("Все файлы", "*.*")])
        if not file_path: return

        self.current_gfx_path = file_path
        # Создаём временный XML в той же папке
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        self.current_xml_path = os.path.join(os.path.dirname(file_path), f"{base_name}_decompiled.xml")

        self.status_var.set(f"Распаковка {base_name}.gfx через swfmill...")
        self.root.update()

        # Запускаем swfmill swf2xml
        result = self.run_command([SWFMILL_EXE, "swf2xml", file_path, self.current_xml_path])

        if result is None or result.returncode != 0:
            error_msg = result.stderr if result else "Не удалось запустить swfmill"
            messagebox.showerror("Ошибка swfmill", f"Не удалось распаковать файл:\n{error_msg}")
            self.status_var.set("Ошибка распаковки.")
            return

        # Показываем XML в текстовом поле
        try:
            with open(self.current_xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            self.text_area.delete(1.0, tk.END)
            self.text_area.insert(tk.END, xml_content)
            self.text_area.edit_modified(False)
            self.status_var.set(f"XML загружен. Можно редактировать и сохранять. Путь: {self.current_xml_path}")
            
            # Активируем кнопки
            self.btn_export.config(state=tk.NORMAL)
            self.btn_import.config(state=tk.DISABLED) # Импорт пока недоступен, пока не собран GFX
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать XML: {e}")

    def export_resources(self):
        if not self.current_gfx_path: return
        
        # Папка для экспорта будет рядом с gfx
        base_name = os.path.splitext(os.path.basename(self.current_gfx_path))[0]
        self.export_dir = os.path.join(os.path.dirname(self.current_gfx_path), f"{base_name}_export")
        
        # Очищаем старую папку, если есть
        if os.path.exists(self.export_dir):
            if not messagebox.askyesno("Папка существует", f"Папка {os.path.basename(self.export_dir)} уже существует. Очистить её?"):
                return
            shutil.rmtree(self.export_dir)
        
        os.makedirs(self.export_dir)

        self.status_var.set(f"Экспорт ресурсов в {self.export_dir}...")
        self.root.update()

        # ffdec -export <dir> <file>
        # Экспортируем всё, чтобы получить картинки и скрипты
        cmd = [JAVA_EXE, "-jar", FFDEC_JAR, "-export", self.export_dir, self.current_gfx_path]
        result = self.run_command(cmd)

        if result is None or result.returncode != 0:
            error_msg = result.stderr if result else "Не удалось запустить Java"
            messagebox.showerror("Ошибка FFDec", f"Не удалось экспортировать ресурсы:\n{error_msg}")
            self.status_var.set("Ошибка экспорта.")
            return

        self.status_var.set(f"Ресурсы экспортированы в: {self.export_dir}")
        messagebox.showinfo("Экспорт завершён", f"Ресурсы извлечены в:\n{self.export_dir}\n\nОтредактируй нужные PNG (не меняя имя и размер!), затем нажми 'Импорт правок'.")
        
        # Теперь можно импортировать
        self.btn_import.config(state=tk.NORMAL)

    def import_resources(self):
        if not self.current_gfx_path or not self.export_dir: return

        # Спрашиваем, куда сохранить новый .gfx
        base_name = os.path.splitext(os.path.basename(self.current_gfx_path))[0]
        new_gfx_path = os.path.join(os.path.dirname(self.current_gfx_path), f"{base_name}_edited.gfx")

        self.status_var.set(f"Импорт правок из {self.export_dir}...")
        self.root.update()

        # ffdec -importScript <in> <out> <sourceDir>
        # Используем importScript, так как он лучше работает с папками ресурсов
        cmd = [JAVA_EXE, "-jar", FFDEC_JAR, "-importScript", self.current_gfx_path, new_gfx_path, self.export_dir]
        result = self.run_command(cmd)

        if result is None or result.returncode != 0:
            error_msg = result.stderr if result else "Не удалось запустить Java"
            messagebox.showerror("Ошибка FFDec", f"Не удалось импортировать правки:\n{error_msg}")
            self.status_var.set("Ошибка импорта.")
            return

        self.status_var.set(f"Успех! Новый файл: {new_gfx_path}")
        messagebox.showinfo("Импорт завершён", f"Новый .gfx сохранён как:\n{new_gfx_path}")

if __name__ == "__main__":
    root = tk.Tk()
    app = MinimapEditorApp(root)
    root.mainloop()