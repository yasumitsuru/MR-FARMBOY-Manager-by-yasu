"""Testes de detalhes de domínio, exclusivamente com saves sintéticos."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import replace
from datetime import timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from mr_farmboy_manager.save_details import inspect_save_slot
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary


HEADER = '[gd_resource type="Resource" format=3]\n'


def summary_for(slot_path):
    return SaveSlotSummary(slot=SaveSlot(number=7, path=slot_path), tres_file_count=2)


def write_tres(path, body):
    path.write_text(HEADER + body, encoding="utf-8")


def test_happy_path_extracts_only_allowlisted_aggregate_details(tmp_path):
    player = tmp_path / "player_data.tres"
    crops = tmp_path / "island_main_data.tres"
    write_tres(
        player,
        """[sub_resource type="Resource" id="player-real-shape"]
current_tutorial = 4
gameMode = 2
island_id = 9
highlighted_unlocked = ["a", "b"]
the_endless_unlocked = [1]
advancements_data = {"private": 1, "another": 2}
inventory = {"secret": 999}
""",
    )
    write_tres(
        crops,
        """[sub_resource type="Resource" id="first"]
current_growth_state = 3
is_planted = true
is_watered = true
is_fertilized = false
is_matured = false
is_harvestable = false
is_dead = false
unknown_private_value = "do not expose"

[sub_resource type="Resource" id="second"]
current_growth_state = 1
is_planted = true
is_watered = false
is_fertilized = true
is_matured = true
is_harvestable = true
is_dead = false
""",
    )

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.summary == summary_for(tmp_path)
    assert result.inspected_file_count == 2
    assert result.total_property_count == 22
    assert result.failed_files == ()
    assert result.player_progress.tutorial_stage == 4
    assert result.player_progress.game_mode_code == 2
    assert result.player_progress.island_id == 9
    assert result.player_progress.highlighted_unlock_count == 2
    assert result.player_progress.endless_unlock_count == 1
    assert result.player_progress.advancement_group_count == 2
    assert result.crop_progress.record_count == 2
    assert result.crop_progress.planted_count == 2
    assert result.crop_progress.watered_count == 1
    assert result.crop_progress.fertilized_count == 1
    assert result.crop_progress.matured_count == 1
    assert result.crop_progress.harvestable_count == 1
    assert result.crop_progress.dead_count == 0
    assert result.crop_progress.growth_state_counts == ((1, 1), (3, 1))
    assert result.latest_modified_at is not None
    assert result.latest_modified_at.tzinfo is timezone.utc
    rendered = repr(result)
    for private in ("inventory", "secret", "unknown_private_value", "do not expose"):
        assert private not in rendered


def test_missing_target_files_are_not_failures(tmp_path):
    result = inspect_save_slot(summary_for(tmp_path))

    assert result.inspected_file_count == 0
    assert result.total_property_count == 0
    assert result.failed_files == ()
    assert result.player_progress is None
    assert result.crop_progress is None
    assert result.latest_modified_at is None


def test_invalid_file_is_recorded_by_sanitized_relative_name_only(tmp_path):
    (tmp_path / "player_data.tres").write_text("not a tres", encoding="utf-8")

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.inspected_file_count == 0
    assert result.failed_files == ("player_data.tres",)
    assert str(tmp_path) not in repr(result)
    assert "not a tres" not in repr(result)


def test_oversized_file_is_rejected_before_open_or_read(tmp_path, monkeypatch):
    import mr_farmboy_manager.save_details as module
    monkeypatch.setattr(module, "os", os, raising=False)

    target = tmp_path / "player_data.tres"
    target.write_bytes(b"x" * 33)

    def should_not_open(path, flags):
        raise AssertionError("oversized file must not be opened")

    monkeypatch.setattr(module.os, "open", should_not_open)
    result = inspect_save_slot(summary_for(tmp_path), max_file_size_bytes=32)

    assert result.inspected_file_count == 0
    assert result.failed_files == ("player_data.tres",)


def test_wrong_types_and_unknown_properties_are_ignored_conservatively(tmp_path):
    write_tres(
        tmp_path / "player_data.tres",
        """[sub_resource type="Resource" id="player-real-shape"]
