"""Tests for the stable core-logic functions of restarter.

GUI deps are faked in conftest.py (imported before this module), so
`import restarter` runs headless. Covered functions: get_de, load_config,
save_config, detect_running_path, start_process, and the process-management
functions find_pids_by_path / kill_processes / wait_until_gone /
restart_process (now tested here on this branch).
"""
import json
from unittest.mock import MagicMock

import pytest

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


@pytest.mark.xfail(
    reason="known bug: load_config does not validate that the parsed value is "
    "a dict; tracked in review backlog",
    strict=True,
)
def test_load_config_valid_non_dict(monkeypatch, tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text("[]")  # valid JSON, but not a dict
    monkeypatch.setattr(restarter, "CONFIG_FILE", str(cfg_file))
    # DESIRED behavior: fall back to the default dict.
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


# --------------------------------------------------------------------------- #
# find_pids_by_path - Linux
# --------------------------------------------------------------------------- #
def test_find_pids_by_path_linux_selects_matches_and_skips(monkeypatch):
    # Glob list covers every branch:
    #   /proc/100/exe -> matches target              -> included
    #   /proc/999/exe -> own pid (getpid)            -> excluded (own-pid guard)
    #   /proc/self/exe -> int("self") raises ValueError -> skipped
    #   /proc/200/exe -> readlink raises OSError      -> skipped
    #   /proc/300/exe -> resolves to a non-target exe -> excluded
    monkeypatch.setattr(restarter.platform, "system", lambda: "Linux")
    monkeypatch.setattr(restarter.os, "getpid", lambda: 999)
    monkeypatch.setattr(
        restarter.glob,
        "glob",
        lambda pattern: [
            "/proc/100/exe",
            "/proc/999/exe",
            "/proc/self/exe",
            "/proc/200/exe",
            "/proc/300/exe",
        ],
    )

    def fake_readlink(link):
        if link == "/proc/200/exe":
            raise OSError("permission denied")
        if link == "/proc/300/exe":
            return "/usr/bin/firefox"
        # 100 and 999 both point at the real binary
        return "/opt/Telegram/Telegram"

    monkeypatch.setattr(restarter.os, "readlink", fake_readlink)
    # realpath is identity here so target == the link destinations above.
    monkeypatch.setattr(restarter.os.path, "realpath", lambda p: p)

    result = restarter.find_pids_by_path("/opt/Telegram/Telegram")
    assert result == [100]


def test_find_pids_by_path_linux_no_match(monkeypatch):
    monkeypatch.setattr(restarter.platform, "system", lambda: "Linux")
    monkeypatch.setattr(restarter.os, "getpid", lambda: 999)
    monkeypatch.setattr(restarter.glob, "glob", lambda pattern: ["/proc/100/exe"])
    monkeypatch.setattr(restarter.os, "readlink", lambda link: "/usr/bin/firefox")
    monkeypatch.setattr(restarter.os.path, "realpath", lambda p: p)
    assert restarter.find_pids_by_path("/opt/Telegram/Telegram") == []


# --------------------------------------------------------------------------- #
# find_pids_by_path - Windows
# --------------------------------------------------------------------------- #
def test_find_pids_by_path_windows_selects_matches(monkeypatch):
    # Matching separators between target and CSV path: this verifies row
    # parsing, the empty-Path skip, the non-matching skip, and the non-numeric
    # Id ValueError skip. Separator/case unification is checked separately
    # below (normcase/normpath are no-ops on a Linux host).
    monkeypatch.setattr(restarter.platform, "system", lambda: "Windows")

    class FakeResult:
        stdout = (
            '"Id","Path"\n'
            '"100","C:\\app\\Telegram.exe"\n'   # match
            '"200","C:\\app\\other.exe"\n'      # non-match
            '"300",""\n'                         # empty path -> skip
            '"abc","C:\\app\\Telegram.exe"\n'    # non-numeric Id -> ValueError skip
        )

    monkeypatch.setattr(restarter.subprocess, "run", lambda *a, **k: FakeResult())
    result = restarter.find_pids_by_path("C:\\app\\Telegram.exe")
    assert result == [100]


def test_find_pids_by_path_windows_separator_unification(monkeypatch):
    # On a Linux CI host os.path.normcase is identity and normpath does not
    # swap "\" <-> "/", so to genuinely prove the intent (forward-slash target
    # from askopenfilename unifying with backslash Get-Process paths) we
    # emulate Windows normcase/normpath: lowercase + "/" -> "\".
    monkeypatch.setattr(restarter.platform, "system", lambda: "Windows")
    monkeypatch.setattr(restarter.os.path, "normcase", lambda p: p.lower())
    monkeypatch.setattr(restarter.os.path, "normpath", lambda p: p.replace("/", "\\"))

    class FakeResult:
        stdout = (
            '"Id","Path"\n'
            '"100","C:\\App\\Telegram.exe"\n'  # backslashes + mixed case
        )

    monkeypatch.setattr(restarter.subprocess, "run", lambda *a, **k: FakeResult())
    # Target passed with forward slashes and different case.
    result = restarter.find_pids_by_path("c:/app/telegram.exe")
    assert result == [100]


# --------------------------------------------------------------------------- #
# kill_processes - Linux
# --------------------------------------------------------------------------- #
def test_kill_processes_linux_kills_group_and_pid(monkeypatch):
    monkeypatch.setattr(restarter.platform, "system", lambda: "Linux")
    monkeypatch.setattr(restarter.os, "getpid", lambda: 1)
    # own group is 50; target pid 100 is in group 77 (different) -> killpg runs.
    monkeypatch.setattr(
        restarter.os, "getpgid", lambda pid: 50 if pid == 1 else 77
    )
    kill = MagicMock()
    killpg = MagicMock()
    monkeypatch.setattr(restarter.os, "kill", kill)
    monkeypatch.setattr(restarter.os, "killpg", killpg)

    restarter.kill_processes([100])

    killpg.assert_called_once_with(77, restarter.signal.SIGKILL)
    kill.assert_called_once_with(100, restarter.signal.SIGKILL)


def test_kill_processes_linux_own_group_guard(monkeypatch):
    # getpgid(pid) == getpgid(getpid()): killpg must NOT run, os.kill still does.
    monkeypatch.setattr(restarter.platform, "system", lambda: "Linux")
    monkeypatch.setattr(restarter.os, "getpid", lambda: 1)
    monkeypatch.setattr(restarter.os, "getpgid", lambda pid: 50)
    kill = MagicMock()
    killpg = MagicMock()
    monkeypatch.setattr(restarter.os, "kill", kill)
    monkeypatch.setattr(restarter.os, "killpg", killpg)

    restarter.kill_processes([100])

    killpg.assert_not_called()
    kill.assert_called_once_with(100, restarter.signal.SIGKILL)


def test_kill_processes_linux_continues_on_process_lookup_error(monkeypatch):
    # First pid is already gone (os.kill raises) -> loop continues to second.
    monkeypatch.setattr(restarter.platform, "system", lambda: "Linux")
    monkeypatch.setattr(restarter.os, "getpid", lambda: 1)
    monkeypatch.setattr(restarter.os, "getpgid", lambda pid: 50 if pid == 1 else 77)
    monkeypatch.setattr(restarter.os, "killpg", MagicMock())

    calls = []

    def fake_kill(pid, sig):
        calls.append(pid)
        if pid == 100:
            raise ProcessLookupError("no such process")

    monkeypatch.setattr(restarter.os, "kill", fake_kill)

    restarter.kill_processes([100, 200])
    assert calls == [100, 200]


# --------------------------------------------------------------------------- #
# kill_processes - Windows
# --------------------------------------------------------------------------- #
def test_kill_processes_windows_taskkill_per_pid(monkeypatch):
    monkeypatch.setattr(restarter.platform, "system", lambda: "Windows")
    run = MagicMock()
    monkeypatch.setattr(restarter.subprocess, "run", run)

    restarter.kill_processes([100, 200])

    assert run.call_count == 2
    for pid, call in zip((100, 200), run.call_args_list):
        args, kwargs = call
        assert args[0] == ["taskkill", "/F", "/T", "/PID", str(pid)]
        assert kwargs.get("capture_output") is True


# --------------------------------------------------------------------------- #
# wait_until_gone
# --------------------------------------------------------------------------- #
def test_wait_until_gone_returns_true_when_gone(monkeypatch):
    # find_pids_by_path returns [] immediately -> True without sleeping.
    monkeypatch.setattr(restarter, "find_pids_by_path", lambda path: [])
    sleep = MagicMock()
    monkeypatch.setattr(restarter.time, "sleep", sleep)
    assert restarter.wait_until_gone("/opt/Telegram/Telegram") is True
    sleep.assert_not_called()


def test_wait_until_gone_returns_false_on_timeout(monkeypatch):
    # timeout=0 -> while loop body never runs -> returns `not [123]` == False.
    monkeypatch.setattr(restarter, "find_pids_by_path", lambda path: [123])
    sleep = MagicMock()
    monkeypatch.setattr(restarter.time, "sleep", sleep)
    assert restarter.wait_until_gone("/opt/Telegram/Telegram", timeout=0) is False
    sleep.assert_not_called()


def test_wait_until_gone_loops_then_succeeds(monkeypatch):
    # First poll still alive, sleep, second poll gone -> True. Deterministic:
    # find_pids_by_path is stubbed to a fixed sequence and sleep is a no-op.
    results = iter([[1], []])
    monkeypatch.setattr(restarter, "find_pids_by_path", lambda path: next(results))
    sleep = MagicMock()
    monkeypatch.setattr(restarter.time, "sleep", sleep)
    assert restarter.wait_until_gone("/opt/Telegram/Telegram", timeout=5.0) is True
    sleep.assert_called_once_with(0.1)


# --------------------------------------------------------------------------- #
# restart_process
# --------------------------------------------------------------------------- #
def test_restart_process_bad_path_warns_and_returns(monkeypatch):
    monkeypatch.setattr(restarter.os.path, "isfile", lambda p: False)
    find = MagicMock()
    kill = MagicMock()
    start = MagicMock(return_value=True)
    monkeypatch.setattr(restarter, "find_pids_by_path", find)
    monkeypatch.setattr(restarter, "kill_processes", kill)
    monkeypatch.setattr(restarter, "start_process", start)

    status = []
    assert restarter.restart_process("/nope", "Telegram", status.append) is None

    restarter.messagebox.showwarning.assert_called_once()
    assert status == []
    find.assert_not_called()
    kill.assert_not_called()
    start.assert_not_called()


def test_restart_process_running_pids_full_flow(monkeypatch):
    monkeypatch.setattr(restarter.os.path, "isfile", lambda p: True)
    monkeypatch.setattr(restarter, "find_pids_by_path", lambda p: [100])
    kill = MagicMock()
    wait = MagicMock()
    start = MagicMock(return_value=True)
    monkeypatch.setattr(restarter, "kill_processes", kill)
    monkeypatch.setattr(restarter, "wait_until_gone", wait)
    monkeypatch.setattr(restarter, "start_process", start)

    status = []
    restarter.restart_process("/opt/Telegram/Telegram", "Telegram", status.append)

    kill.assert_called_once_with([100])
    wait.assert_called_once_with("/opt/Telegram/Telegram")
    start.assert_called_once_with("/opt/Telegram/Telegram", "/opt/Telegram")
    assert status == [
        "Telegram: зупиняю...",
        "Telegram: запускаю...",
        "Telegram: запущено ✓",
    ]


def test_restart_process_fresh_start_skips_kill(monkeypatch):
    # No running pids -> kill_processes/wait_until_gone NOT called, start still runs.
    monkeypatch.setattr(restarter.os.path, "isfile", lambda p: True)
    monkeypatch.setattr(restarter, "find_pids_by_path", lambda p: [])
    kill = MagicMock()
    wait = MagicMock()
    start = MagicMock(return_value=True)
    monkeypatch.setattr(restarter, "kill_processes", kill)
    monkeypatch.setattr(restarter, "wait_until_gone", wait)
    monkeypatch.setattr(restarter, "start_process", start)

    status = []
    restarter.restart_process("/opt/Telegram/Telegram", "Discord", status.append)

    kill.assert_not_called()
    wait.assert_not_called()
    start.assert_called_once()
    assert status[-1] == "Discord: запущено ✓"


def test_restart_process_start_failure_status(monkeypatch):
    monkeypatch.setattr(restarter.os.path, "isfile", lambda p: True)
    monkeypatch.setattr(restarter, "find_pids_by_path", lambda p: [])
    monkeypatch.setattr(restarter, "kill_processes", MagicMock())
    monkeypatch.setattr(restarter, "wait_until_gone", MagicMock())
    monkeypatch.setattr(restarter, "start_process", MagicMock(return_value=False))

    status = []
    restarter.restart_process("/opt/Telegram/Telegram", "Telegram", status.append)
    assert status[-1] == "Telegram: помилка ✗"
