"""Tests for the stable core-logic functions of restarter.

GUI deps are faked in conftest.py (imported before this module), so
`import restarter` runs headless. We only test functions that are stable on
this branch: get_de, load_config, save_config, detect_running_path,
start_process. find_pid_by_path / kill_process / restart_process are out of
scope (rewritten on another branch).
"""
import json
from unittest.mock import MagicMock

import restarter


# --------------------------------------------------------------------------- #
# get_de
# --------------------------------------------------------------------------- #
def test_get_de_windows(monkeypatch):
    monkeypatch.setattr(restarter.platform, "system", lambda: "Windows")
    assert restarter.get_de() == "windows"


def test_get_de_gnome(monkeypatch):
    monkeypatch.setattr(restarter.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "ubuntu:GNOME")
    assert restarter.get_de() == "gnome"


def test_get_de_other_de(monkeypatch):
    monkeypatch.setattr(restarter.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    assert restarter.get_de() == "other"


def test_get_de_empty_de(monkeypatch):
    monkeypatch.setattr(restarter.platform, "system", lambda: "Linux")
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    assert restarter.get_de() == "other"


# --------------------------------------------------------------------------- #
# load_config
# --------------------------------------------------------------------------- #
def test_load_config_valid(monkeypatch, tmp_path):
    cfg_file = tmp_path / "config.json"
    data = {"telegram": "/opt/Telegram/Telegram", "discord": "/usr/bin/discord"}
    cfg_file.write_text(json.dumps(data))
    monkeypatch.setattr(restarter, "CONFIG_FILE", str(cfg_file))
    assert restarter.load_config() == data


def test_load_config_missing_file(monkeypatch, tmp_path):
    cfg_file = tmp_path / "does_not_exist.json"
    monkeypatch.setattr(restarter, "CONFIG_FILE", str(cfg_file))
    assert restarter.load_config() == {"telegram": "", "discord": ""}


def test_load_config_corrupt_json(monkeypatch, tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text("{ this is not valid json ")
    monkeypatch.setattr(restarter, "CONFIG_FILE", str(cfg_file))
    assert restarter.load_config() == {"telegram": "", "discord": ""}


def test_load_config_valid_non_dict(monkeypatch, tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text("[]")  # valid JSON, but not a dict
    monkeypatch.setattr(restarter, "CONFIG_FILE", str(cfg_file))
    # Non-dict JSON falls back to the default dict.
    assert restarter.load_config() == {"telegram": "", "discord": ""}


# --------------------------------------------------------------------------- #
# save_config
# --------------------------------------------------------------------------- #
def test_save_config_roundtrip(monkeypatch, tmp_path):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(restarter, "CONFIG_FILE", str(cfg_file))
    data = {"telegram": "/a/b", "discord": "/c/d"}
    restarter.save_config(data)
    assert json.loads(cfg_file.read_text()) == data
    restarter.messagebox.showerror.assert_not_called()


def test_save_config_failure_shows_error(monkeypatch, tmp_path):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(restarter, "CONFIG_FILE", str(cfg_file))

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", boom)
    restarter.save_config({"telegram": "", "discord": ""})
    restarter.messagebox.showerror.assert_called_once()


# --------------------------------------------------------------------------- #
# detect_running_path
# --------------------------------------------------------------------------- #
def test_detect_running_path_linux_match(monkeypatch):
    monkeypatch.setattr(restarter.platform, "system", lambda: "Linux")
    monkeypatch.setattr(restarter.glob, "glob", lambda pattern: ["/proc/123/exe"])
    monkeypatch.setattr(restarter.os, "readlink", lambda link: "/opt/Telegram/Telegram")
    monkeypatch.setattr(restarter.os.path, "isfile", lambda path: True)
    result = restarter.detect_running_path(restarter.TELEGRAM_NAMES)
    assert result == "/opt/Telegram/Telegram"


def test_detect_running_path_linux_no_match(monkeypatch):
    monkeypatch.setattr(restarter.platform, "system", lambda: "Linux")
    monkeypatch.setattr(restarter.glob, "glob", lambda pattern: ["/proc/123/exe"])
    monkeypatch.setattr(restarter.os, "readlink", lambda link: "/usr/bin/firefox")
    monkeypatch.setattr(restarter.os.path, "isfile", lambda path: True)
    result = restarter.detect_running_path(restarter.TELEGRAM_NAMES)
    assert result is None


def test_detect_running_path_windows_match(monkeypatch):
    monkeypatch.setattr(restarter.platform, "system", lambda: "Windows")

    class FakeResult:
        stdout = (
            '"Name","Path"\n'
            '"firefox","C:\\Program Files\\Mozilla Firefox\\firefox.exe"\n'
            '"Telegram","C:\\Users\\me\\AppData\\Roaming\\Telegram Desktop\\Telegram.exe"\n'
        )

    monkeypatch.setattr(restarter.subprocess, "run", lambda *a, **k: FakeResult())
    monkeypatch.setattr(restarter.os.path, "isfile", lambda path: True)
    result = restarter.detect_running_path(restarter.TELEGRAM_NAMES)
    assert result == "C:\\Users\\me\\AppData\\Roaming\\Telegram Desktop\\Telegram.exe"


def test_detect_running_path_windows_no_file(monkeypatch):
    # Name matches but the executable does not exist on disk -> None (the
    # os.path.isfile guard inside detect_running_path must reject it).
    monkeypatch.setattr(restarter.platform, "system", lambda: "Windows")

    class FakeResult:
        stdout = (
            '"Name","Path"\n'
            '"Telegram","C:\\Users\\me\\AppData\\Roaming\\Telegram Desktop\\Telegram.exe"\n'
        )

    monkeypatch.setattr(restarter.subprocess, "run", lambda *a, **k: FakeResult())
    monkeypatch.setattr(restarter.os.path, "isfile", lambda path: False)
    result = restarter.detect_running_path(restarter.TELEGRAM_NAMES)
    assert result is None


# --------------------------------------------------------------------------- #
# start_process
# --------------------------------------------------------------------------- #
def test_start_process_linux(monkeypatch):
    monkeypatch.setattr(restarter.platform, "system", lambda: "Linux")
    popen = MagicMock()
    monkeypatch.setattr(restarter.subprocess, "Popen", popen)
    result = restarter.start_process("/opt/Telegram/Telegram", "/opt/Telegram")
    assert result is True
    popen.assert_called_once()
    args, kwargs = popen.call_args
    assert args[0] == ["/opt/Telegram/Telegram"]
    assert kwargs.get("start_new_session") is True
    assert kwargs.get("cwd") == "/opt/Telegram"


def test_start_process_windows(monkeypatch):
    monkeypatch.setattr(restarter.platform, "system", lambda: "Windows")
    # These flags do not exist on Linux's subprocess module; inject them.
    monkeypatch.setattr(restarter.subprocess, "DETACHED_PROCESS", 8, raising=False)
    monkeypatch.setattr(
        restarter.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False
    )
    popen = MagicMock()
    monkeypatch.setattr(restarter.subprocess, "Popen", popen)
    result = restarter.start_process("C:\\app\\Telegram.exe", "C:\\app")
    assert result is True
    popen.assert_called_once()
    _, kwargs = popen.call_args
    assert kwargs.get("creationflags") == (8 | 512)


def test_start_process_error_shows_message(monkeypatch):
    monkeypatch.setattr(restarter.platform, "system", lambda: "Linux")

    def boom(*args, **kwargs):
        raise OSError("no such file")

    monkeypatch.setattr(restarter.subprocess, "Popen", boom)
    result = restarter.start_process("/nope", "/tmp")
    assert result is False
    restarter.messagebox.showerror.assert_called_once()