current_tutorial = "wrong"
gameMode = true
island_id = 8
highlighted_unlocked = {"wrong": 1}
the_endless_unlocked = [1, 2]
advancements_data = []
unknown = "opaque"
""",
    )
    write_tres(
        tmp_path / "island_main_data.tres",
        """[sub_resource type="Resource" id="one"]
current_growth_state = "wrong"
is_planted = 1
is_watered = true
is_fertilized = true
is_matured = true
is_harvestable = true
is_dead = true
secret_food = 44

[sub_resource type="Resource" id="two"]
is_planted = true
""",
    )

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.player_progress.tutorial_stage is None
    assert result.player_progress.game_mode_code is None
    assert result.player_progress.island_id == 8
    assert result.player_progress.highlighted_unlock_count is None
    assert result.player_progress.endless_unlock_count == 2
    assert result.player_progress.advancement_group_count is None
    assert result.crop_progress.record_count == 0
    assert result.crop_progress.planted_count == 0
    assert result.crop_progress.watered_count == 0
    assert result.crop_progress.dead_count == 0
    assert result.crop_progress.growth_state_counts == ()
    assert "secret_food" not in repr(result)


def test_original_bytes_hash_and_mtime_remain_unchanged(tmp_path):
    target = tmp_path / "player_data.tres"
    write_tres(target, "[resource]\ncurrent_tutorial = 1\n")
    before = target.read_bytes()
    before_hash = hashlib.sha256(before).hexdigest()
    before_mtime = target.stat().st_mtime_ns

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.inspected_file_count == 1
    assert target.read_bytes() == before
    assert hashlib.sha256(target.read_bytes()).hexdigest() == before_hash
    assert target.stat().st_mtime_ns == before_mtime


def test_growth_states_are_aggregated_and_sorted(tmp_path):
    write_tres(
        tmp_path / "island_main_data.tres",
        """[sub_resource type="Resource" id="a"]
