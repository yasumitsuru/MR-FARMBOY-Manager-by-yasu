"""Restauração transacional de backups, sempre sobre diretórios temporários."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from mr_farmboy_manager.backups import (
    BACKUP_PAYLOAD_DIRECTORY,
    BackupCreationResult,
    BackupErrorCode,
    create_backup,
    restore_backup,
)
from mr_farmboy_manager.save_slots import SaveSlot


SUFFIX = "a" * 32
CREATED_AT = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


def _create_selected_backup(tmp_path: Path, *, slot_number: int = 1):
    game_data = tmp_path / "game_data"
    slot_path = game_data / f"save_{slot_number}"
    slot_path.mkdir(parents=True)
    (slot_path / "player_data.tres").write_bytes(b"selected-backup")
    nested = slot_path / "island"
    nested.mkdir()
    (nested / "main.tres").write_bytes(b"island-backup")
    backup_root = tmp_path / "manager" / "backups"
    slot = SaveSlot(slot_number, slot_path)
    created = create_backup(
        slot,
        game_data,
        backup_root,
        created_at=CREATED_AT,
        suffix=SUFFIX,
    )
    assert created.is_success and created.backup is not None
    return game_data, slot, backup_root, created.backup


def _replace_active_contents(slot: SaveSlot) -> None:
    (slot.path / "player_data.tres").write_bytes(b"current-active")
    (slot.path / "island" / "main.tres").write_bytes(b"current-island")
    (slot.path / "new_file.tres").write_bytes(b"current-only")


def test_restore_replaces_slot_and_keeps_preventive_backup(tmp_path: Path) -> None:
    game_data, slot, backup_root, selected = _create_selected_backup(tmp_path)
    _replace_active_contents(slot)

    result = restore_backup(
        slot,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=True,
    )

    assert result.is_success
    assert result.restored_backup == selected
    assert result.preventive_backup is not None
    assert result.preventive_backup.backup_id != selected.backup_id
    assert not result.cleanup_pending
    assert (slot.path / "player_data.tres").read_bytes() == b"selected-backup"
    assert (slot.path / "island" / "main.tres").read_bytes() == b"island-backup"
    assert not (slot.path / "new_file.tres").exists()
    preventive_payload = (
        result.preventive_backup.destination
        / BACKUP_PAYLOAD_DIRECTORY
        / "player_data.tres"
    )
    assert preventive_payload.read_bytes() == b"current-active"
    assert not any(path.name.startswith(".restore-") for path in game_data.iterdir())


def test_restore_requires_confirmation_before_any_write(tmp_path: Path) -> None:
    game_data, slot, backup_root, selected = _create_selected_backup(tmp_path)
    _replace_active_contents(slot)
    before = {path.name for path in backup_root.iterdir()}

    result = restore_backup(
        slot,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=False,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.RESTORE_NOT_CONFIRMED
    assert (slot.path / "player_data.tres").read_bytes() == b"current-active"
    assert {path.name for path in backup_root.iterdir()} == before
    assert not any(path.name.startswith(".restore-") for path in game_data.iterdir())


@pytest.mark.parametrize("backup_id", ["../save_1", "missing", ""])
def test_restore_rejects_invalid_or_missing_backup_without_writing(
    tmp_path: Path, backup_id: str
) -> None:
    game_data, slot, backup_root, _selected = _create_selected_backup(tmp_path)
    _replace_active_contents(slot)
    before = {path.name for path in backup_root.iterdir()}

    result = restore_backup(
        slot,
        game_data,
        backup_root,
        backup_id,
        confirmed=True,
    )

    assert not result.is_success
    assert result.error_code in {
        BackupErrorCode.INVALID_BACKUP_ID,
        BackupErrorCode.RESTORE_BACKUP_NOT_FOUND,
    }
    assert (slot.path / "player_data.tres").read_bytes() == b"current-active"
    assert {path.name for path in backup_root.iterdir()} == before


def test_restore_rejects_backup_from_another_slot(tmp_path: Path) -> None:
    game_data, _slot_one, backup_root, selected = _create_selected_backup(
        tmp_path, slot_number=1
    )
    slot_two_path = game_data / "save_2"
    slot_two_path.mkdir()
    (slot_two_path / "player_data.tres").write_bytes(b"slot-two")
    slot_two = SaveSlot(2, slot_two_path)

    result = restore_backup(
        slot_two,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=True,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.RESTORE_BACKUP_INVALID
    assert (slot_two_path / "player_data.tres").read_bytes() == b"slot-two"


def test_restore_validates_hashes_before_preventive_backup(
    tmp_path: Path,
) -> None:
    game_data, slot, backup_root, selected = _create_selected_backup(tmp_path)
    _replace_active_contents(slot)
    payload_file = (
        selected.destination / BACKUP_PAYLOAD_DIRECTORY / "player_data.tres"
    )
    original = payload_file.read_bytes()
    payload_file.write_bytes(b"X" * len(original))
    calls = 0

    def creator(*_args, **_kwargs) -> BackupCreationResult:
        nonlocal calls
        calls += 1
        raise AssertionError("não deve criar backup preventivo")

    result = restore_backup(
        slot,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=True,
        preventive_backup_creator=creator,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.RESTORE_BACKUP_INVALID
    assert calls == 0
    assert (slot.path / "player_data.tres").read_bytes() == b"current-active"


def test_preventive_backup_failure_leaves_active_slot_untouched(
    tmp_path: Path,
) -> None:
    game_data, slot, backup_root, selected = _create_selected_backup(tmp_path)
    _replace_active_contents(slot)

    def creator(*_args, **_kwargs) -> BackupCreationResult:
        return BackupCreationResult(
            None,
            BackupErrorCode.COPY_FAILED,
            "falha interna com caminho privado",
        )

    result = restore_backup(
        slot,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=True,
        preventive_backup_creator=creator,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.RESTORE_PREVENTIVE_BACKUP_FAILED
    assert result.preventive_backup is None
    assert result.public_message == "Não foi possível criar o backup preventivo."
    assert (slot.path / "player_data.tres").read_bytes() == b"current-active"


def test_publish_failure_rolls_original_slot_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data, slot, backup_root, selected = _create_selected_backup(tmp_path)
    _replace_active_contents(slot)
    real_rename = backups_module.os.rename
    calls = 0

    def fail_second_rename(source, destination, *args, **kwargs):
        nonlocal calls
        if Path(source).parent == game_data:
            calls += 1
            if calls == 2:
                raise PermissionError("locked-private-path")
        return real_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(backups_module.os, "rename", fail_second_rename)
    result = restore_backup(
        slot,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=True,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.RESTORE_PUBLISH_FAILED
    assert (slot.path / "player_data.tres").read_bytes() == b"current-active"
    assert "locked-private-path" not in result.public_message
    assert str(tmp_path) not in result.public_message
    assert not any(path.name.startswith(".restore-") for path in game_data.iterdir())


def test_restore_keeps_rollback_tree_when_cleanup_inventory_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An extra file injected before cleanup must keep the old slot intact."""
    import mr_farmboy_manager.backups as backups_module

    game_data, slot, backup_root, selected = _create_selected_backup(tmp_path)
    _replace_active_contents(slot)
    real_remove = backups_module._remove_restore_directory
    injected: Path | None = None

    def inject_extra_before_cleanup(path, *args, **kwargs):
        nonlocal injected
        directory = Path(path)
        if directory.name.startswith(".restore-old-"):
            injected = directory / "foreign.tres"
            injected.write_bytes(b"must-stay")
        return real_remove(path, *args, **kwargs)

    monkeypatch.setattr(
        backups_module,
        "_remove_restore_directory",
        inject_extra_before_cleanup,
    )
    result = restore_backup(
        slot,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=True,
    )

    assert result.is_success
    assert result.cleanup_pending
    assert result.error_code is BackupErrorCode.RESTORE_CLEANUP_PENDING
    assert "limpeza temporária" in result.public_message.lower()
    assert str(tmp_path) not in result.public_message
    assert injected is not None and injected.read_bytes() == b"must-stay"
    assert (injected.parent / "player_data.tres").read_bytes() == b"current-active"
    assert (injected.parent / "island" / "main.tres").read_bytes() == b"current-island"
    assert (slot.path / "player_data.tres").read_bytes() == b"selected-backup"


