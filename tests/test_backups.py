from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from mr_farmboy_manager.backups import (
    BackupErrorCode,
    BackupValidationError,
    create_backup_id,
    resolve_backup_destination,
)
from mr_farmboy_manager.save_slots import SaveSlot


SUFFIX_A = "deadbeefdeadbeefdeadbeefdeadbeef"
SUFFIX_B = "cafebabecafebabecafebabecafebabe"


def test_create_backup_id_is_deterministic_and_portable() -> None:
    created_at = datetime(2026, 8, 8, 13, 45, 12, tzinfo=UTC)

    backup_id = create_backup_id(7, created_at=created_at, suffix=SUFFIX_A)

    assert backup_id == f"save_7-20260808T134512Z-{SUFFIX_A}"
    assert set(backup_id).isdisjoint('\\/:*?"<>|')
    assert len(backup_id) < 255


def test_create_backup_id_is_unique_when_suffix_changes() -> None:
    created_at = datetime(2026, 8, 8, 13, 45, 12, tzinfo=UTC)

    first = create_backup_id(7, created_at=created_at, suffix=SUFFIX_A)
    second = create_backup_id(7, created_at=created_at, suffix=SUFFIX_B)

    assert first != second


@pytest.mark.parametrize(
    ("slot_number", "created_at", "suffix"),
    [
        (0, datetime(2026, 8, 8, tzinfo=UTC), SUFFIX_A),
        (1_000_000, datetime(2026, 8, 8, tzinfo=UTC), SUFFIX_A),
        (1, datetime(2026, 8, 8), SUFFIX_A),
        (1, datetime(2026, 8, 8, tzinfo=timezone(timedelta(hours=-3))), SUFFIX_A),
        (1, datetime(2026, 8, 8, tzinfo=UTC), "not-hex"),
        (1, datetime(2026, 8, 8, tzinfo=UTC), ""),
        (1, datetime(2026, 8, 8, tzinfo=UTC), "a" * 31),
        (1, datetime(2026, 8, 8, tzinfo=UTC), "a" * 33),
        (1, datetime(2026, 8, 8, tzinfo=UTC), "A" * 32),
    ],
)
def test_create_backup_id_rejects_invalid_components(
    slot_number: int, created_at: datetime, suffix: str
) -> None:
    with pytest.raises(BackupValidationError) as raised:
        create_backup_id(slot_number, created_at=created_at, suffix=suffix)

    assert raised.value.code in {
        BackupErrorCode.INVALID_SLOT,
        BackupErrorCode.INVALID_TIMESTAMP,
        BackupErrorCode.INVALID_SUFFIX,
    }
    assert "\\" not in raised.value.public_message
    assert ":" not in raised.value.public_message


def test_create_backup_id_rejects_non_datetime_timestamp() -> None:
    with pytest.raises(BackupValidationError) as raised:
        create_backup_id(1, created_at=object(), suffix=SUFFIX_A)  # type: ignore[arg-type]

    assert raised.value.code is BackupErrorCode.INVALID_TIMESTAMP


def test_resolve_backup_destination_returns_safe_location(tmp_path: Path) -> None:
    game_data = tmp_path / "game_data"
    source = game_data / "save_3"
    slot = SaveSlot(number=3, path=source)
    root = tmp_path / "backups"
    backup_id = f"save_3-20260808T134512Z-{SUFFIX_A}"

    location = resolve_backup_destination(slot, game_data, root, backup_id)

    assert location.backup_id == backup_id
    assert location.slot == slot
    assert location.created_at_utc == datetime(2026, 8, 8, 13, 45, 12, tzinfo=UTC)
    assert location.destination == (root / backup_id).resolve(strict=False)
    assert not root.exists()


@pytest.mark.parametrize(
    "backup_id",
    ["../escape", f"save_3-20260808T134512Z-{SUFFIX_A}/child"],
)
def test_resolve_backup_destination_rejects_traversal_or_invalid_id(
    tmp_path: Path, backup_id: str
) -> None:
    slot = SaveSlot(number=3, path=tmp_path / "game_data" / "save_3")

    with pytest.raises(BackupValidationError) as raised:
        resolve_backup_destination(
            slot, tmp_path / "game_data", tmp_path / "backups", backup_id
        )

    assert raised.value.code is BackupErrorCode.INVALID_BACKUP_ID