current_growth_state = 8
[sub_resource type="Resource" id="b"]
current_growth_state = -1
[sub_resource type="Resource" id="c"]
current_growth_state = 8
""",
    )

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.crop_progress.record_count == 3
    assert result.crop_progress.growth_state_counts == ((-1, 1), (8, 2))


def test_only_exact_top_level_target_names_are_considered(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    write_tres(nested / "player_data.tres", "[resource]\ncurrent_tutorial = 99\n")
    write_tres(tmp_path / "player_data.tres.bak", "[resource]\ncurrent_tutorial = 88\n")

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.inspected_file_count == 0
    assert result.player_progress is None


class _StatProxy:
    def __init__(self, wrapped, *, mode=None, reparse=False):
        self._wrapped = wrapped
        self.st_mode = wrapped.st_mode if mode is None else mode
        self.st_file_attributes = getattr(wrapped, "st_file_attributes", 0)
        if reparse:
            self.st_file_attributes |= 0x400

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


def test_reparse_slot_directory_is_rejected_without_opening_targets(tmp_path, monkeypatch):
    import mr_farmboy_manager.save_details as module
    monkeypatch.setattr(module, "os", os, raising=False)

    slot = tmp_path / "save_7"
    slot.mkdir()
    write_tres(slot / "player_data.tres", "[resource]\ncurrent_tutorial = 1\n")
    real_lstat = os.lstat

    def marked_lstat(path):
        result = real_lstat(path)
        return _StatProxy(result, reparse=Path(path) == slot)

    monkeypatch.setattr(module.os, "lstat", marked_lstat)
    monkeypatch.setattr(
        module.os,
        "open",
        lambda path, flags: (_ for _ in ()).throw(AssertionError("must not open")),
    )

    result = inspect_save_slot(summary_for(slot))

    assert result.inspected_file_count == 0
    assert result.failed_files == ("player_data.tres", "island_main_data.tres")


def test_symlink_marked_candidate_is_rejected_without_opening_it(tmp_path, monkeypatch):
    import mr_farmboy_manager.save_details as module
    monkeypatch.setattr(module, "os", os, raising=False)

    target = tmp_path / "player_data.tres"
    write_tres(target, "[resource]\ncurrent_tutorial = 1\n")
    real_lstat = os.lstat

    def symlink_lstat(path):
        result = real_lstat(path)
        if Path(path) == target:
            return _StatProxy(result, mode=stat.S_IFLNK | 0o777)
        return result

    monkeypatch.setattr(module.os, "lstat", symlink_lstat)
    monkeypatch.setattr(
        module.os,
        "open",
        lambda path, flags: (_ for _ in ()).throw(AssertionError("must not open")),
    )

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.inspected_file_count == 0
    assert result.failed_files == ("player_data.tres",)


@pytest.mark.skipif(os.name == "nt", reason="regressão do fallback POSIX")
def test_file_swap_between_lstat_and_open_is_detected_before_read(tmp_path, monkeypatch):
    import mr_farmboy_manager.save_details as module
    monkeypatch.setattr(module, "os", os, raising=False)

    target = tmp_path / "player_data.tres"
    displaced = tmp_path / "displaced.tres"
    replacement = tmp_path / "replacement.tres"
    write_tres(target, "[resource]\ncurrent_tutorial = 1\n")
    write_tres(replacement, "[resource]\ncurrent_tutorial = 2\n")
    real_open = os.open
    swapped = False

    def swapping_open(path, flags):
        nonlocal swapped
        if Path(path) == target and not swapped:
            swapped = True
            target.replace(displaced)
            replacement.replace(target)
        return real_open(path, flags)

    monkeypatch.setattr(module.os, "open", swapping_open)
    monkeypatch.setattr(
        module.os,
        "read",
        lambda fd, size: (_ for _ in ()).throw(AssertionError("must detect before read")),
    )

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.inspected_file_count == 0
    assert result.failed_files == ("player_data.tres",)


@pytest.mark.skipif(os.name == "nt", reason="regressão do fallback POSIX")
def test_slot_swap_between_lstat_and_open_is_detected_before_read(tmp_path, monkeypatch):
    import mr_farmboy_manager.save_details as module
    monkeypatch.setattr(module, "os", os, raising=False)

    slot = tmp_path / "save_7"
    slot.mkdir()
    target = slot / "player_data.tres"
    write_tres(target, "[resource]\ncurrent_tutorial = 1\n")
    displaced_slot = tmp_path / "displaced_save_7"
    real_open = os.open
    swapped = False

    def swapping_open(path, flags):
        nonlocal swapped
        if Path(path) == target and not swapped:
            swapped = True
            slot.rename(displaced_slot)
            slot.mkdir()
            os.link(displaced_slot / target.name, slot / target.name)
        return real_open(path, flags)

    monkeypatch.setattr(module.os, "open", swapping_open)
    monkeypatch.setattr(
        module.os,
        "read",
        lambda fd, size: (_ for _ in ()).throw(AssertionError("must detect before read")),
    )

    result = inspect_save_slot(summary_for(slot))

    assert result.inspected_file_count == 0
    assert result.failed_files == ("player_data.tres",)


def test_growth_past_limit_during_read_is_rejected(tmp_path, monkeypatch):
    import mr_farmboy_manager.save_details as module
    monkeypatch.setattr(module, "os", os, raising=False)

    target = tmp_path / "player_data.tres"
    write_tres(target, "[resource]\ncurrent_tutorial = 1\n")
    original_size = target.stat().st_size
    real_read = os.read
    grew = False

    def growing_read(fd, size):
        nonlocal grew
        if not grew:
            grew = True
            with target.open("ab") as stream:
                stream.write(b"x")
        return real_read(fd, size)

    monkeypatch.setattr(module.os, "read", growing_read)

    result = inspect_save_slot(
        summary_for(tmp_path), max_file_size_bytes=original_size
    )

    assert result.inspected_file_count == 0
    assert result.failed_files == ("player_data.tres",)


def test_reader_failure_becomes_sanitized_filename(tmp_path, monkeypatch):
    import mr_farmboy_manager.save_details as module
    monkeypatch.setattr(module, "os", os, raising=False)

    target = tmp_path / "player_data.tres"
    write_tres(target, "[resource]\ncurrent_tutorial = 1\n")
    if os.name == "nt":
        monkeypatch.setattr(
            module,
            "_open_win32_handle",
            lambda path, access, flags: (_ for _ in ()).throw(
                PermissionError("private path")
            ),
        )
    else:
        monkeypatch.setattr(
            module.os,
            "open",
            lambda path, flags: (_ for _ in ()).throw(
                PermissionError("private path")
            ),
        )

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.inspected_file_count == 0
    assert result.failed_files == ("player_data.tres",)
    assert str(tmp_path) not in repr(result)
    assert "private path" not in repr(result)


def test_descriptor_is_closed_before_parser_receives_bytes(tmp_path, monkeypatch):
    import mr_farmboy_manager.save_details as module
    monkeypatch.setattr(module, "os", os, raising=False)

    target = tmp_path / "player_data.tres"
    write_tres(target, "[resource]\ncurrent_tutorial = 1\n")
    real_open = os.open
    opened_fds = []

    def recording_open(path, flags):
        fd = real_open(path, flags)
        opened_fds.append(fd)
        return fd

    if os.name == "nt":
        real_open_osfhandle = module.msvcrt.open_osfhandle

        def recording_open_osfhandle(handle, flags):
            fd = real_open_osfhandle(handle, flags)
            opened_fds.append(fd)
            return fd

        monkeypatch.setattr(
            module.msvcrt, "open_osfhandle", recording_open_osfhandle
        )
    else:
        monkeypatch.setattr(module.os, "open", recording_open)

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.inspected_file_count == 1
    assert len(opened_fds) == 1
    with pytest.raises(OSError):
        os.fstat(opened_fds[0])


def test_unknown_property_variant_is_never_retained_or_even_accessed():
    import mr_farmboy_manager.save_details as module

    class UnknownProperty:
        name = "inventory"

        @property
        def variant(self):
            raise AssertionError("unknown variant must not be accessed")

    document = SimpleNamespace(
        sections=(SimpleNamespace(properties=(UnknownProperty(),)),)
    )

    assert module._properties_by_name(document, {"current_tutorial"}) == {}


def test_timestamp_conversion_failure_is_sanitized_per_file(tmp_path, monkeypatch):
    import mr_farmboy_manager.save_details as module

    target = tmp_path / "player_data.tres"
    write_tres(target, "[resource]\ncurrent_tutorial = 1\n")

    class BrokenDatetime:
        @staticmethod
        def fromtimestamp(value, *, tz):
            raise OverflowError("private timestamp")

    monkeypatch.setattr(module, "datetime", BrokenDatetime)

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.inspected_file_count == 0
    assert result.failed_files == ("player_data.tres",)
    assert "private timestamp" not in repr(result)


def test_catastrophic_parser_failure_is_not_swallowed(tmp_path, monkeypatch):
    import mr_farmboy_manager.save_details as module

    target = tmp_path / "player_data.tres"
    write_tres(target, "[resource]\ncurrent_tutorial = 1\n")
    monkeypatch.setattr(
        module,
        "parse_godot_tres_document",
        lambda data: (_ for _ in ()).throw(AssertionError("catastrophic")),
    )

    with pytest.raises(AssertionError, match="catastrophic"):
        inspect_save_slot(summary_for(tmp_path))


def test_file_size_override_cannot_exceed_exported_safety_ceiling(tmp_path):
    import mr_farmboy_manager.save_details as module

    ceiling = getattr(module, "MAX_SAVE_DETAIL_FILE_SIZE_BYTES", None)
    assert ceiling == 8 * 1024 * 1024
    with pytest.raises(ValueError):
        inspect_save_slot(summary_for(tmp_path), max_file_size_bytes=ceiling + 1)


@pytest.mark.parametrize("invalid_limit", [True, -1, 1.5])
def test_file_size_override_rejects_invalid_values(tmp_path, invalid_limit):
    with pytest.raises(ValueError):
        inspect_save_slot(summary_for(tmp_path), max_file_size_bytes=invalid_limit)


def test_player_progress_uses_fingerprinted_sub_resource_at_real_ordinal(tmp_path):
    write_tres(
        tmp_path / "player_data.tres",
        """[ext_resource type="Script" path="res://one.gd" id="1"]
