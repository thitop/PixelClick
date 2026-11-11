"""Paths used by the packaged .exe (PyInstaller sets sys.frozen)."""
import sys
from pathlib import Path
from unittest import mock


def test_logs_go_next_to_the_exe_when_frozen(tmp_path):
    from utils.logger import get_log_dir
    exe = tmp_path / "PixelClick" / "PixelClick.exe"
    with mock.patch.object(sys, "frozen", True, create=True), \
            mock.patch.object(sys, "executable", str(exe)):
        assert get_log_dir() == exe.parent / "logs"


def test_logs_go_to_project_folder_from_source():
    from utils.logger import get_log_dir
    assert get_log_dir() == Path(__file__).resolve().parent.parent / "logs"
