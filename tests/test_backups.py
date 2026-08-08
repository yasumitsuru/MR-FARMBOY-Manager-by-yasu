import json
import os
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from mr_farmboy_manager.backups import (
    BACKUP_MANIFEST_FILENAME,
    BACKUP_PAYLOAD_DIRECTORY,
    BackupErrorCode,
    BackupValidationError,
    create_backup,
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


def _create_source_slot(tmp_path: Path, number: int = 3) -> tuple[Path, SaveSlot]:
    game_data = tmp_path / "game_data"
    source = game_data / f"save_{number}"
    (source / "nested").mkdir(parents=True)
    (source / "player_data.tres").write_bytes(b"player-data\x00\xff")
    (source / "nested" / "island_main_data.tres").write_text(
        "fazenda sintetica", encoding="utf-8"
    )
    return game_data, SaveSlot(number=number, path=source)


def test_create_backup_copies_slot_and_publishes_valid_manifest(
    tmp_path: Path,
) -> None:
    game_data, slot = _create_source_slot(tmp_path)
    backup_root = tmp_path / "manager-data" / "backups"
    created_at = datetime(2026, 8, 8, 13, 45, 12, tzinfo=UTC)

    result = create_backup(
        slot,
        game_data,
        backup_root,
        created_at=created_at,
        suffix=SUFFIX_A,
    )

    assert result.is_success
    assert result.error_code is None
    assert result.backup is not None
    assert result.backup.backup_id == f"save_3-20260808T134512Z-{SUFFIX_A}"
    assert result.backup.slot_number == 3
    assert result.backup.created_at_utc == created_at
    assert result.backup.file_count == 2
    assert result.backup.total_size_bytes == len(b"player-data\x00\xff") + len(
        "fazenda sintetica".encode()
    )

    destination = result.backup.destination
    payload = destination / BACKUP_PAYLOAD_DIRECTORY
    assert (payload / "player_data.tres").read_bytes() == b"player-data\x00\xff"
    assert (payload / "nested" / "island_main_data.tres").read_text(
        encoding="utf-8"
    ) == "fazenda sintetica"

    manifest_path = destination / BACKUP_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["backup_id"] == result.backup.backup_id
    assert manifest["slot_number"] == 3
    assert manifest["created_at_utc"] == "2026-08-08T13:45:12Z"
    assert manifest["file_count"] == 2
    assert manifest["total_size_bytes"] == result.backup.total_size_bytes
    assert [entry["relative_path"] for entry in manifest["files"]] == [
        "nested/island_main_data.tres",
        "player_data.tres",
    ]
    assert all(len(entry["sha256"]) == 64 for entry in manifest["files"])
    assert str(slot.path) not in manifest_path.read_text(encoding="utf-8")
    assert not any(path.name.startswith(".staging-") for path in backup_root.iterdir())


@pytest.mark.parametrize("source_kind", ["missing", "file"])
def test_create_backup_rejects_missing_or_non_directory_source(
    tmp_path: Path, source_kind: str
) -> None:
    game_data = tmp_path / "game_data"
    source = game_data / "save_3"
    game_data.mkdir()
    if source_kind == "file":
        source.write_text("not a slot", encoding="utf-8")

    result = create_backup(
        SaveSlot(3, source),
        game_data,
        tmp_path / "backups",
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        suffix=SUFFIX_A,
    )

    assert not result.is_success
    assert result.error_code in {
        BackupErrorCode.SOURCE_NOT_FOUND,
        BackupErrorCode.SOURCE_NOT_DIRECTORY,
    }
    assert result.backup is None
    assert not (tmp_path / "backups").exists()
    assert str(tmp_path) not in result.public_message


def test_create_backup_never_overwrites_an_existing_backup(tmp_path: Path) -> None:
    game_data, slot = _create_source_slot(tmp_path)
    backup_root = tmp_path / "backups"
    kwargs = {
        "created_at": datetime(2026, 8, 8, tzinfo=UTC),
        "suffix": SUFFIX_A,
    }

    first = create_backup(slot, game_data, backup_root, **kwargs)
    assert first.is_success and first.backup is not None
    manifest_before = (first.backup.destination / BACKUP_MANIFEST_FILENAME).read_bytes()
    payload_before = (
        first.backup.destination / BACKUP_PAYLOAD_DIRECTORY / "player_data.tres"
    ).read_bytes()

    (slot.path / "player_data.tres").write_bytes(b"changed source")
    second = create_backup(slot, game_data, backup_root, **kwargs)

    assert not second.is_success
    assert second.error_code is BackupErrorCode.BACKUP_ALREADY_EXISTS
    assert (first.backup.destination / BACKUP_MANIFEST_FILENAME).read_bytes() == manifest_before
    assert (
        first.backup.destination / BACKUP_PAYLOAD_DIRECTORY / "player_data.tres"
    ).read_bytes() == payload_before


def test_create_backup_never_replaces_preexisting_empty_destination(
    tmp_path: Path,
) -> None:
    game_data, slot = _create_source_slot(tmp_path)
    backup_root = tmp_path / "backups"
    backup_id = f"save_3-20260808T000000Z-{SUFFIX_A}"
    destination = backup_root / backup_id
    destination.mkdir(parents=True)

    result = create_backup(
        slot,
        game_data,
        backup_root,
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        suffix=SUFFIX_A,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.BACKUP_ALREADY_EXISTS
    assert destination.is_dir()
    assert list(destination.iterdir()) == []
    assert not any(path.name.startswith(".staging-") for path in backup_root.iterdir())


def _symlink_directory_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink de diretório indisponível: {error}")


class _ReparseStatProxy:
    def __init__(self, wrapped) -> None:
        self._wrapped = wrapped
        self.st_file_attributes = (
            getattr(wrapped, "st_file_attributes", 0) | 0x400
        )

    def __getattr__(self, name: str):
        return getattr(self._wrapped, name)


@pytest.mark.parametrize("reparse_target", ["active", "backup"])
def test_create_backup_rejects_mocked_reparse_root_attribute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reparse_target: str,
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data, slot = _create_source_slot(tmp_path)
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    target = game_data if reparse_target == "active" else backup_root
    original_lstat = backups_module.os.lstat

    def lstat_with_reparse(path):
        result = original_lstat(path)
        if Path(path) == target:
            return _ReparseStatProxy(result)
        return result

    monkeypatch.setattr(backups_module.os, "lstat", lstat_with_reparse)

    result = create_backup(
        slot,
        game_data,
        backup_root,
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        suffix=SUFFIX_A,
    )

    expected = (
        BackupErrorCode.UNSAFE_SOURCE_ENTRY
        if reparse_target == "active"
        else BackupErrorCode.BACKUP_ROOT_UNAVAILABLE
    )
    assert not result.is_success
    assert result.error_code is expected
    assert list(backup_root.iterdir()) == []


def test_create_backup_rejects_static_backup_root_link(tmp_path: Path) -> None:
    game_data, slot = _create_source_slot(tmp_path)
    external_root = tmp_path / "external"
    external_root.mkdir()
    linked_root = tmp_path / "linked-backups"
    _symlink_directory_or_skip(linked_root, external_root)

    result = create_backup(
        slot,
        game_data,
        linked_root,
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        suffix=SUFFIX_A,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.BACKUP_ROOT_UNAVAILABLE
    assert list(external_root.iterdir()) == []


def test_create_backup_rejects_static_active_root_link(tmp_path: Path) -> None:
    actual_root, actual_slot = _create_source_slot(tmp_path)
    linked_root = tmp_path / "linked-game-data"
    _symlink_directory_or_skip(linked_root, actual_root)
    linked_slot = SaveSlot(actual_slot.number, linked_root / actual_slot.path.name)

    result = create_backup(
        linked_slot,
        linked_root,
        tmp_path / "backups",
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        suffix=SUFFIX_A,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.UNSAFE_SOURCE_ENTRY
    assert not (tmp_path / "backups").exists()


def test_create_backup_cleans_staging_after_copy_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data, slot = _create_source_slot(tmp_path)
    backup_root = tmp_path / "backups"
    source_before = {
        path.relative_to(slot.path): path.read_bytes()
        for path in slot.path.rglob("*")
        if path.is_file()
    }

    def fail_copy(*args, **kwargs):
        raise PermissionError("private path token")

    monkeypatch.setattr(backups_module, "_copy_regular_file", fail_copy)

    result = create_backup(
        slot,
        game_data,
        backup_root,
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        suffix=SUFFIX_A,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.COPY_FAILED
    assert result.backup is None
    assert "private path token" not in result.public_message
    assert list(backup_root.iterdir()) == []
    assert source_before == {
        path.relative_to(slot.path): path.read_bytes()
        for path in slot.path.rglob("*")
        if path.is_file()
    }


def test_create_backup_never_reads_source_through_path_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_data, slot = _create_source_slot(tmp_path)
    backup_root = tmp_path / "backups"
    source_files = {path.resolve() for path in slot.path.rglob("*") if path.is_file()}
    original_open = Path.open

    def guarded_open(path: Path, *args, **kwargs):
        if path.resolve() in source_files:
            raise AssertionError("source pathname read")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    result = create_backup(
        slot,
        game_data,
        backup_root,
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        suffix=SUFFIX_A,
    )

    assert result.is_success


def test_create_backup_rejects_source_change_during_copy_and_cleans_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data, slot = _create_source_slot(tmp_path)
    backup_root = tmp_path / "backups"
    original_copy = backups_module._copy_regular_file

    def mutate_after_copy(
        source: Path, destination: Path, expected_state, backup_root_chain
    ):
        copied = original_copy(
            source,
            destination,
            expected_state,
            backup_root_chain,
        )
        source.write_bytes(source.read_bytes() + b"changed")
        return copied

    monkeypatch.setattr(backups_module, "_copy_regular_file", mutate_after_copy)

    result = create_backup(
        slot,
        game_data,
        backup_root,
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        suffix=SUFFIX_A,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.SOURCE_CHANGED
    assert list(backup_root.iterdir()) == []


def test_create_backup_does_not_read_link_swapped_after_lstat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    probe_target = tmp_path / "probe-target"
    probe_target.write_bytes(b"probe")
    probe_link = tmp_path / "probe-link"
    try:
        probe_link.symlink_to(probe_target)
    except OSError as error:
        pytest.skip(f"symlink de arquivo indisponível: {error}")
    probe_link.unlink()

    game_data, slot = _create_source_slot(tmp_path)
    backup_root = tmp_path / "backups"
    external = tmp_path / "external-private.bin"
    external.write_bytes(b"external-private-token")
    original_open = backups_module._open_source_descriptor
    swapped = False

    def swap_then_open(source: Path, expected_state):
        nonlocal swapped
        if not swapped:
            swapped = True
            original = source.with_name(f"{source.name}.original")
            source.rename(original)
            source.symlink_to(external)
        return original_open(source, expected_state)

    monkeypatch.setattr(backups_module, "_open_source_descriptor", swap_then_open)

    result = create_backup(
        slot,
        game_data,
        backup_root,
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        suffix=SUFFIX_A,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.SOURCE_CHANGED
    copied_bytes = b"".join(
        path.read_bytes()
        for path in backup_root.rglob("*")
        if path.is_file() and not path.is_symlink()
    )
    assert b"external-private-token" not in copied_bytes
    assert list(backup_root.iterdir()) == []


@pytest.mark.skipif(os.name == "nt", reason="teste específico de openat POSIX")
def test_posix_source_ancestor_swap_is_rejected_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data, slot = _create_source_slot(tmp_path)
    external_game_data = tmp_path / "external-game-data"
    external_slot = external_game_data / "save_3"
    external_slot.mkdir(parents=True)
    (external_slot / "player_data.tres").write_bytes(b"external-private-token")
    original_root = tmp_path / "game-data-original"
    original_open = backups_module._open_source_descriptor_posix
    swapped = False

    def swap_ancestor_then_open(source: Path, expected_state):
        nonlocal swapped
        if not swapped:
            swapped = True
            game_data.rename(original_root)
            game_data.symlink_to(external_game_data, target_is_directory=True)
        return original_open(source, expected_state)

    monkeypatch.setattr(
        backups_module,
        "_open_source_descriptor_posix",
        swap_ancestor_then_open,
    )

    result = create_backup(
        slot,
        game_data,
        tmp_path / "backups",
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        suffix=SUFFIX_A,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.SOURCE_CHANGED
    assert list((tmp_path / "backups").iterdir()) == []


@pytest.mark.skipif(os.name == "nt", reason="teste específico de ancestor POSIX")
def test_posix_backup_ancestor_swap_is_rejected_before_staging_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data, slot = _create_source_slot(tmp_path)
    manager_root = tmp_path / "manager"
    backup_root = manager_root / "backups"
    external_manager = tmp_path / "external-manager"
    external_manager.mkdir()
    original_manager = tmp_path / "manager-original"
    original_assert = backups_module._assert_directory_chain
    swapped = False

    def swap_ancestor_then_assert(chain):
        nonlocal swapped
        if not swapped and backup_root.exists():
            swapped = True
            manager_root.rename(original_manager)
            manager_root.symlink_to(external_manager, target_is_directory=True)
        return original_assert(chain)

    monkeypatch.setattr(
        backups_module,
        "_assert_directory_chain",
        swap_ancestor_then_assert,
    )

    result = create_backup(
        slot,
        game_data,
        backup_root,
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        suffix=SUFFIX_A,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.BACKUP_ROOT_UNAVAILABLE
    assert list(external_manager.iterdir()) == []


@pytest.mark.skipif(os.name == "nt", reason="teste específico de symlink POSIX")
def test_posix_source_swap_immediately_after_resolution_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data, slot = _create_source_slot(tmp_path)
    external_game_data = tmp_path / "external-game-data"
    external_slot = external_game_data / "save_3"
    external_slot.mkdir(parents=True)
    (external_slot / "player_data.tres").write_bytes(b"external-private-token")
    original_game_data = tmp_path / "game-data-original"
    original_resolve = backups_module.resolve_backup_destination

    def resolve_then_swap(*args, **kwargs):
        location = original_resolve(*args, **kwargs)
        game_data.rename(original_game_data)
        game_data.symlink_to(external_game_data, target_is_directory=True)
        return location

    monkeypatch.setattr(
        backups_module,
        "resolve_backup_destination",
        resolve_then_swap,
    )

    result = create_backup(
        slot,
        game_data,
        tmp_path / "backups",
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        suffix=SUFFIX_A,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.UNSAFE_SOURCE_ENTRY
    assert not (tmp_path / "backups").exists()


@pytest.mark.skipif(os.name == "nt", reason="teste específico de symlink POSIX")
def test_posix_backup_swap_immediately_after_resolution_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data, slot = _create_source_slot(tmp_path)
    manager_root = tmp_path / "manager"
    backup_root = manager_root / "backups"
    manager_root.mkdir()
    external_manager = tmp_path / "external-manager"
    external_manager.mkdir()
    original_manager = tmp_path / "manager-original"
    original_resolve = backups_module.resolve_backup_destination

    def resolve_then_swap(*args, **kwargs):
        location = original_resolve(*args, **kwargs)
        manager_root.rename(original_manager)
        manager_root.symlink_to(external_manager, target_is_directory=True)
        return location

    monkeypatch.setattr(
        backups_module,
        "resolve_backup_destination",
        resolve_then_swap,
    )

    result = create_backup(
        slot,
        game_data,
        backup_root,
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        suffix=SUFFIX_A,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.BACKUP_ROOT_UNAVAILABLE
    assert list(external_manager.iterdir()) == []


def test_create_backup_revalidates_payload_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mr_farmboy_manager.backups as backups_module

    game_data, slot = _create_source_slot(tmp_path)
    backup_root = tmp_path / "backups"
    original_validate = backups_module._validate_staged_backup

    def corrupt_then_validate(staging: Path, manifest) -> None:
        (staging / BACKUP_PAYLOAD_DIRECTORY / "player_data.tres").write_bytes(
            b"corrupt"
        )
        original_validate(staging, manifest)

    monkeypatch.setattr(backups_module, "_validate_staged_backup", corrupt_then_validate)

    result = create_backup(
        slot,
        game_data,
        backup_root,
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        suffix=SUFFIX_A,
    )

    assert not result.is_success
    assert result.error_code is BackupErrorCode.VALIDATION_FAILED
    assert list(backup_root.iterdir()) == []