[ext_resource type="Script" path="res://two.gd" id="2"]
[ext_resource type="Script" path="res://three.gd" id="3"]
[sub_resource type="Resource" id="variable-player-id"]
current_tutorial = 4
gameMode = 2
island_id = 9
""",
    )

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.player_progress.tutorial_stage == 4
    assert result.player_progress.game_mode_code == 2
    assert result.player_progress.island_id == 9


def test_player_decoy_with_two_anchors_does_not_shadow_fingerprint(tmp_path):
    write_tres(
        tmp_path / "player_data.tres",
        """[sub_resource type="Resource" id="decoy"]
current_tutorial = 99
gameMode = 98

[sub_resource type="Resource" id="actual"]
current_tutorial = 4
gameMode = 2
island_id = 9
""",
    )

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.player_progress.tutorial_stage == 4
    assert result.player_progress.game_mode_code == 2
    assert result.player_progress.island_id == 9


def test_player_anchors_split_across_sections_are_not_combined(tmp_path):
    write_tres(
        tmp_path / "player_data.tres",
        """[sub_resource type="Resource" id="one"]
current_tutorial = 4
[sub_resource type="Resource" id="two"]
gameMode = 2
[sub_resource type="Resource" id="three"]
island_id = 9
""",
    )

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.player_progress.tutorial_stage is None
    assert result.player_progress.game_mode_code is None
    assert result.player_progress.island_id is None


def test_player_resource_section_with_all_anchors_is_ignored(tmp_path):
    write_tres(
        tmp_path / "player_data.tres",
        """[resource]
