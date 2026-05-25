#!/bin/bash
pip install customtkinter pystray pillow pyinstaller
pyinstaller --onefile --windowed --name BotRestarter restarter.py
echo "Done. Check dist/BotRestarter"
