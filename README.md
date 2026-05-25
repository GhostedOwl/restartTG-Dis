# Bot Restarter

Простая утилита для перезапуска Telegram и Discord ботов (бинарников) на Windows и Linux.

## Что умеет

- Находит процесс по пути к бинарнику, убивает и запускает заново
- Сворачивается в системный трей с контекстным меню
- Сохраняет пути к бинарникам в `config.json` рядом с собой
- Работает на Windows и Linux (KDE, XFCE, MATE, Cinnamon и др.)

> **GNOME**: системный трей не поддерживается по умолчанию. Приложение работает в обычном режиме окна. Можно добавить трей через расширение [AppIndicator](https://extensions.gnome.org/extension/615/appindicator-support/).

## Запуск из исходника

```bash
pip install customtkinter pystray pillow
python restarter.py
```

## Сборка в бинарник

**Linux:**
```bash
bash build_linux.sh
```

**Windows:**
```bat
build_windows.bat
```

Результат в папке `dist/`.

## config.json

Создаётся автоматически рядом с бинарником после первого выбора файлов.

```json
{
  "telegram": "/path/to/tgbot",
  "discord": "/path/to/discordbot"
}
```

## Как работает перезапуск

1. Ищет PID процесса по пути к бинарнику (`pgrep -f` на Linux, `tasklist` на Windows)
2. Убивает процесс (`SIGKILL` / `taskkill /F`)
3. Запускает бинарник заново в его директории как detached процесс

## Трей

При закрытии окна (крестик) приложение сворачивается в трей, не завершается.  
Правая кнопка на иконке трея:
- **Развернуть** — показывает окно
- **Перезапустить TG + Discord** — перезапускает оба бота
- **Выход** — завершает приложение
