"""Testes TDD do painel de detalhes do slot de save."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QListWidget, QPlainTextEdit

from mr_farmboy_manager.save_details import (
    CropProgressDetails,
    PlayerProgressDetails,
    SaveSlotDetails,
)
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def summary_for(path: Path, number: int = 7, tres_count: int = 5) -> SaveSlotSummary:
    return SaveSlotSummary(SaveSlot(number=number, path=path), tres_count)


def details_for(summary: SaveSlotSummary) -> SaveSlotDetails:
    return SaveSlotDetails(
        summary=summary,
        latest_modified_at=datetime(2026, 8, 8, 12, 30, tzinfo=timezone.utc),
        inspected_file_count=2,
        total_property_count=17,
        failed_files=("arquivo_corrompido.tres",),
        player_progress=PlayerProgressDetails(3, 2, 9, 4, 5, 6),
        crop_progress=CropProgressDetails(8, 7, 6, 5, 4, 3, 2, ((1, 2), (4, 6))),
    )


def detail_widgets(window):
    group = window.findChild(QGroupBox, "save_slot_details_group")
    status = window.findChild(QLabel, "save_slot_details_status_label")
    view = window.findChild(QPlainTextEdit, "save_slot_details_view")
    assert group is not None and status is not None and view is not None
    return group, status, view


def test_initial_details_panel_orients_without_calling_loader(qt_app: QApplication, tmp_path: Path) -> None:
    from mr_farmboy_manager.application import create_main_window

    calls = 0
    summary = summary_for(tmp_path / "save_7")

    def details_loader(received: SaveSlotSummary) -> SaveSlotDetails:
        nonlocal calls
        calls += 1
        return details_for(received)

    window = create_main_window(qt_app, loader=lambda: [summary], save_details_loader=details_loader)
    window.show()
    qt_app.processEvents()
    try:
        group, status, view = detail_widgets(window)

        assert calls == 0
        assert "Selecione" in status.text()
        assert "Selecione" in view.toPlainText()
        assert view.isReadOnly()
        assert view.font().family() == QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        assert 190 <= view.minimumHeight() <= view.maximumHeight() <= 220
        assert view.height() >= view.minimumHeight()
        assert group.height() > view.height()
        assert group.title() == "Detalhes do slot"
    finally:
        window.close()
        qt_app.processEvents()


def test_selection_renders_complete_field_notebook_and_preserves_callback(qt_app: QApplication, tmp_path: Path) -> None:
    from mr_farmboy_manager.application import create_main_window

    summary = summary_for(tmp_path / "save_7")
    received: list[SaveSlotSummary] = []
    calls: list[SaveSlotSummary] = []
    events: list[str] = []

    def callback(received_summary: SaveSlotSummary) -> None:
        events.append("callback")
        received.append(received_summary)

    def details_loader(received_summary: SaveSlotSummary) -> SaveSlotDetails:
        events.append("loader")
        calls.append(received_summary)
        return details_for(received_summary)

    window = create_main_window(
        qt_app,
        loader=lambda: [summary],
        save_details_loader=details_loader,
        on_slot_selected=callback,
    )
    save_list = window.findChild(QListWidget, "save_slots_list")
    assert save_list is not None
    save_list.setCurrentRow(0)
    qt_app.processEvents()
    _, _, view = detail_widgets(window)
    text = view.toPlainText()

    assert calls == [summary]
    assert received == [summary]
    assert events == ["callback", "loader"]
    for expected in (
        "Slot 7",
        str(tmp_path / "save_7"),
        "2026-08-08 12:30 UTC",
        "5",
        "2",
        "arquivo_corrompido.tres",
        "17",
        "Tutorial: 3",
        "Modo do jogo (código): 2",
        "Ilha (código): 9",
        "Destaques desbloqueados: 4",
        "Endless desbloqueados: 5",
        "Grupos de progresso: 6",
        "Registros: 8",
        "Plantados: 7",
        "Regados: 6",
        "Fertilizados: 5",
        "Maduros: 4",
        "Colhíveis: 3",
        "Mortos: 2",
        "1: 2",
        "4: 6",
        "Dados financeiros: não encontrados no schema analisado.",
        "Inventário detalhado: indisponível (formato opaco).",
    ):
        assert expected in text


def test_none_and_loader_error_are_sanitized_without_blocking_callback(qt_app: QApplication, tmp_path: Path) -> None:
    from mr_farmboy_manager.application import create_main_window

    secret_path = tmp_path / "segredo"
    summary = summary_for(secret_path)
    received: list[SaveSlotSummary] = []
    none_details = SaveSlotDetails(summary, None, 0, 0, ("apenas_nome.tres",), None, None)
    responses = [none_details, RuntimeError(f"{secret_path} TOKEN-SECRETO")]

    def details_loader(received_summary: SaveSlotSummary) -> SaveSlotDetails:
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    window = create_main_window(qt_app, loader=lambda: [summary], save_details_loader=details_loader, on_slot_selected=received.append)
    save_list = window.findChild(QListWidget, "save_slots_list")
    assert save_list is not None
    save_list.setCurrentRow(0)
    qt_app.processEvents()
    _, _, view = detail_widgets(window)
    assert "não disponível" in view.toPlainText()
    assert "apenas_nome.tres" in view.toPlainText()

    save_list.setCurrentRow(-1)
    save_list.setCurrentRow(0)
    qt_app.processEvents()
    _, status, view = detail_widgets(window)
    assert "jogo fechado" in status.text().lower()
    assert "TOKEN-SECRETO" not in status.text() + view.toPlainText()
    assert str(secret_path) not in status.text() + view.toPlainText()
    assert received == [summary, summary]


def test_internal_none_values_render_without_crashing(qt_app: QApplication, tmp_path: Path) -> None:
    from mr_farmboy_manager.application import create_main_window

    summary = summary_for(tmp_path / "save_7")
    details = SaveSlotDetails(
        summary,
        None,
        1,
        3,
        (),
        PlayerProgressDetails(None, None, None, None, None, None),
        CropProgressDetails(2, 1, 0, 0, 0, 0, 0, ()),
    )
    window = create_main_window(
        qt_app,
        loader=lambda: [summary],
        save_details_loader=lambda received: details,
    )
    save_list = window.findChild(QListWidget, "save_slots_list")
    assert save_list is not None
    save_list.setCurrentRow(0)
    qt_app.processEvents()
    text = detail_widgets(window)[2].toPlainText()

    for label in (
        "Tutorial",
        "Modo do jogo (código)",
        "Ilha (código)",
        "Destaques desbloqueados",
        "Endless desbloqueados",
        "Grupos de progresso",
        "Estados de crescimento",
    ):
        assert f"{label}: não disponível" in text
    assert "Registros: 2" in text
    assert "Plantados: 1" in text


def test_formatter_failure_is_sanitized_and_callback_still_runs(qt_app: QApplication, tmp_path: Path) -> None:
    from mr_farmboy_manager.application import create_main_window

    secret_path = tmp_path / "segredo-do-formatador"
    summary = summary_for(secret_path)
    events: list[str] = []

    class ExplodingTimestamp:
        def astimezone(self, zone):
            raise RuntimeError(f"{secret_path} FORMATTER-TOKEN")

    malformed_details = SimpleNamespace(latest_modified_at=ExplodingTimestamp())

    def callback(received_summary: SaveSlotSummary) -> None:
        assert received_summary is summary
        events.append("callback")

    def details_loader(received_summary: SaveSlotSummary):
        assert received_summary is summary
        events.append("loader")
        return malformed_details

    window = create_main_window(
        qt_app,
        loader=lambda: [summary],
        on_slot_selected=callback,
        save_details_loader=details_loader,
    )
    save_list = window.findChild(QListWidget, "save_slots_list")
    assert save_list is not None
    save_list.setCurrentRow(0)
    qt_app.processEvents()
    _, status, view = detail_widgets(window)
    visible_text = status.text() + view.toPlainText()

    assert events == ["callback", "loader"]
    assert "jogo fechado" in visible_text.lower()
    assert str(secret_path) not in visible_text
    assert "FORMATTER-TOKEN" not in visible_text


def test_refresh_replaces_selection_and_resets_details(qt_app: QApplication, tmp_path: Path) -> None:
    from mr_farmboy_manager.application import create_main_window
    from PySide6.QtCore import QTimer

    first = summary_for(tmp_path / "save_1", 1)
    second = summary_for(tmp_path / "save_2", 2)
    responses = [[first], [second]]
    window = create_main_window(qt_app, loader=lambda: responses.pop(0), save_details_loader=details_for)
    save_list = window.findChild(QListWidget, "save_slots_list")
    timer = window.findChild(QTimer, "save_auto_refresh_timer")
    assert save_list is not None and timer is not None
    save_list.setCurrentRow(0)
    qt_app.processEvents()
    assert "Slot 1" in detail_widgets(window)[2].toPlainText()

    timer.timeout.emit()
    qt_app.processEvents()
    _, status, view = detail_widgets(window)
    assert save_list.currentRow() == -1
    assert "Selecione" in status.text()
    assert "Slot 1" not in view.toPlainText()


def test_default_loader_inspects_synthetic_tres_slot(qt_app: QApplication, tmp_path: Path) -> None:
    from mr_farmboy_manager.application import create_main_window

    slot_path = tmp_path / "save_3"
    slot_path.mkdir()
    (slot_path / "player_data.tres").write_text(
        "[gd_resource type=\"Resource\" format=3]\n[sub_resource type=\"Resource\" id=\"player\"]\ncurrent_tutorial = 1\ngameMode = 2\nisland_id = 3\nhighlighted_unlocked = [1, 2]\nthe_endless_unlocked = [3]\nadvancements_data = {\"a\": 1}\n",
        encoding="utf-8",
    )
    (slot_path / "island_main_data.tres").write_text(
        "[gd_resource type=\"Resource\" format=3]\n[sub_resource type=\"Resource\" id=\"crop\"]\ncurrent_growth_state = 4\nis_planted = true\nis_watered = true\nis_fertilized = true\nis_matured = true\nis_harvestable = true\n",
        encoding="utf-8",
    )
    summary = summary_for(slot_path, 3, 2)
    window = create_main_window(qt_app, loader=lambda: [summary])
    save_list = window.findChild(QListWidget, "save_slots_list")
    assert save_list is not None
    save_list.setCurrentRow(0)
    qt_app.processEvents()
    text = detail_widgets(window)[2].toPlainText()

    assert "Tutorial: 1" in text
    assert "Modo do jogo (código): 2" in text
    assert "Estados de crescimento: 4: 1" in text
