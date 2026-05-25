import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os
import sys
import subprocess
import platform
import threading
import signal
import time
import glob

try:
    from PIL import Image
    import pystray
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__)), "config.json")

TELEGRAM_NAMES = {"telegram", "telegram-desktop", "telegram desktop"}
DISCORD_NAMES  = {"discord", "discordcanary", "discordptb", "discord canary", "discord ptb"}

def get_de():
    if platform.system() == "Windows":
        return "windows"
    de = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "gnome" in de:
        return "gnome"
    return "other"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"telegram": "", "discord": ""}

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось сохранить конфиг:\n{e}")

def detect_running_path(name_set):
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.run(
                ["wmic", "process", "get", "Name,ExecutablePath", "/FORMAT:CSV"],
                capture_output=True, text=True
            )
            for line in result.stdout.strip().splitlines():
                parts = line.split(",")
                if len(parts) < 3:
                    continue
                exe_path = parts[1].strip()
                name = parts[2].strip()
                base = os.path.splitext(name)[0].lower()
                if base in name_set and exe_path and os.path.isfile(exe_path):
                    return exe_path
        else:
            for exe_link in glob.glob("/proc/*/exe"):
                try:
                    exe_path = os.readlink(exe_link)
                    base = os.path.splitext(os.path.basename(exe_path))[0].lower()
                    if base in name_set and os.path.isfile(exe_path):
                        return exe_path
                except (OSError, PermissionError):
                    continue
    except Exception:
        pass
    return None

def find_pid_by_path(binary_path):
    name = os.path.basename(binary_path)
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True
            )
            for line in result.stdout.strip().splitlines():
                parts = line.strip('"').split('","')
                if len(parts) >= 2 and parts[0].lower() == name.lower():
                    return int(parts[1])
        else:
            result = subprocess.run(["pgrep", "-f", binary_path], capture_output=True, text=True)
            pids = result.stdout.strip().splitlines()
            if pids:
                return int(pids[0])
    except Exception:
        pass
    return None

def kill_process(pid):
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, signal.SIGKILL)
        time.sleep(0.8)
        return True
    except Exception:
        return False

def start_process(binary_path, workdir):
    try:
        kwargs = {
            "cwd": workdir or os.path.dirname(binary_path) or ".",
        }
        if platform.system() == "Windows":
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([binary_path], **kwargs)
        return True
    except Exception as e:
        messagebox.showerror("Ошибка запуска", str(e))
        return False