def test_restore_keeps_staging_tree_when_failed_publish_cleanup_inventory_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An extra file injected into staging must make failed cleanup stay pending."""
    import mr_farmboy_manager.backups as backups_module

    game_data, slot, backup_root, selected = _create_selected_backup(tmp_path)
    _replace_active_contents(slot)
    real_rename = backups_module.os.rename
    real_remove = backups_module._remove_restore_directory
    rename_calls = 0
    injected: Path | None = None

    def fail_publish(source, destination, *args, **kwargs):
        nonlocal rename_calls
        if Path(source).parent == game_data:
            rename_calls += 1
            if rename_calls == 2:
                raise PermissionError("locked-private-path")
        return real_rename(source, destination, *args, **kwargs)

    def inject_extra_before_cleanup(path, *args, **kwargs):
        nonlocal injected
        directory = Path(path)
        if directory.name.startswith(".restore-staging-"):
            injected = directory / "foreign.tres"
            injected.write_bytes(b"must-stay")
        return real_remove(path, *args, **kwargs)

    monkeypatch.setattr(backups_module.os, "rename", fail_publish)
    monkeypatch.setattr(
        backups_module,
        "_remove_restore_directory",
        inject_extra_before_cleanup,
    )
    result = restore_backup(
        slot,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=True,
    )

    assert not result.is_success
    assert result.cleanup_pending
    assert result.error_code is BackupErrorCode.RESTORE_CLEANUP_PENDING
    assert "limpeza temporária" in result.public_message.lower()
    assert "locked-private-path" not in result.public_message
    assert str(tmp_path) not in result.public_message
    assert injected is not None and injected.read_bytes() == b"must-stay"
    assert (injected.parent / "player_data.tres").read_bytes() == b"selected-backup"
    assert (injected.parent / "island" / "main.tres").read_bytes() == b"island-backup"
    assert (slot.path / "player_data.tres").read_bytes() == b"current-active"


def test_failed_rollback_reports_partial_state_and_preserves_both_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data, slot, backup_root, selected = _create_selected_backup(tmp_path)
    _replace_active_contents(slot)
    real_rename = backups_module.os.rename
    calls = 0

    def fail_publish_and_rollback(source, destination, *args, **kwargs):
        nonlocal calls
        if Path(source).parent == game_data:
            calls += 1
            if calls >= 2:
                raise PermissionError("locked-private-path")
        return real_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(backups_module.os, "rename", fail_publish_and_rollback)
    result = restore_backup(
        slot,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=True,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.RESTORE_ROLLBACK_FAILED
    remaining = [path for path in game_data.iterdir() if path.name.startswith(".restore-")]
    assert len(remaining) == 2
    assert any((path / "player_data.tres").read_bytes() == b"current-active" for path in remaining)
    assert any((path / "player_data.tres").read_bytes() == b"selected-backup" for path in remaining)
    assert "estado parcial" in result.public_message.lower()
    assert str(tmp_path) not in result.public_message


def test_cleanup_failure_reports_success_with_pending_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data, slot, backup_root, selected = _create_selected_backup(tmp_path)
    _replace_active_contents(slot)
    real_remove = backups_module._remove_restore_directory

    def fail_old_cleanup(path, *args, **kwargs):
        if Path(path).name.startswith(".restore-old-"):
            raise PermissionError("private-old-path")
        return real_remove(path, *args, **kwargs)

    monkeypatch.setattr(backups_module, "_remove_restore_directory", fail_old_cleanup)
    result = restore_backup(
        slot,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=True,
    )

    assert result.is_success
    assert result.cleanup_pending
    assert result.error_code is BackupErrorCode.RESTORE_CLEANUP_PENDING
    assert (slot.path / "player_data.tres").read_bytes() == b"selected-backup"
    assert "restaurado" in result.public_message.lower()
    assert "private-old-path" not in result.public_message
    assert str(tmp_path) not in result.public_message


def test_active_slot_swap_at_first_rename_is_detected_without_deleting_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data, slot, backup_root, selected = _create_selected_backup(tmp_path)
    _replace_active_contents(slot)
    displaced_original = game_data / "attacker-preserved-original"
    real_rename = backups_module.os.rename
    swapped = False

    def swap_before_rename(source, destination, *args, **kwargs):
        nonlocal swapped
        source_path = Path(source)
        if not swapped and source_path == slot.path:
            swapped = True
            real_rename(slot.path, displaced_original)
            slot.path.mkdir()
            (slot.path / "foreign.tres").write_bytes(b"foreign-data")
        return real_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(backups_module.os, "rename", swap_before_rename)
    result = restore_backup(
        slot,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=True,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.RESTORE_PUBLISH_FAILED
    assert (slot.path / "foreign.tres").read_bytes() == b"foreign-data"
    assert (displaced_original / "player_data.tres").read_bytes() == b"current-active"
    assert not any(path.name.startswith(".restore-") for path in game_data.iterdir())


@pytest.mark.skipif(__import__("os").name != "nt", reason="proteção Win32")
def test_windows_cleanup_refuses_directory_swapped_before_handle_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module
    from mr_farmboy_manager import save_details as secure_reader

    game_data, slot, backup_root, selected = _create_selected_backup(tmp_path)
    _replace_active_contents(slot)
    preserved_old = game_data / "preserved-old"
    real_open = secure_reader._open_win32_handle
    real_rename = backups_module.os.rename
    swapped = False

    def swap_then_open(path, access, flags):
        nonlocal swapped
        candidate = Path(path)
        if not swapped and candidate.name.startswith(".restore-old-"):
            swapped = True
            real_rename(candidate, preserved_old)
            candidate.mkdir()
            (candidate / "foreign.tres").write_bytes(b"foreign-data")
        return real_open(path, access, flags)

    monkeypatch.setattr(secure_reader, "_open_win32_handle", swap_then_open)
    result = restore_backup(
        slot,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=True,
    )

    assert result.is_success
    assert result.cleanup_pending
    replacement = next(
        path for path in game_data.iterdir() if path.name.startswith(".restore-old-")
    )
    assert (replacement / "foreign.tres").read_bytes() == b"foreign-data"
    assert (preserved_old / "player_data.tres").read_bytes() == b"current-active"
    assert (slot.path / "player_data.tres").read_bytes() == b"selected-backup"


@pytest.mark.skipif(__import__("os").name != "nt", reason="ABI Win32")
def test_windows_cleanup_uses_one_byte_file_disposition_info(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ctypes

    from mr_farmboy_manager import save_details as secure_reader

    game_data, slot, backup_root, selected = _create_selected_backup(tmp_path)
    _replace_active_contents(slot)
    real_set = secure_reader._KERNEL32.SetFileInformationByHandle
    observed: list[tuple[int, int]] = []

    def recording_set(handle, info_class, buffer, buffer_size):
        delete_byte = ctypes.cast(
            buffer,
            ctypes.POINTER(ctypes.c_ubyte),
        ).contents.value
        observed.append((buffer_size, delete_byte))
        return real_set(handle, info_class, buffer, buffer_size)

    monkeypatch.setattr(
        secure_reader._KERNEL32,
        "SetFileInformationByHandle",
        recording_set,
    )
    result = restore_backup(
        slot,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=True,
    )

    assert result.is_success and not result.cleanup_pending
    assert observed
    assert set(observed) == {(1, 1)}
    assert not any(path.name.startswith(".restore-old-") for path in game_data.iterdir())


def test_restore_staging_name_collision_is_not_overwritten_or_cleaned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data, slot, backup_root, selected = _create_selected_backup(tmp_path)
    _replace_active_contents(slot)
    token = "b" * 32
    collision = game_data / f".restore-staging-save_1-{token}"
    collision.mkdir()
    marker = collision / "owned.txt"
    marker.write_bytes(b"must-stay")
    monkeypatch.setattr(backups_module.secrets, "token_hex", lambda _length: token)

    result = restore_backup(
        slot,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=True,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.RESTORE_STAGING_FAILED
    assert marker.read_bytes() == b"must-stay"
    assert (slot.path / "player_data.tres").read_bytes() == b"current-active"


def test_restore_result_is_immutable(tmp_path: Path) -> None:
    game_data, slot, backup_root, selected = _create_selected_backup(tmp_path)

    result = restore_backup(
        slot,
        game_data,
        backup_root,
        selected.backup_id,
        confirmed=False,
    )

    with pytest.raises((AttributeError, TypeError)):
        result.cleanup_pending = True  # type: ignore[misc]
