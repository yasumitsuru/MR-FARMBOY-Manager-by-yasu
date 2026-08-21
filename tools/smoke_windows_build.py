"""Smoke test isolado do executável Windows empacotado."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.build_windows import PROJECT_ROOT, artifact_path


QML_RESOURCE_LOAD_EVENT = "qml.load.completed"
READY_EVENT = "qml.controller.initialized"
LOG_FILENAME = "mr-farmboy-manager.log"


def _required_events_were_logged(runtime_root: Path) -> bool:
    logged_events: set[str] = set()
    for log_path in runtime_root.rglob(LOG_FILENAME):
        try:
            contents = log_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for event in (QML_RESOURCE_LOAD_EVENT, READY_EVENT):
            if event in contents:
                logged_events.add(event)
    return logged_events == {QML_RESOURCE_LOAD_EVENT, READY_EVENT}


def _has_files(directory: Path) -> bool:
    return any(directory.iterdir())


def smoke_test(executable: Path, timeout_seconds: float = 20.0) -> None:
    if not executable.is_file():
        raise FileNotFoundError("Executável do build não encontrado.")

    with tempfile.TemporaryDirectory(prefix="mr-farmboy-smoke-") as temporary:
        temporary_root = Path(temporary)
        app_data = temporary_root / "appdata"
        local_app_data = temporary_root / "localappdata"
        runtime_root = temporary_root / "runtime"
        app_data.mkdir()
        local_app_data.mkdir()
        environment = os.environ.copy()
        environment.update(
            {
                "APPDATA": str(app_data),
                "LOCALAPPDATA": str(local_app_data),
                "MR_FARMBOY_RUNTIME_ROOT": str(runtime_root),
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
        ready = False
        try:
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                exit_code = process.poll()
                if exit_code is not None:
                    raise RuntimeError(
                        f"O executável encerrou antes de ficar pronto (código {exit_code})."
                    )
                if _required_events_were_logged(runtime_root):
                    ready = True
                    break
                time.sleep(0.1)
            if not ready:
                raise TimeoutError("O executável não registrou prontidão no prazo.")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        if process.poll() is None:
            raise RuntimeError("O executável permaneceu em execução após o smoke test.")
        if _has_files(app_data) or _has_files(local_app_data):
            raise RuntimeError("O executável escreveu fora de MR_FARMBOY_RUNTIME_ROOT.")


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    executable = Path(arguments[0]) if arguments else artifact_path(PROJECT_ROOT)
    smoke_test(executable.resolve(strict=False))
    print(f"Smoke test aprovado: {executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
