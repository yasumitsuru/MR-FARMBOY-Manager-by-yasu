"""Extração conservadora de detalhes agregados de slots de save.

Somente dois arquivos, com nomes exatos, sao considerados. O conteúdo é lido
por um único descritor validado antes e depois da leitura, e nenhum valor
opaco do save é mantido nos resultados públicos.
"""

from __future__ import annotations

import os
import stat
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .godot_tres import (
    GodotTresDocument,
    GodotTresParseError,
    GodotTresSectionKind,
    parse_godot_tres_document,
)
from .godot_variant import GodotVariant, GodotVariantKind
from .save_slots import SaveSlotSummary


_TARGET_FILES = ("player_data.tres", "island_main_data.tres")
_REPARSE_POINT_ATTRIBUTE = 0x400
_READ_BLOCK_SIZE = 64 * 1024
MAX_SAVE_DETAIL_FILE_SIZE_BYTES = 8 * 1024 * 1024
_PLAYER_PROPERTIES = frozenset(
    {
        "current_tutorial",
        "gameMode",
        "island_id",
        "highlighted_unlocked",
        "the_endless_unlocked",
        "advancements_data",
    }
)
_PLAYER_ANCHORS = frozenset(
    {"current_tutorial", "gameMode", "island_id"}
)
_CROP_PROPERTIES = frozenset(
    {
        "current_growth_state",
        "is_planted",
        "is_watered",
        "is_fertilized",
        "is_matured",
        "is_harvestable",
        "is_dead",
    }
)


class _StableReadError(Exception):
    """Falha esperada e sanitizada da leitura por descritor estável."""


@dataclass(frozen=True, slots=True)
class _StableReadResult:
    data: bytes
    modified_time: float


@dataclass(frozen=True, slots=True)
class _Win32FileInformation:
    attributes: int
    volume_serial_number: int
    file_index: int
    size: int
    modified_time_ticks: int


if os.name == "nt":
    import ctypes
    import msvcrt
    import ntpath
    from ctypes import wintypes

    class _FileTime(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        ]

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", _FileTime),
            ("ftLastAccessTime", _FileTime),
            ("ftLastWriteTime", _FileTime),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _CREATE_FILE_W = _KERNEL32.CreateFileW
    _CREATE_FILE_W.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    _CREATE_FILE_W.restype = wintypes.HANDLE
    _GET_FILE_INFORMATION_BY_HANDLE = _KERNEL32.GetFileInformationByHandle
    _GET_FILE_INFORMATION_BY_HANDLE.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ByHandleFileInformation),
    ]
    _GET_FILE_INFORMATION_BY_HANDLE.restype = wintypes.BOOL
    _GET_FINAL_PATH_NAME_BY_HANDLE_W = _KERNEL32.GetFinalPathNameByHandleW
    _GET_FINAL_PATH_NAME_BY_HANDLE_W.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    _GET_FINAL_PATH_NAME_BY_HANDLE_W.restype = wintypes.DWORD
    _CLOSE_HANDLE = _KERNEL32.CloseHandle
    _CLOSE_HANDLE.argtypes = [wintypes.HANDLE]
    _CLOSE_HANDLE.restype = wintypes.BOOL

    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _GENERIC_READ = 0x80000000
    _FILE_READ_ATTRIBUTES = 0x0080
    _FILE_SHARE_READ = 0x00000001
    _OPEN_EXISTING = 3
    _FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000


@dataclass(frozen=True, slots=True)
class PlayerProgressDetails:
    tutorial_stage: int | None
    game_mode_code: int | None
    island_id: int | None
    highlighted_unlock_count: int | None
    endless_unlock_count: int | None
    advancement_group_count: int | None


@dataclass(frozen=True, slots=True)
class CropProgressDetails:
    record_count: int
    planted_count: int
    watered_count: int
    fertilized_count: int
    matured_count: int
    harvestable_count: int
    dead_count: int
    growth_state_counts: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True, repr=False)
