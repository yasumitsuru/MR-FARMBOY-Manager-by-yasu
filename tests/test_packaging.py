"""Contrato do empacotamento Windows reproduzível."""

from pathlib import Path
import runpy
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest


def test_windows_build_command_is_onedir_gui_and_excludes_local_data() -> None:
    from tools.build_windows import APP_NAME, build_command

    project_root = Path("C:/project")
    command = build_command(Path("C:/python/python.exe"), project_root)
    rendered = " ".join(str(argument) for argument in command)

    assert command[:3] == ["C:\\python\\python.exe", "-m", "PyInstaller"]
    assert "--windowed" in command
    assert "--onedir" in command
    assert command[command.index("--name") + 1] == APP_NAME
    assert str(project_root / "tools" / "windows_entrypoint.py") in command
    assert "locais.txt" not in rendered
    assert "--add-data" not in command


def test_windows_artifact_path_points_to_expected_executable() -> None:
    from tools.build_windows import APP_NAME, artifact_path

    project_root = Path("C:/project")

    assert artifact_path(project_root) == (
        project_root / "dist" / APP_NAME / f"{APP_NAME}.exe"
    )


def test_build_collects_qml_runtime_plugins() -> None:
    from tools.build_windows import build_command

    command = build_command(project_root=Path("C:/project"))
    joined = " ".join(command)

    assert "PySide6.QtQml" in joined
    assert "PySide6.QtQuick" in joined
    assert "PySide6.QtQuickControls2" in joined


def test_windows_entrypoint_delegates_exit_code_to_qml_run(monkeypatch) -> None:
    import mr_farmboy_manager.qml_application

    calls: list[str] = []
    monkeypatch.setattr(
        mr_farmboy_manager.qml_application,
        "run",
        lambda: calls.append("run") or 23,
    )

    with pytest.raises(SystemExit) as raised:
        runpy.run_path("tools/windows_entrypoint.py", run_name="__main__")

    assert raised.value.code == 23
    assert calls == ["run"]


def test_smoke_detects_qml_resource_load_and_readiness(tmp_path: Path) -> None:
    from tools.smoke_windows_build import _required_events_were_logged

    log_path = tmp_path / "runtime" / "logs" / "mr-farmboy-manager.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        "qml.load.completed\nqml.controller.initialized\n",
        encoding="utf-8",
    )

    assert _required_events_were_logged(tmp_path / "runtime")


@pytest.mark.parametrize(
    "events, expected",
    [
        ("", False),
        ("qml.load.completed\n", False),
        ("qml.controller.initialized\n", False),
        ("qml.load.completed\nqml.controller.initialized\n", True),
    ],
)
def test_smoke_requires_both_qml_load_and_readiness_events(
    tmp_path: Path, events: str, expected: bool
) -> None:
    from tools.smoke_windows_build import _required_events_were_logged

    log_path = tmp_path / "runtime" / "logs" / "mr-farmboy-manager.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(events, encoding="utf-8")

    assert _required_events_were_logged(tmp_path / "runtime") is expected


def test_smoke_rejects_writes_to_isolated_temp_root(
    monkeypatch, tmp_path: Path
) -> None:
    import tools.smoke_windows_build as smoke

    executable = tmp_path / "MR-FARMBOY-Manager.exe"
    executable.touch()

    class FakeProcess:
        def __init__(self, _command, *, env, **_kwargs) -> None:
            runtime_root = Path(env["MR_FARMBOY_RUNTIME_ROOT"])
            log_path = runtime_root / "logs" / smoke.LOG_FILENAME
            log_path.parent.mkdir(parents=True)
            log_path.write_text(
                "qml.load.completed\nqml.controller.initialized\n", encoding="utf-8"
            )
            temp_root = runtime_root.parent / "temp"
            temp_root.mkdir(exist_ok=True)
            (temp_root / "unexpected-empty-directory").mkdir()
            self.running = True

        def poll(self):
            return None if self.running else 0

        def terminate(self) -> None:
            self.running = False

        def wait(self, timeout: float) -> int:
            self.running = False
            return 0

    monkeypatch.setattr(smoke.subprocess, "Popen", FakeProcess)

    with pytest.raises(RuntimeError, match="TEMP"):
        smoke.smoke_test(executable)


