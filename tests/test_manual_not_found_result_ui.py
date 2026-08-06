"""Testes para tratamento de resultado NOT_FOUND no carregamento manual."""

from __future__ import annotations

import pytest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QPushButton, QListWidget, QLabel

from mr_farmboy_manager.manual_paths import SaveSlotsLoadResult, DirectoryValidationCode, DirectoryValidationResult
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    """Cria uma instância global de QApplication para toda a suíte de testes."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestManualNotFoundResultUI:
    """Testes de tratamento de resultado NOT_FOUND no carregamento manual."""

    def test_not_found_limpa_item_anterior(
        self, qt_app: QApplication
    ) -> None:
        """Verifica que NOT_FOUND limpa itens anteriores."""
        from mr_farmboy_manager.application import create_main_window

        slot = SaveSlot(number=1, path=Path("save_1"))
        initial_summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        def loader() -> list[SaveSlotSummary]:
            return [initial_summary]

        call_count = 0
        def manual_loader(path: str) -> SaveSlotsLoadResult:
            nonlocal call_count
            call_count += 1
            return SaveSlotsLoadResult(
                validation=DirectoryValidationResult(code=DirectoryValidationCode.NOT_FOUND, path=None),
                summaries=(),
            )

        window = create_main_window(qt_app, loader=loader, manual_save_loader=manual_loader)

        button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget)

        assert button is not None
        assert list_widget is not None

        # Estado inicial com item do loader padrão
        assert list_widget.count() == 1

        # Clique com resultado NOT_FOUND
        button.click()
        QApplication.processEvents()

        # Lista deve ser limpa
        assert list_widget.count() == 0

    def test_not_found_mensagem_exata(
        self, qt_app: QApplication
    ) -> None:
        """Verifica que mensagem exata é exibida após NOT_FOUND."""
        from mr_farmboy_manager.application import create_main_window

        slot = SaveSlot(number=1, path=Path("save_1"))
        initial_summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        def loader() -> list[SaveSlotSummary]:
            return [initial_summary]

        call_count = 0
        def manual_loader(path: str) -> SaveSlotsLoadResult:
            nonlocal call_count
            call_count += 1
            return SaveSlotsLoadResult(
                validation=DirectoryValidationResult(code=DirectoryValidationCode.NOT_FOUND, path=None),
                summaries=(),
            )

        window = create_main_window(qt_app, loader=loader, manual_save_loader=manual_loader)

        button = window.findChild(QPushButton, "load_saves_button")
        label = window.findChild(QLabel, "empty_save_slots_label")

        assert button is not None
        assert label is not None

        # Clique com resultado NOT_FOUND
        button.click()
        QApplication.processEvents()

        # Mensagem exata
        assert label.text() == "A pasta dos saves não existe."

    def test_not_found_visibilidade(
        self, qt_app: QApplication
    ) -> None:
        """Verifica visibilidade após NOT_FOUND."""
        from mr_farmboy_manager.application import create_main_window

        slot = SaveSlot(number=1, path=Path("save_1"))
        initial_summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        def loader() -> list[SaveSlotSummary]:
            return [initial_summary]

        call_count = 0
        def manual_loader(path: str) -> SaveSlotsLoadResult:
            nonlocal call_count
            call_count += 1
            return SaveSlotsLoadResult(
                validation=DirectoryValidationResult(code=DirectoryValidationCode.NOT_FOUND, path=None),
                summaries=(),
            )

        window = create_main_window(qt_app, loader=loader, manual_save_loader=manual_loader)

        button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget)
        label = window.findChild(QLabel, "empty_save_slots_label")

        assert button is not None
        assert list_widget is not None
        assert label is not None

        # Estado inicial
        assert list_widget.isHidden() is False
        assert label.isHidden() is True

        # Clique com resultado NOT_FOUND
        button.click()
        QApplication.processEvents()

        # Label deve ser visível, lista escondida
        assert label.isHidden() is False
        assert list_widget.isHidden() is True

    def test_not_directory_continua_sem_tratamento(
        self, qt_app: QApplication
    ) -> None:
        """Verifica que NOT_DIRECTORY continua sem tratamento visual."""
        from mr_farmboy_manager.application import create_main_window

        slot = SaveSlot(number=1, path=Path("save_1"))
        initial_summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        def loader() -> list[SaveSlotSummary]:
            return [initial_summary]

        call_count = 0
        def manual_loader(path: str) -> SaveSlotsLoadResult:
            nonlocal call_count
            call_count += 1
            return SaveSlotsLoadResult(
                validation=DirectoryValidationResult(code=DirectoryValidationCode.NOT_DIRECTORY, path=None),
                summaries=(),
            )

        window = create_main_window(qt_app, loader=loader, manual_save_loader=manual_loader)

        button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget)

        assert button is not None
        assert list_widget is not None

        # Estado inicial com item do loader padrão
        assert list_widget.count() == 1
        assert list_widget.item(0).text() == "save_1 — Slot 1 — 4 arquivos .tres"

        # Clique com resultado NOT_DIRECTORY - não deve alterar nada
        button.click()
        QApplication.processEvents()

        # Item inicial deve permanecer intacto
        assert list_widget.count() == 1
        assert list_widget.item(0).text() == "save_1 — Slot 1 — 4 arquivos .tres"
