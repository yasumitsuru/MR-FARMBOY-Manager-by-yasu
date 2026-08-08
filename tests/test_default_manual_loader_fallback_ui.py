"""Testes para fallback do carregador manual usando load_save_slot_summaries."""

from __future__ import annotations

import pytest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QPushButton, QListWidget, QLabel

from mr_farmboy_manager.manual_paths import SaveSlotsLoadResult, DirectoryValidationCode, DirectoryValidationResult
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary


@pytest.fixture(scope="function")
def qt_app() -> QApplication:
    """Cria uma instância de QApplication para cada teste."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestDefaultManualLoaderFallback:
    """Testes do fallback do carregador manual usando load_save_slot_summaries."""

    def test_injected_loader_has_priority_over_fallback(
        self,
        qt_app: QApplication,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Verifica que loader injetado tem prioridade sobre o fallback."""
        from mr_farmboy_manager.application import create_main_window

        slot = SaveSlot(number=1, path=Path("save_1"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        call_count = 0
        def manual_loader(path: str) -> SaveSlotsLoadResult:
            nonlocal call_count
            call_count += 1
            return SaveSlotsLoadResult(
                validation=DirectoryValidationResult(code=DirectoryValidationCode.VALID, path=None),
                summaries=(summary,),
            )

        monkeypatch.setenv("APPDATA", str(tmp_path))
        window = create_main_window(qt_app, manual_save_loader=manual_loader)

        button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget)

        assert button is not None
        assert list_widget is not None

        # Estado inicial com lista vazia
        assert list_widget.count() == 0

        # Clique com manual_save_loader injetado - deve usar o loader, não o fallback
        button.click()
        qt_app.processEvents()

        # Loader injetado foi chamado exatamente uma vez
        assert call_count == 1

        # O item corresponde ao resumo retornado pelo loader injetado
        # (o tratamento de VALID limpa e renderiza os novos resumos)
        assert list_widget.count() == 1
        assert list_widget.item(0).text() == "save_1 — Slot 1 — 4 arquivos .tres"

    def test_fallback_real_when_manual_loader_not_provided(
        self, qt_app: QApplication
    ) -> None:
        """Verifica que fallback real ocorre quando loader manual não é fornecido."""
        from mr_farmboy_manager.application import create_main_window

        slot = SaveSlot(number=1, path=Path("save_1"))
        initial_summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        def loader() -> list[SaveSlotSummary]:
            return [initial_summary]

        window = create_main_window(qt_app, loader=loader)

        button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget)
        label = window.findChild(QLabel, "empty_save_slots_label")

        assert button is not None
        assert list_widget is not None
        assert label is not None

        # Estado inicial com item do loader padrão
        assert list_widget.count() == 1

        # Clique sem manual_save_loader - deve usar fallback e tratar como EMPTY
        button.click()
        qt_app.processEvents()

        # Tratamento real de EMPTY
        assert list_widget.count() == 0
        assert label.isHidden() is False
        assert list_widget.isHidden() is True
        assert label.text() == "Informe a pasta dos saves."