@pytest.mark.parametrize("root_name", ["game_data", "save_3/nested_backups"])
def test_resolve_backup_destination_rejects_root_equal_or_inside_active_game_data(
    tmp_path: Path, root_name: str
) -> None:
    game_data = tmp_path / "game_data"
    slot = SaveSlot(number=3, path=game_data / "save_3")

    with pytest.raises(BackupValidationError) as raised:
        resolve_backup_destination(
            slot,
            game_data,
            game_data / root_name if root_name != "game_data" else game_data,
            f"save_3-20260808T134512Z-{SUFFIX_A}",
        )

    assert raised.value.code is BackupErrorCode.UNSAFE_BACKUP_ROOT


def test_resolve_backup_destination_rejects_source_inside_backup_root(tmp_path: Path) -> None:
    root = tmp_path / "backups"
    slot = SaveSlot(number=3, path=root / "game_data" / "save_3")

    with pytest.raises(BackupValidationError) as raised:
        resolve_backup_destination(
            slot,
            root / "game_data",
            root,
            f"save_3-20260808T134512Z-{SUFFIX_A}",
        )

    assert raised.value.code is BackupErrorCode.SOURCE_INSIDE_BACKUP_ROOT


@pytest.mark.parametrize(
    "slot",
    [
        lambda tmp_path: SaveSlot(number=3, path=tmp_path / "game_data" / "save_4"),
        lambda tmp_path: SaveSlot(number=3, path=tmp_path / "game_data" / "other"),
    ],
)
def test_resolve_backup_destination_rejects_incoherent_slot_path(tmp_path: Path, slot) -> None:
    with pytest.raises(BackupValidationError) as raised:
        resolve_backup_destination(
            slot(tmp_path),
            tmp_path / "game_data",
            tmp_path / "backups",
            f"save_3-20260808T134512Z-{SUFFIX_A}",
        )

    assert raised.value.code is BackupErrorCode.INCOHERENT_SOURCE


def test_resolve_backup_destination_rejects_source_outside_active_root(
    tmp_path: Path,
) -> None:
    slot = SaveSlot(number=3, path=tmp_path / "rogue_game_data" / "save_3")

    with pytest.raises(BackupValidationError) as raised:
        resolve_backup_destination(
            slot,
            tmp_path / "game_data",
            tmp_path / "backups",
            f"save_3-20260808T134512Z-{SUFFIX_A}",
        )

    assert raised.value.code is BackupErrorCode.INCOHERENT_SOURCE


@pytest.mark.parametrize("backup_root", ["", "   ", "backups"])
def test_resolve_backup_destination_rejects_empty_or_relative_backup_root(
    tmp_path: Path, backup_root: str
) -> None:
    game_data = tmp_path / "game_data"
    slot = SaveSlot(number=3, path=game_data / "save_3")

    with pytest.raises(BackupValidationError) as raised:
        resolve_backup_destination(
            slot,
            game_data,
            backup_root,
            f"save_3-20260808T134512Z-{SUFFIX_A}",
        )

    assert raised.value.code is BackupErrorCode.UNSAFE_BACKUP_ROOT


def test_resolve_backup_destination_rejects_relative_source(tmp_path: Path) -> None:
    slot = SaveSlot(number=3, path=Path("game_data/save_3"))

    with pytest.raises(BackupValidationError) as raised:
        resolve_backup_destination(
            slot,
            tmp_path / "game_data",
            tmp_path / "backups",
            f"save_3-20260808T134512Z-{SUFFIX_A}",
        )

    assert raised.value.code is BackupErrorCode.INCOHERENT_SOURCE


def test_resolve_backup_destination_rejects_relative_active_root(
    tmp_path: Path,
) -> None:
    slot = SaveSlot(number=3, path=tmp_path / "game_data" / "save_3")

    with pytest.raises(BackupValidationError) as raised:
        resolve_backup_destination(
            slot,
            "game_data",
            tmp_path / "backups",
            f"save_3-20260808T134512Z-{SUFFIX_A}",
        )

    assert raised.value.code is BackupErrorCode.INCOHERENT_SOURCE