current_tutorial = 4
gameMode = 2
island_id = 9
""",
    )

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.player_progress.tutorial_stage is None
    assert result.player_progress.game_mode_code is None
    assert result.player_progress.island_id is None


def test_player_optional_containers_may_be_missing_or_wrong_type(tmp_path):
    write_tres(
        tmp_path / "player_data.tres",
        """[sub_resource type="Resource" id="actual"]
current_tutorial = 4
gameMode = 2
island_id = 9
highlighted_unlocked = {}
advancements_data = []
""",
    )

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.player_progress.tutorial_stage == 4
    assert result.player_progress.highlighted_unlock_count is None
    assert result.player_progress.endless_unlock_count is None
    assert result.player_progress.advancement_group_count is None


def test_player_fingerprint_does_not_access_unknown_variant():
    import mr_farmboy_manager.save_details as module

    class UnknownProperty:
        name = "inventory"

        @property
        def variant(self):
            raise AssertionError("unknown variant must not be accessed")

    def integer_property(name, value):
        return SimpleNamespace(
            name=name,
            variant=SimpleNamespace(
                kind=module.GodotVariantKind.INTEGER, value=value
            ),
        )

    document = SimpleNamespace(
        sections=(
            SimpleNamespace(
                kind=module.GodotTresSectionKind.SUB_RESOURCE,
                properties=(
                    integer_property("current_tutorial", 4),
                    integer_property("gameMode", 2),
                    integer_property("island_id", 9),
                    UnknownProperty(),
                ),
            ),
        )
    )

    progress = module._player_progress(document)

    assert progress.tutorial_stage == 4
    assert progress.game_mode_code == 2
    assert progress.island_id == 9


def test_crop_progress_uses_only_valid_sub_resource_records(tmp_path):
    write_tres(
        tmp_path / "island_main_data.tres",
        """[sub_resource type="Resource" id="valid"]
current_growth_state = 2
is_planted = true

[sub_resource type="Resource" id="wrong_type"]
current_growth_state = "3"
is_planted = true

