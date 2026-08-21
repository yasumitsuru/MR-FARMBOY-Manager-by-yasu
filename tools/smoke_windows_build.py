"""Smoke test isolado do executável Windows empacotado."""

from __future__ import annotations

import hashlib
import os
import stat
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
FILE_ATTRIBUTE_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


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


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_failure(operation: str, path: Path, error: OSError) -> RuntimeError:
    return RuntimeError(f"Falha ao {operation} em {path}: {error}")


def _is_reparse(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        attributes & FILE_ATTRIBUTE_REPARSE_POINT
    )


def _directory_metadata(
    metadata: os.stat_result, *, include_mtime: bool
) -> tuple[object, ...]:
    values: tuple[object, ...] = (
        metadata.st_mode,
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_ctime_ns,
    )
    return values + ((metadata.st_mtime_ns,) if include_mtime else ())


def _tree_snapshot(
    directory: Path, *, include_directory_mtime: bool = True
) -> dict[Path, tuple[object, ...]]:
    """Registra a árvore sem atravessar symlinks, junctions ou reparse points."""
    snapshot: dict[Path, tuple[object, ...]] = {}

    try:
        root_metadata = directory.lstat()
    except OSError as error:
        raise _snapshot_failure("executar lstat da raiz", directory, error) from error
    if _is_reparse(root_metadata):
        raise RuntimeError(f"A raiz do snapshot é um reparse point: {directory}")
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise RuntimeError(f"A raiz do snapshot não é um diretório: {directory}")
    snapshot[Path(".")] = (
        "directory",
        *_directory_metadata(root_metadata, include_mtime=include_directory_mtime),
    )

    def visit(current: Path, relative_root: Path) -> None:
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    relative_path = relative_root / entry.name
                    try:
                        metadata = entry.stat(follow_symlinks=False)
                    except OSError as error:
                        raise _snapshot_failure(
                            "executar stat da entrada", path, error
                        ) from error
                    if _is_reparse(metadata):
                        try:
                            target = os.readlink(path)
                        except OSError as error:
                            raise _snapshot_failure(
                                "ler reparse point", path, error
                            ) from error
                        snapshot[relative_path] = (
                            "reparse",
                            metadata.st_mode,
                            metadata.st_dev,
                            metadata.st_ino,
                            metadata.st_size,
                            metadata.st_ctime_ns,
                            metadata.st_mtime_ns,
                            target,
                        )
                    elif stat.S_ISDIR(metadata.st_mode):
                        snapshot[relative_path] = (
                            "directory",
                            *_directory_metadata(
                                metadata, include_mtime=include_directory_mtime
                            ),
                        )
                        visit(path, relative_path)
                    elif stat.S_ISREG(metadata.st_mode):
                        try:
                            digest = _file_digest(path)
                        except OSError as error:
                            raise _snapshot_failure(
                                "calcular digest", path, error
                            ) from error
                        snapshot[relative_path] = (
                            "file",
                            metadata.st_mode,
                            metadata.st_dev,
                            metadata.st_ino,
                            metadata.st_size,
                            metadata.st_ctime_ns,
                            metadata.st_mtime_ns,
                            digest,
                        )
                    else:
                        snapshot[relative_path] = (
                            "other",
                            metadata.st_mode,
                            metadata.st_dev,
                            metadata.st_ino,
                            metadata.st_size,
                            metadata.st_ctime_ns,
                            metadata.st_mtime_ns,
                        )
        except OSError as error:
            raise _snapshot_failure("executar scandir", current, error) from error

    visit(directory, Path())
    return snapshot


def _changed_entries(
    before: dict[Path, tuple[object, ...]], after: dict[Path, tuple[object, ...]]
) -> list[Path]:
    return sorted(
        path
        for path in before.keys() | after.keys()
        if before.get(path) != after.get(path)
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
        isolated_before = {
            name: _tree_snapshot(directory) for name, directory in isolated_roots.items()
        }
        cwd_before = _tree_snapshot(executable.parent, include_directory_mtime=False)
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
            name
            for name, directory in isolated_roots.items()
            if _changed_entries(isolated_before[name], _tree_snapshot(directory))
        ]
        cwd_changes = _changed_entries(
            cwd_before,
            _tree_snapshot(executable.parent, include_directory_mtime=False),
        )
        if cwd_changes:
            unexpected_boundaries.append("cwd")
        if unexpected_boundaries:
            boundaries = ", ".join(unexpected_boundaries)
            cwd_details = ", ".join(str(path) for path in cwd_changes)
            raise RuntimeError(
                "O executável escreveu em fronteiras isoladas fora de "
                "MR_FARMBOY_RUNTIME_ROOT: "
                f"{boundaries}. Cwd alterado: {cwd_details}."
            )


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    executable = Path(arguments[0]) if arguments else artifact_path(PROJECT_ROOT)
    smoke_test(executable.resolve(strict=False))
    print(f"Smoke test aprovado: {executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
