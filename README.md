# Restarter

A simple utility to restart Telegram and Discord clients on Windows and Linux.

## Features

- Automatically detects running Telegram/Discord and fills in the paths — no manual configuration needed on first launch
- Finds the process by executable path, kills it and starts it again
- Minimizes to system tray with a context menu (toggle show/hide)
- Saves paths to `config.json` next to the executable
- Works on Windows and Linux (KDE, XFCE, MATE, Cinnamon, etc.)

> **GNOME**: system tray is not supported by default. The app works as a regular window. Tray can be enabled via the [AppIndicator](https://extensions.gnome.org/extension/615/appindicator-support/) extension.

## Run from source

```bash
pip install customtkinter pystray pillow
python restarter.py
```

### Tests

The test suite is headless and needs no GUI libraries (GUI deps are faked):

```bash
pip install -r requirements-dev.txt
pytest
```

## Downloads

Pre-built binaries are available on the [Releases](../../releases) page:

| File | Platform |
|------|----------|
| `Restarter.exe` | Windows |
| `Restarter` | Linux (Debian/Ubuntu) |
| `Restarter-rhel` | Linux (RHEL/Rocky/Fedora) |
| `Restarter-opensuse` | Linux (openSUSE) |

On Linux, make the file executable before running:
```bash
chmod +x Restarter
./Restarter
```

## config.json

Created automatically next to the executable. Stores paths to Telegram and Discord binaries. Filled in automatically if the apps are already running when Restarter starts.

## Tray

Closing the window (×) minimizes to tray, does not exit.  
Right-click the tray icon:
- **Show / Hide** — toggles the window
- **Restart TG + Discord** — restarts both
- **Exit** — closes the app

## How restart works

1. Looks up the process PID by executable path (`pgrep -f` on Linux, `tasklist` on Windows)
2. Kills the process (`SIGKILL` / `taskkill /F`)
3. Starts the executable again in its directory as a detached process

---

# Restarter

Проста утиліта для перезапуску клієнтів Telegram і Discord на Windows та Linux.

## Можливості

- Автоматично визначає запущені Telegram/Discord і заповнює шляхи — ніякого ручного налаштування при першому запуску
- Знаходить процес за шляхом до виконуваного файлу, вбиває і запускає знову
- Згортається в системний трей з контекстним меню (показати/сховати вікно)
- Зберігає шляхи у `config.json` поруч із собою
- Працює на Windows та Linux (KDE, XFCE, MATE, Cinnamon тощо)

> **GNOME**: системний трей не підтримується за замовчуванням. Застосунок працює у звичайному режимі вікна. Трей можна додати через розширення [AppIndicator](https://extensions.gnome.org/extension/615/appindicator-support/).

## Запуск із вихідного коду

```bash
pip install customtkinter pystray pillow
python restarter.py
```

## Завантаження

Готові бінарники доступні на сторінці [Releases](../../releases):

| Файл | Платформа |
|------|-----------|
| `Restarter.exe` | Windows |
| `Restarter` | Linux (Debian/Ubuntu) |
| `Restarter-rhel` | Linux (RHEL/Rocky/Fedora) |
| `Restarter-opensuse` | Linux (openSUSE) |

На Linux перед запуском зробіть файл виконуваним:
```bash
chmod +x Restarter
./Restarter
```

## config.json

Створюється автоматично поруч із виконуваним файлом. Зберігає шляхи до бінарників Telegram і Discord. Заповнюється автоматично, якщо застосунки вже запущені на момент старту Restarter.

## Трей

Закриття вікна (×) згортає в трей, не завершує роботу.  
Права кнопка на іконці трею:
- **Згорнути / Розгорнути** — перемикає видимість вікна
- **Перезапустити TG + Discord** — перезапускає обидва
- **Вихід** — завершує застосунок

## Як працює перезапуск

1. Шукає PID процесу за шляхом до виконуваного файлу (`pgrep -f` на Linux, `tasklist` на Windows)
2. Вбиває процес (`SIGKILL` / `taskkill /F`)
3. Запускає виконуваний файл знову в його директорії як detached процес