[resource]
current_growth_state = 7
is_planted = true
""",
    )

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.crop_progress.record_count == 1
    assert result.crop_progress.planted_count == 1
    assert result.crop_progress.growth_state_counts == ((2, 1),)


@pytest.mark.skipif(os.name != "nt", reason="exige locking real do Win32")
def test_windows_reader_blocks_write_and_replace_while_reading(tmp_path, monkeypatch):
    import mr_farmboy_manager.save_details as module

    slot = tmp_path / "save_7"
    slot.mkdir()
    target = slot / "player_data.tres"
    replacement = tmp_path / "replacement.tres"
    moved_target = tmp_path / "moved_player_data.tres"
    moved_slot = tmp_path / "moved_save_7"
    write_tres(
        target,
        """[sub_resource type="Resource" id="actual"]
current_tutorial = 1
gameMode = 2
island_id = 3
""",
    )
    write_tres(
        replacement,
        """[sub_resource type="Resource" id="replacement"]
current_tutorial = 9
gameMode = 8
island_id = 7
""",
    )
    original = target.read_bytes()
    real_read = os.read
    attack_attempted = False

    def attacking_read(fd, size):
        nonlocal attack_attempted
        if not attack_attempted:
            attack_attempted = True
            with pytest.raises(PermissionError):
                with target.open("r+b"):
                    pass
            with pytest.raises(PermissionError):
                replacement.replace(target)
        return real_read(fd, size)

    monkeypatch.setattr(module.os, "read", attacking_read)

    result = inspect_save_slot(summary_for(slot))

    assert attack_attempted is True
    assert result.failed_files == ()
    assert result.player_progress.tutorial_stage == 1
    assert target.read_bytes() == original
    target.rename(moved_target)
    slot.rename(moved_slot)


@pytest.mark.skipif(os.name != "nt", reason="exige helper Win32")
def test_windows_handle_reparse_attribute_is_rejected(tmp_path, monkeypatch):
    import mr_farmboy_manager.save_details as module

    target = tmp_path / "player_data.tres"
    write_tres(target, "[resource]\ncurrent_tutorial = 1\n")
    real_get_info = getattr(module, "_get_win32_file_information", None)
    calls = 0

    def flagged_info(handle):
        nonlocal calls
        calls += 1
        if real_get_info is None:
            return SimpleNamespace(attributes=0x400)
        info = real_get_info(handle)
        if calls == 2:
            return replace(info, attributes=info.attributes | 0x400)
        return info

    monkeypatch.setattr(
        module, "_get_win32_file_information", flagged_info, raising=False
    )

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.inspected_file_count == 0
    assert result.failed_files == ("player_data.tres",)


@pytest.mark.skipif(os.name != "nt", reason="exige helper Win32")
def test_windows_candidate_final_parent_must_match_slot_handle_path(tmp_path, monkeypatch):
    import mr_farmboy_manager.save_details as module

    target = tmp_path / "player_data.tres"
    write_tres(target, "[resource]\ncurrent_tutorial = 1\n")
    real_final_path = getattr(module, "_get_win32_final_path", None)
    calls = 0

    def divergent_path(handle):
        nonlocal calls
        calls += 1
        if calls == 2:
            return r"\\?\C:\outside\player_data.tres"
        if real_final_path is None:
            return str(tmp_path)
        return real_final_path(handle)

    monkeypatch.setattr(module, "_get_win32_final_path", divergent_path, raising=False)

    result = inspect_save_slot(summary_for(tmp_path))

    assert result.inspected_file_count == 0
    assert result.failed_files == ("player_data.tres",)


def test_two_descriptor_reads_reject_same_size_divergent_bytes(tmp_path, monkeypatch):
    import mr_farmboy_manager.save_details as module

    target = tmp_path / "player_data.tres"
    write_tres(target, "[resource]\ncurrent_tutorial = 1\n")
    real_read = os.read
    nonempty_reads = 0

    def divergent_read(fd, size):
        nonlocal nonempty_reads
        block = real_read(fd, size)
        if block:
            nonempty_reads += 1
            if nonempty_reads == 2:
                return block.replace(b" = 1", b" = 2", 1)
        return block

    monkeypatch.setattr(module.os, "read", divergent_read)

    result = inspect_save_slot(summary_for(tmp_path))

    assert nonempty_reads >= 2
    assert result.inspected_file_count == 0
    assert result.failed_files == ("player_data.tres",)