def restart_process(binary_path, label, status_cb):
    if not binary_path or not os.path.isfile(binary_path):
        messagebox.showwarning("Не найден", f"Бинарник {label} не указан или не существует.")
        return
    status_cb(f"{label}: останавливаю...")
    pid = find_pid_by_path(binary_path)
    if pid:
        kill_process(pid)
    workdir = os.path.dirname(binary_path)
    status_cb(f"{label}: запускаю...")
    ok = start_process(binary_path, workdir)
    status_cb(f"{label}: {'запущен ✓' if ok else 'ошибка ✗'}")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config_data = load_config()
        self.tray_icon = None
        self.is_quitting = False

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Restarter")
        self.geometry("480x380")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_ui()
        self._check_gnome()

        if TRAY_AVAILABLE and get_de() != "gnome":
            self._setup_tray()

        self.after(100, self._autodetect)

    def _autodetect(self):
        changed = False
        if not self.config_data.get("telegram"):
            path = detect_running_path(TELEGRAM_NAMES)
            if path:
                self.config_data["telegram"] = path
                self.tg_entry.insert(0, path)
                changed = True
        if not self.config_data.get("discord"):
            path = detect_running_path(DISCORD_NAMES)
            if path:
                self.config_data["discord"] = path
                self.dc_entry.insert(0, path)
                changed = True
        if changed:
            save_config(self.config_data)

    def _build_ui(self):
        pad = {"padx": 20, "pady": 8}

        header = ctk.CTkLabel(self, text="Restarter", font=ctk.CTkFont(size=22, weight="bold"))
        header.pack(pady=(24, 4))

        sub = ctk.CTkLabel(self, text="Telegram & Discord process manager", font=ctk.CTkFont(size=13), text_color="gray")
        sub.pack(pady=(0, 20))

        # Telegram
        tg_frame = ctk.CTkFrame(self, corner_radius=10)
        tg_frame.pack(fill="x", **pad)

        ctk.CTkLabel(tg_frame, text="Telegram", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(10, 4))

        tg_row = ctk.CTkFrame(tg_frame, fg_color="transparent")
        tg_row.pack(fill="x", padx=10, pady=(0, 10))

        self.tg_entry = ctk.CTkEntry(tg_row, placeholder_text="Путь к бинарнику...", height=34)
        self.tg_entry.pack(side="left", fill="x", expand=True, padx=(4, 6))
        if self.config_data.get("telegram"):
            self.tg_entry.insert(0, self.config_data["telegram"])

        ctk.CTkButton(tg_row, text="Обзор", width=70, height=34, command=lambda: self._browse("telegram")).pack(side="right", padx=4)

        # Discord
        dc_frame = ctk.CTkFrame(self, corner_radius=10)
        dc_frame.pack(fill="x", **pad)

        ctk.CTkLabel(dc_frame, text="Discord", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(10, 4))

        dc_row = ctk.CTkFrame(dc_frame, fg_color="transparent")
        dc_row.pack(fill="x", padx=10, pady=(0, 10))

        self.dc_entry = ctk.CTkEntry(dc_row, placeholder_text="Путь к бинарнику...", height=34)
        self.dc_entry.pack(side="left", fill="x", expand=True, padx=(4, 6))
        if self.config_data.get("discord"):
            self.dc_entry.insert(0, self.config_data["discord"])

        ctk.CTkButton(dc_row, text="Обзор", width=70, height=34, command=lambda: self._browse("discord")).pack(side="right", padx=4)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(12, 4))

        ctk.CTkButton(btn_frame, text="⟳  Telegram", height=36, command=lambda: self._do_restart("telegram")).pack(side="left", expand=True, padx=(0, 4))
        ctk.CTkButton(btn_frame, text="⟳  Discord", height=36, fg_color="#5865F2", hover_color="#4752C4", command=lambda: self._do_restart("discord")).pack(side="left", expand=True, padx=(4, 4))
        ctk.CTkButton(btn_frame, text="⟳  Оба", height=36, fg_color="#2d6a4f", hover_color="#1b4332", command=self._do_restart_both).pack(side="left", expand=True, padx=(4, 0))

        # Status
        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12), text_color="gray")
        self.status_label.pack(pady=(8, 4))

    def _check_gnome(self):
        if get_de() == "gnome":
            messagebox.showinfo(
                "Трей недоступен",
                "GNOME не поддерживает системный трей по умолчанию.\n"
                "Приложение будет работать без иконки в трее.\n\n"
                "Можно установить расширение 'AppIndicator' из GNOME Extensions."
            )

    def _browse(self, target):
        path = filedialog.askopenfilename(title=f"Выберите бинарник {target}")
        if path:
            if target == "telegram":
                self.tg_entry.delete(0, "end")
                self.tg_entry.insert(0, path)
            else:
                self.dc_entry.delete(0, "end")
                self.dc_entry.insert(0, path)
            self._save_paths()

    def _save_paths(self):
        self.config_data["telegram"] = self.tg_entry.get()
        self.config_data["discord"] = self.dc_entry.get()
        save_config(self.config_data)

    def _set_status(self, text):
        self.after(0, lambda: self.status_label.configure(text=text))

    def _do_restart(self, target):
        self._save_paths()
        path = self.config_data.get(target, "")
        label = "Telegram" if target == "telegram" else "Discord"
        threading.Thread(target=restart_process, args=(path, label, self._set_status), daemon=True).start()

    def _do_restart_both(self):
        self._save_paths()
        def both():
            restart_process(self.config_data.get("telegram", ""), "Telegram", self._set_status)
            restart_process(self.config_data.get("discord", ""), "Discord", self._set_status)
        threading.Thread(target=both, daemon=True).start()

    def _setup_tray(self):
        try:
            img = Image.new("RGB", (64, 64), color=(37, 99, 235))
            draw_tray_icon(img)

            def toggle_label(item):
                return "Свернуть" if self.winfo_viewable() else "Развернуть"

            def toggle_action(icon, item):
                if self.winfo_viewable():
                    self.after(0, self.withdraw)
                else:
                    self.after(0, self.deiconify)
                    self.after(0, self.lift)

            menu = pystray.Menu(
                pystray.MenuItem(toggle_label, toggle_action, default=True),
                pystray.MenuItem("Перезапустить TG + Discord", lambda icon, item: self._tray_restart_both()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Выход", lambda icon, item: self._quit()),
            )
            self.tray_icon = pystray.Icon("Restarter", img, "Restarter", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception:
            pass

    def _tray_restart_both(self):
        self._do_restart_both()

    def on_close(self):
        if TRAY_AVAILABLE and self.tray_icon and get_de() != "gnome":
            self.withdraw()
        else:
            self._quit()

    def _quit(self):
        self.is_quitting = True
        if self.tray_icon:
            self.tray_icon.stop()
        self.destroy()

def draw_tray_icon(img):
    try:
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        d.ellipse([8, 8, 56, 56], fill=(255, 255, 255))
        d.text((18, 16), "R", fill=(37, 99, 235))
    except Exception:
        pass

if __name__ == "__main__":
    app = App()
    app.mainloop()
