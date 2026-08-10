"""Smoke test isolado do executável Windows empacotado."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from tools.build_windows import PROJECT_ROOT, artifact_path


READY_EVENT = "application.ready"
LOG_FILENAME = "mr-farmboy-manager.log"


def _ready_was_logged(local_app_data: Path) -> bool:
    for log_path in local_app_data.rglob(LOG_FILENAME):
        try:
            if READY_EVENT in log_path.read_text(encoding="utf-8"):
                return True
        except OSError:
            continue
    return False


def smoke_test(executable: Path, timeout_seconds: float = 20.0) -> None:
    if not executable.is_file():
        raise FileNotFoundError("Executável do build não encontrado.")

    with tempfile.TemporaryDirectory(prefix="mr-farmboy-smoke-") as temporary:
        temporary_root = Path(temporary)
        app_data = temporary_root / "appdata"
        local_app_data = temporary_root / "localappdata"
        app_data.mkdir()
        local_app_data.mkdir()
        environment = os.environ.copy()
        environment.update(
            {
                "APPDATA": str(app_data),
                "LOCALAPPDATA": str(local_app_data),
                "MR_FARMBOY_RUNTIME_ROOT": str(temporary_root / "runtime"),
                "QT_QPA_PLATFORM": "offscreen",
            }
        )
        process = subprocess.Popen(
            [str(executable)],
            cwd=executable.parent,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                exit_code = process.poll()
                if exit_code is not None:
                    raise RuntimeError(
                        f"O executável encerrou antes de ficar pronto (código {exit_code})."
                    )
                if _ready_was_logged(temporary_root):
                    return
                time.sleep(0.1)
            raise TimeoutError("O executável não registrou prontidão no prazo.")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    executable = Path(arguments[0]) if arguments else artifact_path(PROJECT_ROOT)
    smoke_test(executable.resolve(strict=False))
    print(f"Smoke test aprovado: {executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
