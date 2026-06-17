"""Pytest bootstrap: fake GUI deps so restarter imports headless.

Runs at module-import time (before any test module imports restarter) so that
``import customtkinter`` / ``import tkinter`` resolve to fakes registered in
sys.modules. customtkinter is not installed in CI and we never want a real
display, real subprocess, or real filesystem side effects in the suite.
"""
import os
import sys
import types
from unittest.mock import MagicMock

import pytest

# --- repo root on sys.path so `import restarter` works -----------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# --- fake customtkinter ------------------------------------------------------
# restarter does `class App(ctk.CTk):` at import time, so CTk must be a REAL
# class (you cannot subclass a MagicMock instance). Everything else is only
# used at runtime, so MagicMock is fine.
_ctk = types.ModuleType("customtkinter")
_ctk.CTk = type("CTk", (), {})
for _attr in (
    "set_appearance_mode",
    "set_default_color_theme",
    "CTkFont",
    "CTkLabel",
    "CTkButton",
    "CTkEntry",
    "CTkFrame",
    "CTkToplevel",
    "CTkTextbox",
    "CTkCheckBox",
    "CTkScrollableFrame",
):
    setattr(_ctk, _attr, MagicMock(name="customtkinter.%s" % _attr))
sys.modules["customtkinter"] = _ctk

# --- fake tkinter + filedialog + messagebox ----------------------------------
# Lets the suite run with no python3-tk present. messagebox/filedialog
# functions are MagicMock so tests can assert calls.
_messagebox = types.ModuleType("tkinter.messagebox")
_messagebox.showerror = MagicMock(name="messagebox.showerror")
_messagebox.showwarning = MagicMock(name="messagebox.showwarning")
_messagebox.showinfo = MagicMock(name="messagebox.showinfo")

_filedialog = types.ModuleType("tkinter.filedialog")
_filedialog.askopenfilename = MagicMock(name="filedialog.askopenfilename")

_tk = types.ModuleType("tkinter")
_tk.messagebox = _messagebox
_tk.filedialog = _filedialog

sys.modules["tkinter"] = _tk
sys.modules["tkinter.messagebox"] = _messagebox
sys.modules["tkinter.filedialog"] = _filedialog

# NOTE: pystray / PIL are intentionally NOT faked. restarter imports them in a
# try/except, so their absence just sets TRAY_AVAILABLE = False.


@pytest.fixture(autouse=True)
def _reset_gui_mocks():
    """Reset call history on the fake GUI mocks before each test so that
    call-assertions do not leak between tests."""
    for mock in (
        _messagebox.showerror,
        _messagebox.showwarning,
        _messagebox.showinfo,
        _filedialog.askopenfilename,
    ):
        mock.reset_mock()
    yield
