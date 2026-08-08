"""Testes da atualizacao automatica dos slots de save."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
)

from mr_farmboy_manager.manual_paths import (
    DirectoryValidationCode,
    DirectoryValidationResult,
    SaveSlotsLoadResult,
)
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    """Cria uma unica QApplication para os testes deste modulo."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _summary(number: int, tres_file_count: int) -> SaveSlotSummary:
    return SaveSlotSummary(
        slot=SaveSlot(number=number, path=Path(f"save_{number}")),
        tres_file_count=tres_file_count,
    )


class TestAutomaticRefreshUI:
    """Comportamentos do temporizador de atualizacao da janela principal."""

    def test_timer_inicia_ativo_com_intervalo_de_cinco_minutos(
        self,
        qt_app: QApplication,
    ) -> None:
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app, loader=lambda: [])
        timer = window.findChild(QTimer, "save_auto_refresh_timer")

        assert timer is not None
        assert timer.isActive() is True
        assert timer.interval() == 300_000

    def test_timeout_recarrega_fonte_inicial_e_sincroniza_selecao(
        self,
        qt_app: QApplication,
    ) -> None:
        from mr_farmboy_manager.application import create_main_window

        initial_summary = _summary(1, 4)
        refreshed_summary = _summary(2, 7)
        pending_results = [[initial_summary], [refreshed_summary]]
        received_summaries: list[SaveSlotSummary] = []

        def loader() -> list[SaveSlotSummary]:
            return pending_results.pop(0)

        window = create_main_window(
            qt_app,
            loader=loader,
            on_slot_selected=received_summaries.append,
        )
        timer = window.findChild(QTimer, "save_auto_refresh_timer")
        list_widget = window.findChild(QListWidget, "save_slots_list")

        assert timer is not None
        assert list_widget is not None

        timer.timeout.emit()
        list_widget.setCurrentRow(0)
        QApplication.processEvents()

        assert list_widget.item(0).text() == "save_2 — Slot 2 — 7 arquivos .tres"
        assert received_summaries == [refreshed_summary]

    def test_timeout_preserva_ultima_fonte_manual_valida(
        self,
        qt_app: QApplication,
    ) -> None:
        from mr_farmboy_manager.application import create_main_window

        initial_summary = _summary(1, 4)
        manual_summary = _summary(2, 7)
        refreshed_manual_summary = _summary(3, 9)
        initial_load_count = 0
        manual_paths: list[str] = []
        pending_manual_summaries = [manual_summary, refreshed_manual_summary]

        def initial_loader() -> list[SaveSlotSummary]:
            nonlocal initial_load_count
            initial_load_count += 1
            return [initial_summary]

        def manual_loader(path: str) -> SaveSlotsLoadResult:
            manual_paths.append(path)
            return SaveSlotsLoadResult(
                validation=DirectoryValidationResult(
                    code=DirectoryValidationCode.VALID,
                    path=Path(path),
                ),
                summaries=(pending_manual_summaries.pop(0),),
            )

        window = create_main_window(
            qt_app,
            loader=initial_loader,
            manual_save_loader=manual_loader,
        )
        timer = window.findChild(QTimer, "save_auto_refresh_timer")
        path_input = window.findChild(QLineEdit, "save_path_input")
        load_button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget, "save_slots_list")

        assert timer is not None
        assert path_input is not None
        assert load_button is not None
        assert list_widget is not None

        loaded_path = "C:\\synthetic\\game_data"
        path_input.setText(loaded_path)
        load_button.click()
        path_input.setText("C:\\edited-but-not-loaded")
        timer.timeout.emit()
        QApplication.processEvents()

        assert initial_load_count == 1
        assert manual_paths == [loaded_path, loaded_path]
        assert list_widget.item(0).text() == "save_3 — Slot 3 — 9 arquivos .tres"

    def test_timeout_invalido_remove_dados_obsoletos_e_exibe_status(
        self,
        qt_app: QApplication,
    ) -> None:
        from mr_farmboy_manager.application import create_main_window

        manual_summary = _summary(2, 7)
        pending_results = [
            SaveSlotsLoadResult(
                validation=DirectoryValidationResult(
                    code=DirectoryValidationCode.VALID,
                    path=Path("C:\\synthetic\\game_data"),
                ),
                summaries=(manual_summary,),
            ),
            SaveSlotsLoadResult(
                validation=DirectoryValidationResult(
                    code=DirectoryValidationCode.NOT_FOUND,
                    path=Path("C:\\synthetic\\game_data"),
                ),
                summaries=(),
            ),
        ]

        window = create_main_window(
            qt_app,
            loader=lambda: [],
            manual_save_loader=lambda path: pending_results.pop(0),
        )
        timer = window.findChild(QTimer, "save_auto_refresh_timer")
        path_input = window.findChild(QLineEdit, "save_path_input")
        load_button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget, "save_slots_list")
        empty_label = window.findChild(QLabel, "empty_save_slots_label")

        assert timer is not None
        assert path_input is not None
        assert load_button is not None
        assert list_widget is not None
        assert empty_label is not None

        path_input.setText("C:\\synthetic\\game_data")
        load_button.click()
        timer.timeout.emit()
        QApplication.processEvents()

        assert list_widget.count() == 0
        assert empty_label.text() == "A pasta dos saves não existe."
        assert empty_label.isHidden() is False

    def test_tentativa_manual_invalida_nao_substitui_fonte_ativa(
        self,
        qt_app: QApplication,
    ) -> None:
        from mr_farmboy_manager.application import create_main_window

        loaded_path = "C:\\synthetic\\game_data"
        invalid_path = "C:\\missing"
        manual_paths: list[str] = []
        pending_results = [
            SaveSlotsLoadResult(
                validation=DirectoryValidationResult(
                    code=DirectoryValidationCode.VALID,
                    path=Path(loaded_path),
                ),
                summaries=(_summary(2, 7),),
            ),
            SaveSlotsLoadResult(
                validation=DirectoryValidationResult(
                    code=DirectoryValidationCode.NOT_FOUND,
                    path=Path(invalid_path),
                ),
                summaries=(),
            ),
            SaveSlotsLoadResult(
                validation=DirectoryValidationResult(
                    code=DirectoryValidationCode.VALID,
                    path=Path(loaded_path),
                ),
                summaries=(_summary(3, 9),),
            ),
        ]

        def manual_loader(path: str) -> SaveSlotsLoadResult:
            manual_paths.append(path)
            return pending_results.pop(0)

        window = create_main_window(
            qt_app,
            loader=lambda: [],
            manual_save_loader=manual_loader,
        )
        timer = window.findChild(QTimer, "save_auto_refresh_timer")
        path_input = window.findChild(QLineEdit, "save_path_input")
        load_button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget, "save_slots_list")

        assert timer is not None
        assert path_input is not None
        assert load_button is not None
        assert list_widget is not None

        path_input.setText(loaded_path)
        load_button.click()
        path_input.setText(invalid_path)
        load_button.click()
        timer.timeout.emit()
        QApplication.processEvents()

        assert manual_paths == [loaded_path, invalid_path, loaded_path]
        assert list_widget.item(0).text() == "save_3 — Slot 3 — 9 arquivos .tres"
