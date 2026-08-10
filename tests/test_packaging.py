"""Contrato do empacotamento Windows reproduzível."""

from pathlib import Path


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
