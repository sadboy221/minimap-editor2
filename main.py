import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess
import os
import sys
import shutil

# --- ПУТИ ---
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JAVA_EXE = "java"  # или полный путь к java.exe
FFDEC_JAR = os.path.join(BASE_DIR, "ffdec_lib.jar")
SWFMILL_EXE = os.path.join(BASE_DIR, "swfmill.exe")


class MinimapEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Minimap .gfx Редактор (FFDec + swfmill)")
        self.root.geometry("1100x700")

        self.current_gfx_path = None
        self.current_swf_path = None
        self.current_xml_path = None
        self.export_dir = None

        self.create_widgets()

    def create_widgets(self):
        top_frame = tk.Frame(self.root, pady=10)
        top_frame.pack(fill=tk.X)

        tk.Button(top_frame, text="1. Открыть .gfx",
                  command=self.open_gfx, width=28, height=2).pack(side=tk.LEFT, padx=6)
        tk.Button(top_frame, text="2. Сохранить XML",
                  command=self.save_xml, width=28, height=2, state=tk.DISABLED).pack(side=tk.LEFT, padx=6)
        self.btn_rebuild = tk.Button(top_frame, text="3. Собрать .gfx обратно",
                                     command=self.rebuild_gfx, width=28, height=2, state=tk.DISABLED)
        self.btn_rebuild.pack(side=tk.LEFT, padx=6)
        self.btn_export = tk.Button(top_frame, text="Экспорт ресурсов (FFDec)",
                                    command=self.export_resources, width=28, height=2, state=tk.DISABLED)
        self.btn_export.pack(side=tk.LEFT, padx=6)

        self.text_area = scrolledtext.ScrolledText(self.root, wrap=tk.NONE, font=("Consolas", 10))
        self.text_area.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0, 10))

        self.status_var = tk.StringVar(value="Готов. Выберите .gfx файл.")
        tk.Label(self.root, textvariable=self.status_var,
                 bd=1, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

    def check_tools(self):
        missing = []
        if not os.path.exists(FFDEC_JAR):
            missing.append("ffdec_lib.jar")
        if not os.path.exists(SWFMILL_EXE):
            missing.append("swfmill.exe")
        if missing:
            messagebox.showerror("Ошибка",
                                 f"Не найдены файлы:\n{', '.join(missing)}\n\n"
                                 f"Проверь папку: {BASE_DIR}")
            return False
        return True

    def run_command(self, cmd, timeout=180):
        try:
            kwargs = {}
            if sys.platform == "win32":
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kwargs)
        except Exception as e:
            print(f"[cmd error] {e}")
            return None

    # ШАГ 1: .gfx → .swf (через FFDec) → .xml (через swfmill)
    def open_gfx(self):
        if not self.check_tools():
            return

        file_path = filedialog.askopenfilename(
            title="Выберите .gfx файл",
            filetypes=[("Scaleform GFx", "*.gfx"), ("Все файлы", "*.*")]
        )
        if not file_path:
            return

        self.current_gfx_path = file_path
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        work_dir = os.path.dirname(file_path)

        self.current_swf_path = os.path.join(work_dir, f"{base_name}_converted.swf")
        self.current_xml_path = os.path.join(work_dir, f"{base_name}_decompiled.xml")

        # 1.1: .gfx → .swf через FFDec
        self.status_var.set("Шаг 1/3: FFDec конвертирует .gfx в .swf...")
        self.root.update()

        cmd1 = [JAVA_EXE, "-jar", FFDEC_JAR,
                "-convertSWF", file_path, self.current_swf_path]
        r1 = self.run_command(cmd1)

        if r1 is None or r1.returncode != 0 or not os.path.exists(self.current_swf_path):
            err = r1.stderr if r1 else "Не удалось запустить Java"
            messagebox.showerror("Ошибка FFDec",
                                 f"Не удалось конвертировать .gfx в .swf:\n{err}")
            self.status_var.set("Ошибка конвертации.")
            return

        # 1.2: .swf → .xml через swfmill
        self.status_var.set("Шаг 2/3: swfmill распаковывает .swf в .xml...")
        self.root.update()

        cmd2 = [SWFMILL_EXE, "swf2xml", self.current_swf_path, self.current_xml_path]
        r2 = self.run_command(cmd2)

        if r2 is None or r2.returncode != 0:
            err = r2.stderr if r2 else "Не удалось запустить swfmill"
            messagebox.showerror("Ошибка swfmill",
                                 f"Не удалось распаковать .swf в XML:\n{err}")
            self.status_var.set("Ошибка распаковки.")
            return

        try:
            with open(self.current_xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            self.text_area.delete(1.0, tk.END)
            self.text_area.insert(tk.END, xml_content)
            self.status_var.set(f"XML загружен. Правь цвета, потом нажми 'Собрать .gfx обратно'.")
            self.btn_rebuild.config(state=tk.NORMAL)
            self.btn_export.config(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать XML: {e}")

    # Сохранение XML на диск (чтобы swfmill его увидел)
    def save_xml(self):
        if not self.current_xml_path:
            return
        try:
            with open(self.current_xml_path, 'w', encoding='utf-8') as f:
                f.write(self.text_area.get(1.0, tk.END))
            messagebox.showinfo("Сохранено", f"XML записан: {self.current_xml_path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить XML: {e}")

    # ШАГ 3: .xml → .swf (swfmill) → .gfx (FFDec)
    def rebuild_gfx(self):
        if not self.current_xml_path or not self.current_swf_path:
            return

        # Сначала сохраняем XML из текстового поля
        try:
            with open(self.current_xml_path, 'w', encoding='utf-8') as f:
                f.write(self.text_area.get(1.0, tk.END))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить XML: {e}")
            return

        base_name = os.path.splitext(os.path.basename(self.current_gfx_path))[0]
        new_swf = os.path.join(os.path.dirname(self.current_gfx_path),
                               f"{base_name}_edited.swf")
        new_gfx = os.path.join(os.path.dirname(self.current_gfx_path),
                               f"{base_name}_edited.gfx")

        # 3.1: XML → SWF через swfmill
        self.status_var.set("Шаг 1/2: swfmill пакует XML в .swf...")
        self.root.update()

        cmd1 = [SWFMILL_EXE, "xml2swf", self.current_xml_path, new_swf]
        r1 = self.run_command(cmd1)

        if r1 is None or r1.returncode != 0:
            err = r1.stderr if r1 else "Не удалось запустить swfmill"
            messagebox.showerror("Ошибка swfmill",
                                 f"Не удалось собрать .swf из XML:\n{err}")
            self.status_var.set("Ошибка сборки.")
            return

        # 3.2: SWF → GFX через FFDec
        self.status_var.set("Шаг 2/2: FFDec конвертирует .swf в .gfx...")
        self.root.update()

        cmd2 = [JAVA_EXE, "-jar", FFDEC_JAR,
                "-convertGFX", new_swf, new_gfx]
        r2 = self.run_command(cmd2)

        if r2 is None or r2.returncode != 0 or not os.path.exists(new_gfx):
            err = r2.stderr if r2 else "Не удалось запустить Java"
            messagebox.showerror("Ошибка FFDec",
                                 f"Не удалось собрать .gfx из .swf:\n{err}")
            self.status_var.set("Ошибка сборки.")
            return

        self.status_var.set(f"Готово! Новый файл: {new_gfx}")
        messagebox.showinfo("Готово",
                            f"Новый .gfx сохранён как:\n{new_gfx}")

    # Экспорт всех картинок из .gfx через FFDec
    def export_resources(self):
        if not self.current_gfx_path:
            return

        base_name = os.path.splitext(os.path.basename(self.current_gfx_path))[0]
        self.export_dir = os.path.join(os.path.dirname(self.current_gfx_path),
                                       f"{base_name}_export")

        if os.path.exists(self.export_dir):
            if not messagebox.askyesno("Папка существует",
                                       f"Папка уже существует. Очистить её?"):
                return
            shutil.rmtree(self.export_dir)
        os.makedirs(self.export_dir)

        self.status_var.set("Экспорт ресурсов через FFDec...")
        self.root.update()

        cmd = [JAVA_EXE, "-jar", FFDEC_JAR, "-export", self.export_dir,
               self.current_gfx_path]
        r = self.run_command(cmd)

        if r is None or r.returncode != 0:
            err = r.stderr if r else "Не удалось запустить Java"
            messagebox.showerror("Ошибка FFDec",
                                 f"Не удалось экспортировать ресурсы:\n{err}")
            return

        messagebox.showinfo("Экспорт завершён",
                            f"Ресурсы извлечены в:\n{self.export_dir}")


if __name__ == "__main__":
    root = tk.Tk()
    app = MinimapEditorApp(root)
    root.mainloop()
