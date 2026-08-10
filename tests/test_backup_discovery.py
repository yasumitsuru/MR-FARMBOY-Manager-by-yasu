"""Descoberta e validação estrutural dos backups persistentes."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mr_farmboy_manager.backups import (
    BACKUP_MANIFEST_FILENAME,
    BackupErrorCode,
    create_backup,
    discover_backups,
)
from mr_farmboy_manager.save_slots import SaveSlot


SUFFIX_A = "a" * 32
SUFFIX_B = "b" * 32
SUFFIX_C = "c" * 32


def _slot(game_data: Path, number: int) -> SaveSlot:
    path = game_data / f"save_{number}"
    path.mkdir(parents=True, exist_ok=True)
    (path / "player_data.tres").write_text(
        f"slot sintetico {number}", encoding="utf-8"
    )
    return SaveSlot(number, path)


def _create(
    game_data: Path,
    backup_root: Path,
    number: int,
    created_at: datetime,
    suffix: str,
):
    result = create_backup(
        _slot(game_data, number),
        game_data,
        backup_root,
        created_at=created_at,
        suffix=suffix,
    )
    assert result.is_success and result.backup is not None
    return result.backup


def test_discover_backups_returns_empty_without_creating_missing_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "missing-backups"

    result = discover_backups(root)

    assert result.is_success
    assert result.backups == ()
    assert result.invalid_entries == ()
    assert "Nenhum backup" in result.public_message
    assert not root.exists()


def test_discover_backups_associates_slots_and_orders_newest_first(
    tmp_path: Path,
) -> None:
    game_data = tmp_path / "game_data"
    root = tmp_path / "backups"
    oldest = _create(
        game_data,
        root,
        1,
        datetime(2026, 8, 7, 10, tzinfo=UTC),
        SUFFIX_A,
    )
    newest = _create(
        game_data,
        root,
        2,
        datetime(2026, 8, 8, 12, tzinfo=UTC),
        SUFFIX_B,
    )
    middle = _create(
        game_data,
        root,
        1,
        datetime(2026, 8, 8, 9, tzinfo=UTC),
        SUFFIX_C,
    )

    result = discover_backups(root)

    assert result.is_success
    assert [backup.backup_id for backup in result.backups] == [
        newest.backup_id,
        middle.backup_id,
        oldest.backup_id,
    ]
    assert [backup.slot_number for backup in result.backups] == [2, 1, 1]
    assert all(backup.destination.parent == root for backup in result.backups)
    assert result.invalid_entries == ()


def test_discover_backups_uses_id_as_deterministic_tiebreaker(
    tmp_path: Path,
) -> None:
    game_data = tmp_path / "game_data"
    root = tmp_path / "backups"
    created_at = datetime(2026, 8, 8, 12, tzinfo=UTC)
    first = _create(game_data, root, 1, created_at, SUFFIX_A)
    second = _create(game_data, root, 1, created_at, SUFFIX_B)

    result = discover_backups(root)

    assert [backup.backup_id for backup in result.backups] == [
        second.backup_id,
        first.backup_id,
    ]


def test_discover_backups_reports_invalid_entries_by_basename_only(
    tmp_path: Path,
) -> None:
    game_data = tmp_path / "game_data"
    root = tmp_path / "backups"
    valid = _create(
        game_data,
        root,
        1,
        datetime(2026, 8, 8, 12, tzinfo=UTC),
        SUFFIX_A,
    )
    (root / "notes.txt").write_text("ignorar", encoding="utf-8")
    (root / "nome-invalido").mkdir()
    missing_manifest = root / f"save_1-20260808T130000Z-{SUFFIX_B}"
    missing_manifest.mkdir()
    corrupt = root / f"save_2-20260808T140000Z-{SUFFIX_C}"
    corrupt.mkdir()
    (corrupt / BACKUP_MANIFEST_FILENAME).write_text("{", encoding="utf-8")
    (root / ".staging-operacao-interrompida").mkdir()
    (root / ".delete-trash-operacao-interrompida").mkdir()

    result = discover_backups(root)

    assert [backup.backup_id for backup in result.backups] == [valid.backup_id]
    assert result.invalid_entries == tuple(
        sorted(
            {
                corrupt.name,
                missing_manifest.name,
                "nome-invalido",
                "notes.txt",
            }
        )
    )
    assert all(str(tmp_path) not in entry for entry in result.invalid_entries)
    assert ".staging-operacao-interrompida" not in result.invalid_entries
    assert ".delete-trash-operacao-interrompida" not in result.invalid_entries


def test_discover_backups_rejects_mismatched_or_traversing_manifest(
    tmp_path: Path,
) -> None:
    game_data = tmp_path / "game_data"
    root = tmp_path / "backups"
    record = _create(
        game_data,
        root,
        1,
        datetime(2026, 8, 8, 12, tzinfo=UTC),
        SUFFIX_A,
    )
    manifest_path = record.destination / BACKUP_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["backup_id"] = f"save_2-20260808T120000Z-{SUFFIX_B}"
    manifest["files"][0]["relative_path"] = "../outside.tres"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = discover_backups(root)

    assert result.backups == ()
    assert result.invalid_entries == (record.backup_id,)


def test_discover_backups_rejects_boolean_schema_version(tmp_path: Path) -> None:
    game_data = tmp_path / "game_data"
    root = tmp_path / "backups"
    record = _create(
        game_data,
        root,
        1,
        datetime(2026, 8, 8, 12, tzinfo=UTC),
        SUFFIX_A,
    )
    manifest_path = record.destination / BACKUP_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = discover_backups(root)

    assert result.backups == ()
    assert result.invalid_entries == (record.backup_id,)


@pytest.mark.parametrize("payload_change", ["missing", "extra"])
def test_discover_backups_rejects_payload_structure_mismatch(
    tmp_path: Path, payload_change: str
) -> None:
    game_data = tmp_path / "game_data"
    root = tmp_path / "backups"
    record = _create(
        game_data,
        root,
        1,
        datetime(2026, 8, 8, 12, tzinfo=UTC),
        SUFFIX_A,
    )
    payload = record.destination / "payload"
    if payload_change == "missing":
        (payload / "player_data.tres").unlink()
    else:
        (payload / "extra.tres").write_text("extra", encoding="utf-8")

    result = discover_backups(root)

    assert result.backups == ()
    assert result.invalid_entries == (record.backup_id,)


class _ReparseStatProxy:
    def __init__(self, wrapped) -> None:
        self._wrapped = wrapped
        self.st_file_attributes = (
            getattr(wrapped, "st_file_attributes", 0) | 0x400
        )

    def __getattr__(self, name: str):
        return getattr(self._wrapped, name)


def test_discover_backups_rejects_reparse_payload_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data = tmp_path / "game_data"
    root = tmp_path / "backups"
    record = _create(
        game_data,
        root,
        1,
        datetime(2026, 8, 8, 12, tzinfo=UTC),
        SUFFIX_A,
    )
    target = record.destination / "payload" / "player_data.tres"
    original_lstat = backups_module.os.lstat

    def lstat_with_reparse(path):
        result = original_lstat(path)
        if Path(path) == target:
            return _ReparseStatProxy(result)
        return result

    monkeypatch.setattr(backups_module.os, "lstat", lstat_with_reparse)

    result = discover_backups(root)

    assert result.backups == ()
    assert result.invalid_entries == (record.backup_id,)


def test_discover_backups_rejects_manifest_swapped_after_lstat_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data = tmp_path / "game_data"
    root = tmp_path / "backups"
    record = _create(
        game_data,
        root,
        1,
        datetime(2026, 8, 8, 12, tzinfo=UTC),
        SUFFIX_A,
    )
    external = tmp_path / "external-private.json"
    external.write_text('{"private":"external-private-token"}', encoding="utf-8")
    original_manifest = record.destination / "manifest-original.json"
    original_reader = backups_module._read_manifest_bytes
    swapped = False

    def swap_then_read(path: Path, state):
        nonlocal swapped
        if not swapped:
            swapped = True
            path.rename(original_manifest)
            path.hardlink_to(external)
        return original_reader(path, state)

    def forbid_external_read(*_args, **_kwargs):
        raise AssertionError("conteúdo externo não pode ser lido")

    monkeypatch.setattr(backups_module, "_read_manifest_bytes", swap_then_read)
    monkeypatch.setattr(backups_module.os, "read", forbid_external_read)

    result = discover_backups(root)

    assert result.backups == ()
    assert result.invalid_entries == (record.backup_id,)
    assert "external-private-token" not in result.public_message


@pytest.mark.parametrize("root_kind", ["relative", "file"])
def test_discover_backups_fails_closed_for_invalid_root(
    tmp_path: Path, root_kind: str
) -> None:
    root: Path | str
    if root_kind == "relative":
        root = "backups"
    else:
        root = tmp_path / "backups"
        root.write_text("not a directory", encoding="utf-8")

    result = discover_backups(root)

    assert not result.is_success
    assert result.error_code is BackupErrorCode.DISCOVERY_FAILED
    assert result.backups == ()
    assert str(tmp_path) not in result.public_message


def test_backup_discovery_result_is_immutable(tmp_path: Path) -> None:
    result = discover_backups(tmp_path / "missing")

    with pytest.raises(FrozenInstanceError):
        result.public_message = "alterado"  # type: ignore[misc]
