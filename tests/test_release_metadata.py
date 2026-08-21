"""Consistência da metadata da release MVP."""

import tomllib
from pathlib import Path

from mr_farmboy_manager import __version__
from tools.build_windows import build_command


RELEASE_VERSION = "0.2.0"


def test_release_version_is_consistent_across_package_and_windows_metadata() -> None:
    project_root = Path(__file__).resolve().parents[1]
    project = tomllib.loads(
        (project_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    version_file = project_root / "packaging" / "windows_version_info.txt"
    command = build_command(project_root=project_root)

    assert __version__ == RELEASE_VERSION
    assert project["project"]["version"] == RELEASE_VERSION
    assert "Development Status :: 4 - Beta" in project["project"]["classifiers"]
    assert "Development Status :: 1 - Planning" not in project["project"]["classifiers"]
    version_info = version_file.read_text(encoding="utf-8")

    assert "filevers=(0, 2, 0, 0)" in version_info
    assert "prodvers=(0, 2, 0, 0)" in version_info
    assert "StringStruct('FileVersion', '0.2.0')" in version_info
    assert "StringStruct('ProductVersion', '0.2.0')" in version_info
    assert command[command.index("--version-file") + 1] == str(version_file)


def test_uv_lock_pins_current_project_release_version() -> None:
    project_root = Path(__file__).resolve().parents[1]
    lock = tomllib.loads((project_root / "uv.lock").read_text(encoding="utf-8"))
    package = next(
        item
        for item in lock["package"]
        if item["name"] == "mr-farmboy-manager-by-yasu"
    )

    assert package["version"] == RELEASE_VERSION


def test_changelog_contains_dated_mvp_release() -> None:
    project_root = Path(__file__).resolve().parents[1]
    changelog = (project_root / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## [0.1.0] - 2026-08-10" in changelog
    assert "backup" in changelog.lower()
    assert "restaura" in changelog.lower()
    assert "Windows" in changelog
