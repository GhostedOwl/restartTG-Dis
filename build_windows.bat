@echo off
pip install customtkinter pystray pillow pyinstaller
pyinstaller --onefile --windowed --name BotRestarter --icon=icon.ico restarter.py
echo Done. Check dist\BotRestarter.exe
