"""Exclusão segura de backups persistentes em diretórios temporários."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from mr_farmboy_manager.backups import (
    BackupErrorCode,
    create_backup,
    delete_backup,
)
from mr_farmboy_manager.save_slots import SaveSlot


def _create_backup(tmp_path: Path, *, slot_number: int = 1, suffix: str = "a" * 32):
    game_data = tmp_path / "game_data"
    slot_path = game_data / f"save_{slot_number}"
    slot_path.mkdir(parents=True, exist_ok=True)
    (slot_path / "player_data.tres").write_bytes(
        f"slot-{slot_number}-{suffix[0]}".encode()
    )
    root = tmp_path / "manager" / "backups"
    created = create_backup(
        SaveSlot(slot_number, slot_path),
        game_data,
        root,
        created_at=datetime(2026, 8, 8, 12, slot_number, tzinfo=UTC),
        suffix=suffix,
    )
    assert created.is_success and created.backup is not None
    return game_data, slot_path, root, created.backup


def test_delete_requires_confirmation_before_any_mutation(tmp_path: Path) -> None:
    _game_data, _slot_path, root, record = _create_backup(tmp_path)

    result = delete_backup(root, record.backup_id, confirmed=False)

    assert not result.is_success
    assert result.error_code is BackupErrorCode.DELETE_NOT_CONFIRMED
    assert record.destination.is_dir()


@pytest.mark.parametrize("backup_id", ["", "../save_1", "save_1", "C:\\private"])
def test_delete_rejects_invalid_id_without_touching_backup(
    tmp_path: Path, backup_id: str
) -> None:
    _game_data, _slot_path, root, record = _create_backup(tmp_path)

    result = delete_backup(root, backup_id, confirmed=True)

    assert not result.is_success
    assert result.error_code is BackupErrorCode.INVALID_BACKUP_ID
    assert record.destination.is_dir()


def test_delete_reports_missing_backup_without_broadening_target(tmp_path: Path) -> None:
    game_data, slot_path, root, record = _create_backup(tmp_path)
    missing_id = "save_1-20260808T130000Z-" + "b" * 32

    result = delete_backup(root, missing_id, confirmed=True)

    assert not result.is_success
    assert result.error_code is BackupErrorCode.DELETE_BACKUP_NOT_FOUND
    assert record.destination.is_dir()
    assert slot_path.is_dir()
    assert game_data.is_dir()


def test_delete_removes_only_selected_valid_backup(tmp_path: Path) -> None:
    _game_data, _slot_path, root, selected = _create_backup(
        tmp_path, suffix="a" * 32
    )
    sibling_result = create_backup(
        SaveSlot(1, tmp_path / "game_data" / "save_1"),
        tmp_path / "game_data",
        root,
        created_at=datetime(2026, 8, 8, 13, 0, tzinfo=UTC),
        suffix="b" * 32,
    )
    assert sibling_result.is_success and sibling_result.backup is not None
    sibling = sibling_result.backup

    result = delete_backup(root, selected.backup_id, confirmed=True)

    assert result.is_success
    assert result.deleted_backup_id == selected.backup_id
    assert result.error_code is None
    assert not selected.destination.exists()
    assert sibling.destination.is_dir()
    assert set(path.name for path in root.iterdir()) == {sibling.backup_id}


def test_delete_refuses_corrupted_backup(tmp_path: Path) -> None:
    _game_data, _slot_path, _root, record = _create_backup(tmp_path)
    payload = record.destination / "payload" / "player_data.tres"
    original = payload.read_bytes()
    payload.write_bytes(b"X" * len(original))

    result = delete_backup(record.destination.parent, record.backup_id, confirmed=True)

    assert not result.is_success
    assert result.error_code is BackupErrorCode.DELETE_BACKUP_INVALID
    assert record.destination.is_dir()
    assert payload.read_bytes() == b"X" * len(original)


def test_delete_refuses_foreign_top_level_entry(tmp_path: Path) -> None:
    _game_data, _slot_path, root, record = _create_backup(tmp_path)
    foreign = record.destination / "foreign.txt"
    foreign.write_bytes(b"must-stay")

    result = delete_backup(root, record.backup_id, confirmed=True)

    assert not result.is_success
    assert result.error_code is BackupErrorCode.DELETE_BACKUP_INVALID
    assert record.destination.is_dir()
    assert foreign.read_bytes() == b"must-stay"


def test_delete_cleanup_failure_is_sanitized_and_leaves_only_quarantine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    _game_data, _slot_path, root, record = _create_backup(tmp_path)

    def fail_remove(*_args, **_kwargs) -> None:
        raise PermissionError(f"private-token-{tmp_path}")

    monkeypatch.setattr(backups_module, "_remove_restore_directory", fail_remove)
    result = delete_backup(root, record.backup_id, confirmed=True)

    assert result.is_success
    assert result.error_code is BackupErrorCode.DELETE_CLEANUP_PENDING
    assert result.cleanup_pending
    assert result.deleted_backup_id == record.backup_id
    assert result.public_message == (
        "O backup foi excluído, mas uma limpeza temporária ficou pendente."
    )
    assert str(tmp_path) not in result.public_message
    assert "private-token" not in result.public_message
    assert not record.destination.exists()
    quarantines = tuple(
        entry for entry in root.iterdir() if entry.name.startswith(".delete-trash-")
    )
    assert len(quarantines) == 1
    assert (quarantines[0] / "manifest.json").is_file()
    assert (quarantines[0] / "payload" / "player_data.tres").is_file()


def test_delete_partial_cleanup_never_leaves_partial_canonical_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    _game_data, _slot_path, root, record = _create_backup(tmp_path)

    def partially_remove(directory: Path, *_args, **_kwargs) -> None:
        (directory / "manifest.json").unlink()
        raise PermissionError(f"private-token-{tmp_path}")

    monkeypatch.setattr(backups_module, "_remove_restore_directory", partially_remove)
    result = delete_backup(root, record.backup_id, confirmed=True)

    assert result.is_success
    assert result.error_code is BackupErrorCode.DELETE_CLEANUP_PENDING
    assert result.cleanup_pending
    assert not record.destination.exists()
    quarantines = tuple(
        entry for entry in root.iterdir() if entry.name.startswith(".delete-trash-")
    )
    assert len(quarantines) == 1
    assert not (quarantines[0] / "manifest.json").exists()
    assert (quarantines[0] / "payload" / "player_data.tres").is_file()


@pytest.mark.skipif(__import__("os").name != "nt", reason="proteção Win32")
def test_windows_delete_quarantines_swap_before_cleanup_handle_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module
    from mr_farmboy_manager import save_details as secure_reader

    _game_data, _slot_path, root, record = _create_backup(tmp_path)
    preserved = root / "preserved-valid-backup"
    real_open = secure_reader._open_win32_handle
    real_rename = backups_module.os.rename
    swapped = False

    def swap_then_open(path, access, flags):
        nonlocal swapped
        candidate = Path(path)
        if (
            not swapped
            and candidate.parent == root
            and candidate.name.startswith(".delete-trash-")
            and access & 0x00010000
        ):
            swapped = True
            real_rename(candidate, preserved)
            candidate.mkdir()
            (candidate / "foreign.txt").write_bytes(b"foreign")
        return real_open(path, access, flags)

    monkeypatch.setattr(secure_reader, "_open_win32_handle", swap_then_open)
    result = delete_backup(root, record.backup_id, confirmed=True)

    assert result.is_success
    assert result.error_code is BackupErrorCode.DELETE_CLEANUP_PENDING
    assert result.cleanup_pending
    assert not record.destination.exists()
    quarantines = tuple(
        entry for entry in root.iterdir() if entry.name.startswith(".delete-trash-")
    )
    assert len(quarantines) == 1
    assert (quarantines[0] / "foreign.txt").read_bytes() == b"foreign"
    assert (preserved / "payload" / "player_data.tres").is_file()


@pytest.mark.skipif(__import__("os").name != "nt", reason="proteção Win32")
def test_windows_delete_refuses_target_swapped_before_quarantine_handle_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module
    from mr_farmboy_manager import save_details as secure_reader

    _game_data, _slot_path, root, record = _create_backup(tmp_path)
    preserved = root / "preserved-valid-backup"
    real_open = secure_reader._open_win32_handle
    real_rename = backups_module.os.rename
    swapped = False

    def swap_then_open(path, access, flags):
        nonlocal swapped
        candidate = Path(path)
        if (
            not swapped
            and candidate == record.destination
            and access & 0x00010000
        ):
            swapped = True
            real_rename(candidate, preserved)
            candidate.mkdir()
            (candidate / "foreign.txt").write_bytes(b"must-stay")
        return real_open(path, access, flags)

    monkeypatch.setattr(secure_reader, "_open_win32_handle", swap_then_open)
    result = delete_backup(root, record.backup_id, confirmed=True)

    assert not result.is_success
    assert result.error_code is BackupErrorCode.DELETE_FAILED
    assert (record.destination / "foreign.txt").read_bytes() == b"must-stay"
    assert (preserved / "payload" / "player_data.tres").is_file()
    assert not any(entry.name.startswith(".delete-trash-") for entry in root.iterdir())


@pytest.mark.skipif(__import__("os").name != "nt", reason="proteção Win32")
def test_windows_quarantine_rename_is_relative_to_validated_root_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ctypes
    from ctypes import wintypes
    import os
    from types import SimpleNamespace

    import mr_farmboy_manager.backups as backups_module
    from mr_farmboy_manager import save_details as secure_reader

    _game_data, _slot_path, root, record = _create_backup(tmp_path)
    target = record.destination
    quarantine = root / f".delete-trash-{record.backup_id}-{'c' * 16}"
    root_state = os.lstat(root)
    target_state = os.lstat(target)

    class ObservedRename(RuntimeError):
        pass

    class FileRenameInfo(ctypes.Structure):
        _fields_ = [
            ("replace_or_flags", wintypes.DWORD),
            ("root_directory", wintypes.HANDLE),
            ("file_name_length", wintypes.DWORD),
            ("file_name", wintypes.WCHAR * 1),
        ]

    def inspect_rename(_handle, _io_status, information, _size, info_class):
        info = ctypes.cast(information, ctypes.POINTER(FileRenameInfo)).contents
        filename = ctypes.wstring_at(
            ctypes.addressof(info) + FileRenameInfo.file_name.offset,
            info.file_name_length // ctypes.sizeof(wintypes.WCHAR),
        )
        assert info_class == 10
        assert info.root_directory not in {None, 0}
        assert filename == quarantine.name
        raise ObservedRename

    real_win_dll = ctypes.WinDLL

    def intercept_ntdll(name, *args, **kwargs):
        if name == "ntdll":
            return SimpleNamespace(NtSetInformationFile=inspect_rename)
        return real_win_dll(name, *args, **kwargs)

    monkeypatch.setattr(ctypes, "WinDLL", intercept_ntdll)

    with pytest.raises(ObservedRename):
        backups_module._quarantine_backup_directory_windows(
            target,
            quarantine,
            root,
            root_state,
            target_state,
        )
    assert target.is_dir()
    assert not quarantine.exists()


@pytest.mark.skipif(__import__("os").name != "nt", reason="proteção Win32")
def test_windows_delete_never_removes_foreign_child_inserted_during_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    _game_data, _slot_path, root, record = _create_backup(tmp_path)
    real_scandir = backups_module.os.scandir
    quarantine_scans = 0

    def insert_foreign_before_cleanup_scan(path):
        nonlocal quarantine_scans
        candidate = Path(path)
        if candidate.parent == root and candidate.name.startswith(".delete-trash-"):
            quarantine_scans += 1
            if quarantine_scans == 2:
                (candidate / "foreign.txt").write_bytes(b"must-stay")
        return real_scandir(path)

    monkeypatch.setattr(backups_module.os, "scandir", insert_foreign_before_cleanup_scan)
    result = delete_backup(root, record.backup_id, confirmed=True)

    assert result.is_success
    assert result.error_code is BackupErrorCode.DELETE_CLEANUP_PENDING
    assert result.cleanup_pending
    assert not record.destination.exists()
    quarantines = tuple(
        entry for entry in root.iterdir() if entry.name.startswith(".delete-trash-")
    )
    assert len(quarantines) == 1
    assert (quarantines[0] / "foreign.txt").read_bytes() == b"must-stay"
    assert (quarantines[0] / "manifest.json").is_file()
    assert (quarantines[0] / "payload" / "player_data.tres").is_file()


def test_backup_root_cannot_turn_active_save_into_delete_target(tmp_path: Path) -> None:
    game_data, slot_path, _root, record = _create_backup(tmp_path)

    result = delete_backup(game_data, record.backup_id, confirmed=True)

    assert not result.is_success
    assert result.error_code is BackupErrorCode.DELETE_BACKUP_NOT_FOUND
    assert slot_path.is_dir()
    assert (slot_path / "player_data.tres").is_file()


def test_delete_result_is_immutable(tmp_path: Path) -> None:
    _game_data, _slot_path, root, record = _create_backup(tmp_path)
    result = delete_backup(root, record.backup_id, confirmed=False)

    with pytest.raises((AttributeError, TypeError)):
        result.deleted_backup_id = "changed"  # type: ignore[misc]