def test_smoke_accepts_clean_isolated_roots(monkeypatch, tmp_path: Path) -> None:
    import tools.smoke_windows_build as smoke

    executable = tmp_path / "MR-FARMBOY-Manager.exe"
    executable.touch()

    class FakeProcess:
        def __init__(self, _command, *, env, **_kwargs) -> None:
            runtime_root = Path(env["MR_FARMBOY_RUNTIME_ROOT"])
            log_path = runtime_root / "logs" / smoke.LOG_FILENAME
            log_path.parent.mkdir(parents=True)
            log_path.write_text(
                "qml.load.completed\nqml.controller.initialized\n", encoding="utf-8"
            )
            self.running = True

        def poll(self):
            return None if self.running else 0

        def terminate(self) -> None:
            self.running = False

        def wait(self, timeout: float) -> int:
            self.running = False
            return 0

    monkeypatch.setattr(smoke.subprocess, "Popen", FakeProcess)

    smoke.smoke_test(executable)


def test_smoke_disables_qml_disk_cache(monkeypatch, tmp_path: Path) -> None:
    import tools.smoke_windows_build as smoke

    executable = tmp_path / "MR-FARMBOY-Manager.exe"
    executable.touch()
    captured_environment: dict[str, str] = {}

    class FakeProcess:
        def __init__(self, _command, *, env, **_kwargs) -> None:
            captured_environment.update(env)
            runtime_root = Path(env["MR_FARMBOY_RUNTIME_ROOT"])
            log_path = runtime_root / "logs" / smoke.LOG_FILENAME
            log_path.parent.mkdir(parents=True)
            log_path.write_text(
                "qml.load.completed\nqml.controller.initialized\n", encoding="utf-8"
            )
            self.running = True

        def poll(self):
            return None if self.running else 0

        def terminate(self) -> None:
            self.running = False

        def wait(self, timeout: float) -> int:
            self.running = False
            return 0

    monkeypatch.setattr(smoke.subprocess, "Popen", FakeProcess)

    smoke.smoke_test(executable)

    assert captured_environment["QML_DISABLE_DISK_CACHE"] == "1"


def test_tree_snapshot_records_reparse_point_without_descending(
    monkeypatch, tmp_path: Path
) -> None:
    import tools.smoke_windows_build as smoke

    link_path = tmp_path / "link"
    metadata = SimpleNamespace(
        st_mode=stat.S_IFDIR,
        st_size=0,
        st_mtime_ns=1,
        st_file_attributes=smoke.FILE_ATTRIBUTE_REPARSE_POINT,
    )

    class FakeEntry:
        name = "link"
        path = str(link_path)

        def stat(self, *, follow_symlinks: bool):
            assert not follow_symlinks
            return metadata

    class FakeScandir:
        def __enter__(self):
            return iter([FakeEntry()])

        def __exit__(self, *_args) -> None:
            return None

    scanned: list[Path] = []

    def fake_scandir(path):
        scanned.append(Path(path))
        return FakeScandir()

    monkeypatch.setattr(smoke.os, "scandir", fake_scandir)
    monkeypatch.setattr(smoke.os, "readlink", lambda _path: "target")

    snapshot = smoke._tree_snapshot(tmp_path)

    assert snapshot[Path("link")][0] == "reparse"
    assert scanned == [tmp_path]


def test_smoke_script_can_import_its_build_helper() -> None:
    result = subprocess.run(
        [sys.executable, "tools/smoke_windows_build.py", "missing.exe"],
        capture_output=True,
        cwd=Path.cwd(),
        text=True,
    )

    assert result.returncode == 1
    assert "Executável do build não encontrado" in result.stderr
    assert "No module named 'tools'" not in result.stderr
