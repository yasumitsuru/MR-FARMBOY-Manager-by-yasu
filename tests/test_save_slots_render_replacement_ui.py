"""Testes para substituição de itens na renderização de slots de save."""

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


class TestSaveSlotsRenderReplacementUI:
    """Testes de substituição de itens na renderização de slots de save."""

    def test_segundo_resultado_substitui_o_primeiro(
        self,
        qt_app: QApplication,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Verifica que segundo clique substitui o primeiro resultado."""
        from mr_farmboy_manager.application import create_main_window

        slot1 = SaveSlot(number=1, path=Path("save_1"))
        slot2 = SaveSlot(number=2, path=Path("save_2"))
        summary1_first = SaveSlotSummary(slot=slot1, tres_file_count=4)
        summary2_first = SaveSlotSummary(slot=slot2, tres_file_count=7)
        summary2_second = SaveSlotSummary(slot=slot2, tres_file_count=9)

        call_count = 0
        def manual_loader(path: str) -> SaveSlotsLoadResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return SaveSlotsLoadResult(
                    validation=DirectoryValidationResult(code=DirectoryValidationCode.VALID, path=None),
                    summaries=(summary1_first, summary2_first),
                )
            else:
                return SaveSlotsLoadResult(
                    validation=DirectoryValidationResult(code=DirectoryValidationCode.VALID, path=None),
                    summaries=(summary2_second,),
                )

        monkeypatch.setenv("APPDATA", str(tmp_path))
        window = create_main_window(qt_app, manual_save_loader=manual_loader)

        button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget)

        assert button is not None
        assert list_widget is not None

        # Primeiro clique
        button.click()
        QApplication.processEvents()

        assert list_widget.count() == 2
        assert list_widget.item(0).text() == "save_1 — Slot 1 — 4 arquivos .tres"
        assert list_widget.item(1).text() == "save_2 — Slot 2 — 7 arquivos .tres"

        # Segundo clique - deve substituir, não acumular
        button.click()
        QApplication.processEvents()

        assert list_widget.count() == 1
        assert list_widget.item(0).text() == "save_2 — Slot 2 — 9 arquivos .tres"

    def test_resultado_vazio_remove_itens_anteriores(
        self,
        qt_app: QApplication,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Verifica que resultado vazio remove itens anteriores."""
        from mr_farmboy_manager.application import create_main_window

        slot1 = SaveSlot(number=1, path=Path("save_1"))
        slot2 = SaveSlot(number=2, path=Path("save_2"))
        summary1 = SaveSlotSummary(slot=slot1, tres_file_count=4)
        summary2 = SaveSlotSummary(slot=slot2, tres_file_count=7)

        call_count = 0
        def manual_loader(path: str) -> SaveSlotsLoadResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return SaveSlotsLoadResult(
                    validation=DirectoryValidationResult(code=DirectoryValidationCode.VALID, path=None),
                    summaries=(summary1, summary2),
                )
            else:
                return SaveSlotsLoadResult(
                    validation=DirectoryValidationResult(code=DirectoryValidationCode.VALID, path=None),
                    summaries=(),
                )

        monkeypatch.setenv("APPDATA", str(tmp_path))
        window = create_main_window(qt_app, manual_save_loader=manual_loader)

        button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget)
        label = window.findChild(QLabel, "empty_save_slots_label")

        assert button is not None
        assert list_widget is not None
        assert label is not None

        # Primeiro clique
        button.click()
        QApplication.processEvents()

        assert list_widget.count() == 2
        assert list_widget.isHidden() is False
        assert label.isHidden() is True

        # Segundo clique com resultado vazio
        button.click()
        QApplication.processEvents()

        assert list_widget.count() == 0
        assert list_widget.isHidden() is True
        assert label.isHidden() is False

    def test_novo_resultado_nao_acumula_itens(
        self,
        qt_app: QApplication,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Verifica que novo resultado não acumula itens."""
        from mr_farmboy_manager.application import create_main_window

        slot1 = SaveSlot(number=1, path=Path("save_1"))
        slot2 = SaveSlot(number=2, path=Path("save_2"))
        slot3 = SaveSlot(number=3, path=Path("save_3"))

        call_count = 0
        def manual_loader(path: str) -> SaveSlotsLoadResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return SaveSlotsLoadResult(
                    validation=DirectoryValidationResult(code=DirectoryValidationCode.VALID, path=None),
                    summaries=(SaveSlotSummary(slot=slot1, tres_file_count=4), SaveSlotSummary(slot=slot2, tres_file_count=7)),
                )
            elif call_count == 2:
                return SaveSlotsLoadResult(
                    validation=DirectoryValidationResult(code=DirectoryValidationCode.VALID, path=None),
                    summaries=(SaveSlotSummary(slot=slot1, tres_file_count=4), SaveSlotSummary(slot=slot2, tres_file_count=7), SaveSlotSummary(slot=slot3, tres_file_count=9)),
                )
            else:
                return SaveSlotsLoadResult(
                    validation=DirectoryValidationResult(code=DirectoryValidationCode.VALID, path=None),
                    summaries=(SaveSlotSummary(slot=slot3, tres_file_count=9),),
                )

        monkeypatch.setenv("APPDATA", str(tmp_path))
        window = create_main_window(qt_app, manual_save_loader=manual_loader)

        button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget)

        assert button is not None
        assert list_widget is not None

        # Primeiro clique - 2 resumos
        button.click()
        QApplication.processEvents()

        assert list_widget.count() == 2

        # Segundo clique - 3 resumos (substitui, não acumula)
        button.click()
        QApplication.processEvents()

        assert list_widget.count() == 3

        # Terceiro clique - 1 resumo (substitui, não acumula)
        button.click()
        QApplication.processEvents()

        assert list_widget.count() == 1
