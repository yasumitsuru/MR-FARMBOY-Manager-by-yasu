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
    return any(path.is_file() for path in directory.rglob("*"))


def _file_snapshot(directory: Path) -> dict[Path, tuple[int, int]]:
    snapshot: dict[Path, tuple[int, int]] = {}
    for path in directory.rglob("*"):
        try:
            if path.is_file():
                metadata = path.stat()
        except OSError:
            continue
        else:
            snapshot[path.relative_to(directory)] = (metadata.st_size, metadata.st_mtime_ns)
    return snapshot


def _changed_files(
    before: dict[Path, tuple[int, int]], after: dict[Path, tuple[int, int]]
) -> list[Path]:
    return sorted(
        path for path, metadata in after.items() if before.get(path) != metadata
    )


def smoke_test(executable: Path, timeout_seconds: float = 20.0) -> None:
    if not executable.is_file():
        raise FileNotFoundError("Executável do build não encontrado.")

    with tempfile.TemporaryDirectory(prefix="mr-farmboy-smoke-") as temporary:
        temporary_root = Path(temporary)
        runtime_root = temporary_root / "runtime"
        isolated_roots = {
            "APPDATA": temporary_root / "appdata",
            "LOCALAPPDATA": temporary_root / "localappdata",
            "TEMP": temporary_root / "temp",
            "TMP": temporary_root / "tmp",
            "USERPROFILE": temporary_root / "userprofile",
        }
        for directory in isolated_roots.values():
            directory.mkdir()
        environment = os.environ.copy()
        environment.update(
            {
                "MR_FARMBOY_RUNTIME_ROOT": str(runtime_root),
                "QT_QPA_PLATFORM": "offscreen",
                # Qt otherwise writes QML bytecode caches below USERPROFILE.
                "QML_DISABLE_DISK_CACHE": "1",
                **{name: str(directory) for name, directory in isolated_roots.items()},
            }
        )
        cwd_before = _file_snapshot(executable.parent)
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
        unexpected_boundaries = [
            name for name, directory in isolated_roots.items() if _has_files(directory)
        ]
        if _changed_files(cwd_before, _file_snapshot(executable.parent)):
            unexpected_boundaries.append("cwd")
        if unexpected_boundaries:
            boundaries = ", ".join(unexpected_boundaries)
            raise RuntimeError(
                "O executável escreveu em fronteiras isoladas fora de "
                f"MR_FARMBOY_RUNTIME_ROOT: {boundaries}."
            )


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    executable = Path(arguments[0]) if arguments else artifact_path(PROJECT_ROOT)
    smoke_test(executable.resolve(strict=False))
    print(f"Smoke test aprovado: {executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