class SaveSlotDetails:
    """Resultado agregado; repr não expõe o caminho guardado no resumo."""

    summary: SaveSlotSummary
    latest_modified_at: datetime | None
    inspected_file_count: int
    total_property_count: int
    failed_files: tuple[str, ...]
    player_progress: PlayerProgressDetails | None
    crop_progress: CropProgressDetails | None

    def __repr__(self) -> str:
        return (
            "SaveSlotDetails("
            f"inspected_file_count={self.inspected_file_count}, "
            f"total_property_count={self.total_property_count}, "
            f"failed_file_count={len(self.failed_files)}, "
            f"has_player_progress={self.player_progress is not None}, "
            f"has_crop_progress={self.crop_progress is not None})"
        )

    __str__ = __repr__


def _is_reparse_or_symlink(stat_result: object) -> bool:
    """Detecta symlinks e reparse points somente pelos dados de lstat/fstat."""
    if stat.S_ISLNK(stat_result.st_mode):
        return True
    attributes = getattr(stat_result, "st_file_attributes", 0)
    return bool(attributes & _REPARSE_POINT_ATTRIBUTE)


def _same_identity(first: object, second: object) -> bool:
    return (first.st_dev, first.st_ino) == (second.st_dev, second.st_ino)


def _same_file_state(first: object, second: object) -> bool:
    return (
        _same_identity(first, second)
        and first.st_size == second.st_size
        and first.st_mtime_ns == second.st_mtime_ns
    )


