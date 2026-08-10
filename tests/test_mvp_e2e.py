"""Jornada MVP integrada usando somente filesystem temporário."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
)

from mr_farmboy_manager.application import create_main_window
from mr_farmboy_manager.backups import create_backup, restore_backup


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def _widget(window, widget_type, object_name: str):
    widget = window.findChild(widget_type, object_name)
    assert widget is not None
    return widget


def test_complete_local_mvp_journey(qt_app: QApplication, tmp_path: Path) -> None:
    game_data = tmp_path / "game_data"
    slot = game_data / "save_1"
    slot.mkdir(parents=True)
    backup_root = tmp_path / "manager" / "backups"
    original_player = (
        '[gd_resource type="Resource" format=3]\n'
        '[sub_resource type="Resource" id="player"]\n'
        "current_tutorial = 1\n"
        "gameMode = 2\n"
        "island_id = 3\n"
    )
    player_file = slot / "player_data.tres"
    player_file.write_text(original_player, encoding="utf-8")
    (slot / "island_main_data.tres").write_text(
        '[gd_resource type="Resource" format=3]\n'
        '[sub_resource type="Resource" id="crop"]\n'
        "current_growth_state = 4\n"
        "is_planted = true\n"
        "is_watered = true\n",
        encoding="utf-8",
    )

    original_backup_id = "save_1-20260810T120000Z-" + "a" * 32

    def deterministic_creator(slot_to_copy, active_root, destination_root):
        return create_backup(
            slot_to_copy,
            active_root,
            destination_root,
            created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
            suffix="a" * 32,
        )

    def deterministic_restorer(
        slot_to_restore,
        active_root,
        destination_root,
        backup_id,
        *,
        confirmed,
    ):
        def preventive_creator(slot_to_copy, source_root, backup_destination):
            return create_backup(
                slot_to_copy,
                source_root,
                backup_destination,
                created_at=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
                suffix="b" * 32,
            )

        return restore_backup(
            slot_to_restore,
            active_root,
            destination_root,
            backup_id,
            confirmed=confirmed,
            preventive_backup_creator=preventive_creator,
        )

    window = create_main_window(
        qt_app,
        loader=lambda: [],
        save_directory_chooser=lambda: game_data,
        backup_root=backup_root,
        backup_creator=deterministic_creator,
        backup_restorer=deterministic_restorer,
        restore_confirmer=lambda _record: True,
        delete_confirmer=lambda _record: True,
    )
    try:
        save_input = _widget(window, QLineEdit, "save_path_input")
        browse_button = _widget(window, QPushButton, "browse_save_path_button")
        save_list = _widget(window, QListWidget, "save_slots_list")
        details = _widget(window, QPlainTextEdit, "save_slot_details_view")
        create_button = _widget(window, QPushButton, "create_backup_button")
        backup_list = _widget(window, QListWidget, "backups_list")
        restore_button = _widget(window, QPushButton, "restore_backup_button")
        delete_button = _widget(window, QPushButton, "delete_backup_button")

        browse_button.click()
        QApplication.processEvents()

        assert save_input.text() == str(game_data)
        assert save_list.count() == 1
        assert "Slot 1" in save_list.item(0).text()

        save_list.setCurrentRow(0)
        QApplication.processEvents()

        assert "Tutorial: 1" in details.toPlainText()
        assert create_button.isEnabled()

        create_button.click()
        QApplication.processEvents()

        assert (backup_root / original_backup_id).is_dir()
        assert backup_list.count() == 1
        assert original_backup_id in backup_list.item(0).text()

        player_file.write_text(
            original_player.replace("current_tutorial = 1", "current_tutorial = 9"),
            encoding="utf-8",
        )
        assert "current_tutorial = 9" in player_file.read_text(encoding="utf-8")

        backup_list.setCurrentRow(0)
        QApplication.processEvents()
        assert restore_button.isEnabled()
        restore_button.click()
        QApplication.processEvents()

        assert player_file.read_text(encoding="utf-8") == original_player
        assert backup_list.count() == 2

        original_row = next(
            row
            for row in range(backup_list.count())
            if original_backup_id in backup_list.item(row).text()
        )
        backup_list.setCurrentRow(original_row)
        QApplication.processEvents()
        assert delete_button.isEnabled()
        delete_button.click()
        QApplication.processEvents()

        assert not (backup_root / original_backup_id).exists()
        assert backup_list.count() == 1
        assert original_backup_id not in backup_list.item(0).text()
    finally:
        window.close()
        QApplication.processEvents()
