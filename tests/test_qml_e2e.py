"""Jornada QML e contratos dos entry points, sempre isolados em ``tmp_path``."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from mr_farmboy_manager.backups import create_backup, delete_backup, restore_backup
from mr_farmboy_manager.diagnostics import configure_logging
from mr_farmboy_manager.manual_paths import load_save_slot_summaries
from mr_farmboy_manager.save_details import inspect_save_slot


def test_qml_entrypoints_use_qml_runner() -> None:
    project_root = Path(__file__).resolve().parents[1]
    assert 'mr_farmboy_manager.qml_application:run' in (project_root / 'pyproject.toml').read_text(encoding='utf-8')
    assert 'from .qml_application import run' in (project_root / 'src/mr_farmboy_manager/__main__.py').read_text(encoding='utf-8')
    assert 'from mr_farmboy_manager.qml_application import run' in (project_root / 'tools/windows_entrypoint.py').read_text(encoding='utf-8')


def test_complete_qml_journey_only_mutates_tmp_path(tmp_path: Path, caplog) -> None:
    game_data = tmp_path / 'game_data'
    slot = game_data / 'save_1'
    slot.mkdir(parents=True)
    runtime = tmp_path / 'runtime'
    player = slot / 'player_data.tres'
    original = '[gd_resource type="Resource" format=3]\ncurrent_tutorial = 1\n'
    player.write_text(original, encoding='utf-8')
    (slot / 'island_main_data.tres').write_text(
        '[gd_resource type="Resource" format=3]\ncurrent_growth_state = 4\nis_planted = true\n',
        encoding='utf-8',
    )
    outside_before = {path: path.stat().st_mtime_ns for path in tmp_path.parent.iterdir() if path != tmp_path}
    caplog.set_level(logging.INFO, logger='mr_farmboy_manager')
    log_path = configure_logging(runtime / 'logs')

    loaded = load_save_slot_summaries(str(game_data))
    assert loaded.is_success and len(loaded.summaries) == 1
    summary = loaded.summaries[0]
    assert inspect_save_slot(summary).inspected_file_count == 2
    created = create_backup(summary.slot, game_data, runtime / 'backups', created_at=datetime(2026, 8, 10, tzinfo=UTC), suffix='a' * 32)
    assert created.is_success and created.backup is not None
    player.write_text(original.replace(' = 1', ' = 9'), encoding='utf-8')
    restored = restore_backup(summary.slot, game_data, runtime / 'backups', created.backup.backup_id, confirmed=True)
    assert restored.is_success and player.read_text(encoding='utf-8') == original
    deleted = delete_backup(runtime / 'backups', created.backup.backup_id, confirmed=True)
    assert deleted.is_success
    refreshed = load_save_slot_summaries(str(game_data))
    assert refreshed.is_success and refreshed.summaries[0].slot.path == slot
    logging.getLogger('mr_farmboy_manager').info('qml.e2e.completed slot=1')
    for handler in logging.getLogger('mr_farmboy_manager').handlers:
        handler.flush()
    assert log_path is not None and log_path.exists()
    assert str(tmp_path) not in log_path.read_text(encoding='utf-8')
    assert outside_before == {path: path.stat().st_mtime_ns for path in outside_before}
