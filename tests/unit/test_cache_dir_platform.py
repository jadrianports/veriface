"""D-28: the platform-monkeypatch substitute for a Windows CI runner.

CI runs on ``ubuntu-latest`` only; this test monkeypatches ``sys.platform``
and the relevant environment variables to prove both the Windows and Linux
cache-path resolutions, without needing an actual Windows runner.
"""

from __future__ import annotations

import sys
from pathlib import Path

from veriface.config import VerifaceSettings, clear_settings_cache, default_cache_dir


def test_windows_resolution_uses_localappdata(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\tester\AppData\Local")
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    resolved = default_cache_dir()

    assert resolved == Path(r"C:\Users\tester\AppData\Local") / "veriface" / "cache"


def test_windows_resolution_falls_back_without_localappdata(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    resolved = default_cache_dir()

    assert resolved == Path.home() / "AppData" / "Local" / "veriface" / "cache"


def test_linux_resolution_uses_xdg_cache_home(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", "/home/tester/.cache")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    resolved = default_cache_dir()

    assert resolved == Path("/home/tester/.cache") / "veriface"


def test_linux_resolution_falls_back_without_xdg_cache_home(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    resolved = default_cache_dir()

    assert resolved == Path.home() / ".cache" / "veriface"


def test_windows_and_linux_resolutions_differ(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\tester\AppData\Local")
    windows_resolution = default_cache_dir()

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", "/home/tester/.cache")
    linux_resolution = default_cache_dir()

    assert windows_resolution != linux_resolution


def test_explicit_env_var_overrides_platform_default(monkeypatch, tmp_path):
    override = tmp_path / "explicit-cache"
    monkeypatch.setenv("VERIFACE_CACHE_DIR", str(override))
    clear_settings_cache()

    settings = VerifaceSettings()

    assert settings.cache_dir == override
    clear_settings_cache()