def _read_descriptor_once(descriptor: int, max_file_size_bytes: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    remaining = max_file_size_bytes + 1
    chunks: list[bytes] = []
    total_read = 0
    while remaining > 0:
        block = os.read(descriptor, min(_READ_BLOCK_SIZE, remaining))
        if not block:
            break
        chunks.append(block)
        block_size = len(block)
        total_read += block_size
        remaining -= block_size
    if total_read > max_file_size_bytes:
        raise _StableReadError
    return b"".join(chunks)


def _read_descriptor_twice(
    descriptor: int, max_file_size_bytes: int
) -> _StableReadResult:
    """Faz duas leituras completas no mesmo fd e rejeita qualquer divergência."""
    initial_stat = os.fstat(descriptor)
    if (
        not stat.S_ISREG(initial_stat.st_mode)
        or initial_stat.st_size > max_file_size_bytes
    ):
        raise _StableReadError

    first = _read_descriptor_once(descriptor, max_file_size_bytes)
    middle_stat = os.fstat(descriptor)
    second = _read_descriptor_once(descriptor, max_file_size_bytes)
    final_stat = os.fstat(descriptor)
    if (
        not _same_file_state(initial_stat, middle_stat)
        or not _same_file_state(initial_stat, final_stat)
        or len(first) != final_stat.st_size
        or len(second) != final_stat.st_size
        or first != second
    ):
        raise _StableReadError
    return _StableReadResult(data=first, modified_time=final_stat.st_mtime)


def _read_stable_file_posix(
    slot_path: Path,
    candidate: Path,
    slot_lstat: object,
    candidate_lstat: object,
    max_file_size_bytes: int,
) -> _StableReadResult:
    """Fallback POSIX: O_NOFOLLOW, estados do fd e duas leituras idênticas."""
    flags = os.O_RDONLY
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None

    try:
        descriptor = os.open(candidate, flags)
        opened_stat = os.fstat(descriptor)
        current_slot_stat = os.lstat(slot_path)
        if (
            not stat.S_ISDIR(current_slot_stat.st_mode)
            or _is_reparse_or_symlink(current_slot_stat)
            or not _same_identity(slot_lstat, current_slot_stat)
        ):
            raise _StableReadError
        if (
            not stat.S_ISREG(opened_stat.st_mode)
            or _is_reparse_or_symlink(opened_stat)
            or not _same_file_state(candidate_lstat, opened_stat)
            or opened_stat.st_size > max_file_size_bytes
        ):
            raise _StableReadError
        result = _read_descriptor_twice(descriptor, max_file_size_bytes)
        if not _same_file_state(opened_stat, os.fstat(descriptor)):
            raise _StableReadError
        return result
    except _StableReadError:
        raise
    except (OSError, OverflowError, ValueError):
        raise _StableReadError from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                if sys.exception() is None:
                    raise _StableReadError from None


def _open_win32_handle(path: Path, access: int, flags: int) -> int:
    handle = _CREATE_FILE_W(
        str(path),
        access,
        _FILE_SHARE_READ,
        None,
        _OPEN_EXISTING,
        flags,
        None,
    )
    if handle == _INVALID_HANDLE_VALUE:
        raise OSError
    return handle


def _close_win32_handle(handle: int) -> None:
    if not _CLOSE_HANDLE(handle):
        raise OSError


def _get_win32_file_information(handle: int) -> _Win32FileInformation:
    raw = _ByHandleFileInformation()
    if not _GET_FILE_INFORMATION_BY_HANDLE(handle, ctypes.byref(raw)):
        raise OSError
    return _Win32FileInformation(
        attributes=raw.dwFileAttributes,
        volume_serial_number=raw.dwVolumeSerialNumber,
        file_index=(raw.nFileIndexHigh << 32) | raw.nFileIndexLow,
        size=(raw.nFileSizeHigh << 32) | raw.nFileSizeLow,
        modified_time_ticks=(
            (raw.ftLastWriteTime.dwHighDateTime << 32)
            | raw.ftLastWriteTime.dwLowDateTime
        ),
    )


def _get_win32_final_path(handle: int) -> str:
    required = _GET_FINAL_PATH_NAME_BY_HANDLE_W(handle, None, 0, 0)
    if required == 0:
        raise OSError
    buffer = ctypes.create_unicode_buffer(required + 1)
    written = _GET_FINAL_PATH_NAME_BY_HANDLE_W(
        handle, buffer, len(buffer), 0
    )
    if written == 0 or written >= len(buffer):
        raise OSError
    return buffer.value


def _normalize_win32_final_path(value: str) -> str:
    if value.casefold().startswith("\\\\?\\unc\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    return ntpath.normpath(value).rstrip("\\/").casefold()


def _same_win32_file_state(
    first: _Win32FileInformation, second: _Win32FileInformation
) -> bool:
    return (
        first.volume_serial_number == second.volume_serial_number
        and first.file_index == second.file_index
        and first.size == second.size
        and first.modified_time_ticks == second.modified_time_ticks
    )


def _read_stable_file_windows(
    slot_path: Path,
    candidate: Path,
    max_file_size_bytes: int,
) -> _StableReadResult:
    """Lê sob handles Win32 que negam compartilhamento WRITE e DELETE."""
    slot_handle: int | None = None
    file_handle: int | None = None
    descriptor: int | None = None
    try:
        slot_handle = _open_win32_handle(
            slot_path,
            _FILE_READ_ATTRIBUTES,
            _FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT,
        )
        slot_info = _get_win32_file_information(slot_handle)
        if (
            slot_info.attributes & _REPARSE_POINT_ATTRIBUTE
            or not slot_info.attributes & _FILE_ATTRIBUTE_DIRECTORY
        ):
            raise _StableReadError
        slot_final_path = _normalize_win32_final_path(
            _get_win32_final_path(slot_handle)
        )

        file_handle = _open_win32_handle(
            candidate,
            _GENERIC_READ,
            _FILE_FLAG_OPEN_REPARSE_POINT | _FILE_FLAG_SEQUENTIAL_SCAN,
        )
        file_info = _get_win32_file_information(file_handle)
        if (
            file_info.attributes & _REPARSE_POINT_ATTRIBUTE
            or file_info.attributes & _FILE_ATTRIBUTE_DIRECTORY
            or file_info.size > max_file_size_bytes
        ):
            raise _StableReadError
        candidate_final_path = _normalize_win32_final_path(
            _get_win32_final_path(file_handle)
        )
        if ntpath.dirname(candidate_final_path) != slot_final_path:
            raise _StableReadError

        descriptor = msvcrt.open_osfhandle(
            file_handle, os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
        file_handle = None  # ownership transferido para o descritor CRT
        opened_stat = os.fstat(descriptor)
        if opened_stat.st_size != file_info.size:
            raise _StableReadError
        result = _read_descriptor_twice(descriptor, max_file_size_bytes)
        final_info = _get_win32_file_information(
            msvcrt.get_osfhandle(descriptor)
        )
        if (
            final_info.attributes & _REPARSE_POINT_ATTRIBUTE
            or not _same_win32_file_state(file_info, final_info)
            or os.fstat(descriptor).st_size != final_info.size
        ):
            raise _StableReadError
        return result
    except _StableReadError:
        raise
    except (OSError, OverflowError, ValueError):
        raise _StableReadError from None
    finally:
        cleanup_failed = False
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                cleanup_failed = True
        elif file_handle is not None:
            try:
                _close_win32_handle(file_handle)
            except OSError:
                cleanup_failed = True
        if slot_handle is not None:
            try:
                _close_win32_handle(slot_handle)
            except OSError:
                cleanup_failed = True
        if cleanup_failed and sys.exception() is None:
            raise _StableReadError from None


def _read_stable_file(
    slot_path: Path,
    candidate: Path,
    slot_lstat: object,
    candidate_lstat: object,
    max_file_size_bytes: int,
) -> _StableReadResult:
    if os.name == "nt":
        return _read_stable_file_windows(
            slot_path, candidate, max_file_size_bytes
        )
    return _read_stable_file_posix(
        slot_path,
        candidate,
        slot_lstat,
        candidate_lstat,
        max_file_size_bytes,
    )


def _integer(variant: GodotVariant | None) -> int | None:
    if variant is None or variant.kind is not GodotVariantKind.INTEGER:
        return None
    value = variant.value
    return value if type(value) is int else None


def _bool(variant: GodotVariant | None) -> bool:
    return bool(variant is not None and variant.kind is GodotVariantKind.BOOL and variant.value is True)


def _collection_count(variant: GodotVariant | None, expected_kind: GodotVariantKind) -> int | None:
    if variant is None or variant.kind is not expected_kind:
        return None
    return len(variant.items if expected_kind is GodotVariantKind.ARRAY else variant.entries)


def _properties_by_name(
    document: GodotTresDocument,
    allowlist: frozenset[str] | set[str],
    section_kinds: frozenset[GodotTresSectionKind] | None = None,
) -> dict[str, GodotVariant]:
    """Retém a primeira ocorrência somente das chaves explicitamente aceitas."""
    properties: dict[str, GodotVariant] = {}
    for section in document.sections:
        if section_kinds is not None and section.kind not in section_kinds:
            continue
        for property_ in section.properties:
            name = property_.name
            if name in allowlist and name not in properties:
                properties[name] = property_.variant
    return properties


def _player_progress(document: GodotTresDocument) -> PlayerProgressDetails:
    props: dict[str, GodotVariant] = {}
    for section in document.sections:
        if section.kind is not GodotTresSectionKind.SUB_RESOURCE:
            continue
        property_names = {property_.name for property_ in section.properties}
        if not _PLAYER_ANCHORS.issubset(property_names):
            continue
        for property_ in section.properties:
            name = property_.name
            if name in _PLAYER_PROPERTIES and name not in props:
                props[name] = property_.variant
        break
    return PlayerProgressDetails(
        tutorial_stage=_integer(props.get("current_tutorial")),
        game_mode_code=_integer(props.get("gameMode")),
        island_id=_integer(props.get("island_id")),
        highlighted_unlock_count=_collection_count(props.get("highlighted_unlocked"), GodotVariantKind.ARRAY),
        endless_unlock_count=_collection_count(props.get("the_endless_unlocked"), GodotVariantKind.ARRAY),
        advancement_group_count=_collection_count(props.get("advancements_data"), GodotVariantKind.DICTIONARY),
    )


def _crop_progress(document: GodotTresDocument) -> CropProgressDetails:
    counts = {name: 0 for name in _CROP_PROPERTIES if name != "current_growth_state"}
    state_counts: dict[int, int] = {}
    record_count = 0
    for section in document.sections:
        if section.kind is not GodotTresSectionKind.SUB_RESOURCE:
            continue
        props = {property_.name: property_.variant for property_ in section.properties if property_.name in _CROP_PROPERTIES}
        state = _integer(props.get("current_growth_state"))
        if state is None:
            continue
        record_count += 1
        state_counts[state] = state_counts.get(state, 0) + 1
        for name in counts:
            if _bool(props.get(name)):
                counts[name] += 1
    return CropProgressDetails(
        record_count=record_count,
        planted_count=counts["is_planted"],
        watered_count=counts["is_watered"],
        fertilized_count=counts["is_fertilized"],
        matured_count=counts["is_matured"],
        harvestable_count=counts["is_harvestable"],
        dead_count=counts["is_dead"],
        growth_state_counts=tuple(sorted(state_counts.items())),
    )


def inspect_save_slot(
    summary: SaveSlotSummary,
    max_file_size_bytes: int = MAX_SAVE_DETAIL_FILE_SIZE_BYTES,
) -> SaveSlotDetails:
    """Inspeciona as métricas allowlist de um slot, sem alterar o original."""
    if (
        type(max_file_size_bytes) is not int
        or max_file_size_bytes < 0
        or max_file_size_bytes > MAX_SAVE_DETAIL_FILE_SIZE_BYTES
    ):
        raise ValueError("limite de tamanho inválido")

    inspected_count = 0
    total_property_count = 0
    failed: list[str] = []
    latest_modified_at: datetime | None = None
    player: PlayerProgressDetails | None = None
    crops: CropProgressDetails | None = None

    try:
        slot_stat = os.lstat(summary.slot.path)
        slot_is_unsafe = (
            _is_reparse_or_symlink(slot_stat)
            or not stat.S_ISDIR(slot_stat.st_mode)
        )
    except OSError:
        slot_is_unsafe = True

    for filename in _TARGET_FILES:
        if slot_is_unsafe:
            failed.append(filename)
            continue
        candidate = summary.slot.path / filename
        try:
            stat_result = os.lstat(candidate)
        except FileNotFoundError:
            continue
        except OSError:
            failed.append(filename)
            continue

        if (
            _is_reparse_or_symlink(stat_result)
            or not stat.S_ISREG(stat_result.st_mode)
            or stat_result.st_size > max_file_size_bytes
        ):
            failed.append(filename)
            continue

        try:
            read_result = _read_stable_file(
                summary.slot.path,
                candidate,
                slot_stat,
                stat_result,
                max_file_size_bytes,
            )
            document = parse_godot_tres_document(read_result.data)
        except (_StableReadError, GodotTresParseError):
            failed.append(filename)
            continue

        try:
            modified_at = datetime.fromtimestamp(
                read_result.modified_time, tz=timezone.utc
            )
        except (OSError, OverflowError, ValueError):
            failed.append(filename)
            continue

        if filename == "player_data.tres":
            file_player = _player_progress(document)
            file_crops = None
        else:
            file_player = None
            file_crops = _crop_progress(document)

        inspected_count += 1
        total_property_count += document.total_property_count
        if latest_modified_at is None or modified_at > latest_modified_at:
            latest_modified_at = modified_at
        if file_player is not None:
            player = file_player
        if file_crops is not None:
            crops = file_crops

    return SaveSlotDetails(
        summary=summary,
        latest_modified_at=latest_modified_at,
        inspected_file_count=inspected_count,
        total_property_count=total_property_count,
        failed_files=tuple(failed),
        player_progress=player,
        crop_progress=crops,
    )


__all__ = [
    "MAX_SAVE_DETAIL_FILE_SIZE_BYTES",
    "PlayerProgressDetails",
    "CropProgressDetails",
    "SaveSlotDetails",
    "inspect_save_slot",
]
