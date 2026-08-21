"""Contrato do empacotamento Windows reproduzível."""

from pathlib import Path
import runpy
import subprocess
import sys

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
