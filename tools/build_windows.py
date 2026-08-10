"""Build reproduzível do aplicativo Windows com PyInstaller."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


APP_NAME = "MR-FARMBOY-Manager"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def artifact_path(project_root: Path = PROJECT_ROOT) -> Path:
    return project_root / "dist" / APP_NAME / f"{APP_NAME}.exe"


def build_command(
    python_executable: Path = Path(sys.executable),
    project_root: Path = PROJECT_ROOT,
) -> list[str]:
    entry_point = project_root / "tools" / "windows_entrypoint.py"
    build_root = project_root / "build" / "pyinstaller"
    return [
        str(python_executable),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--noupx",
        "--name",
        APP_NAME,
        "--paths",
        str(project_root / "src"),
        "--distpath",
        str(project_root / "dist"),
        "--workpath",
        str(build_root / "work"),
        "--specpath",
        str(build_root),
        str(entry_point),
    ]


def main() -> int:
    if os.name != "nt":
        raise RuntimeError("O build deste projeto deve ser executado no Windows.")

    subprocess.run(build_command(), cwd=PROJECT_ROOT, check=True)
    executable = artifact_path()
    if not executable.is_file():
        raise RuntimeError("O executável esperado não foi produzido.")
    print(executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
