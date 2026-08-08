"""Testes para renderização de carregamento manual válido."""

from __future__ import annotations

import pytest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QPushButton, QLineEdit, QListWidget, QLabel, QMainWindow

from mr_farmboy_manager.manual_paths import SaveSlotsLoadResult, DirectoryValidationCode, DirectoryValidationResult
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    """Cria uma instância global de QApplication para toda a suíte de testes."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app





class TestManualValidRenderUI:
    """Testes de renderização de carregamento manual válido."""

    def test_valid_com_um_resumo_renderiza_exatamente_um_item(
        self,
        qt_app: QApplication,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Verifica que VALID com um resumo renderiza exatamente um item."""
        from mr_farmboy_manager.application import create_main_window

        slot = SaveSlot(number=1, path=Path("save_1"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        def manual_loader(path: str) -> SaveSlotsLoadResult:
            return SaveSlotsLoadResult(
                validation=DirectoryValidationResult(code=DirectoryValidationCode.VALID, path=None),
                summaries=(summary,),
            )

        monkeypatch.setenv("APPDATA", str(tmp_path))
        window = create_main_window(qt_app, manual_save_loader=manual_loader)

        button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget)
        label = window.findChild(QLabel, "empty_save_slots_label")

        assert button is not None
        assert list_widget is not None
        assert label is not None

        button.click()
        QApplication.processEvents()

        assert list_widget.count() == 1
        assert list_widget.item(0).text() == "save_1 — Slot 1 — 4 arquivos .tres"
        assert label.isVisible() is False

    def test_valid_com_dois_resumos_preserva_ordem(
        self,
        qt_app: QApplication,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Verifica que VALID com dois resumos preserva a ordem."""
        from mr_farmboy_manager.application import create_main_window

        slot1 = SaveSlot(number=1, path=Path("save_1"))
        slot2 = SaveSlot(number=2, path=Path("save_2"))
        summary1 = SaveSlotSummary(slot=slot1, tres_file_count=4)
        summary2 = SaveSlotSummary(slot=slot2, tres_file_count=7)

        def manual_loader(path: str) -> SaveSlotsLoadResult:
            return SaveSlotsLoadResult(
                validation=DirectoryValidationResult(code=DirectoryValidationCode.VALID, path=None),
                summaries=(summary1, summary2),
            )

        monkeypatch.setenv("APPDATA", str(tmp_path))
        window = create_main_window(qt_app, manual_save_loader=manual_loader)

        button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget)
        label = window.findChild(QLabel, "empty_save_slots_label")

        assert button is not None
        assert list_widget is not None
        assert label is not None

        button.click()
        QApplication.processEvents()

        assert list_widget.count() == 2
        assert list_widget.item(0).text() == "save_1 — Slot 1 — 4 arquivos .tres"
        assert list_widget.item(1).text() == "save_2 — Slot 2 — 7 arquivos .tres"
        assert label.isVisible() is False

    def test_valid_vazio_deixa_lista_vazia(
        self, qt_app: QApplication
    ) -> None:
        """Verifica que VALID vazio deixa lista vazia."""
        from mr_farmboy_manager.application import create_main_window

        slot = SaveSlot(number=1, path=Path("save_1"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        loader = lambda: [summary]

        def manual_loader(path: str) -> SaveSlotsLoadResult:
            return SaveSlotsLoadResult(
                validation=DirectoryValidationResult(code=DirectoryValidationCode.VALID, path=None),
                summaries=(),
            )

        window = create_main_window(qt_app, loader=loader, manual_save_loader=manual_loader)

        button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget)
        label = window.findChild(QLabel, "empty_save_slots_label")

        assert button is not None
        assert list_widget is not None
        assert label is not None

        button.click()
        QApplication.processEvents()

        assert list_widget.count() == 0
        assert label.isHidden() is False

    def test_valid_vazio_mostra_exatamente_texto_esperado(
        self,
        qt_app: QApplication,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Verifica que VALID vazio mostra exatamente o texto esperado."""
        from mr_farmboy_manager.application import create_main_window

        def manual_loader(path: str) -> SaveSlotsLoadResult:
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

        button.click()
        QApplication.processEvents()

        assert label.text() == "Nenhum save encontrado"

    def test_selecao_apos_carga_manual_recebe_novo_resumo(
        self,
        qt_app: QApplication,
    ) -> None:
        """A selecao deve acompanhar os resumos substituidos pela carga manual."""
        from mr_farmboy_manager.application import create_main_window

        initial_summary = SaveSlotSummary(
            slot=SaveSlot(number=1, path=Path("save_1")),
            tres_file_count=4,
        )
        manual_summary = SaveSlotSummary(
            slot=SaveSlot(number=2, path=Path("save_2")),
            tres_file_count=7,
        )
        received_summaries: list[SaveSlotSummary] = []

        def manual_loader(path: str) -> SaveSlotsLoadResult:
            return SaveSlotsLoadResult(
                validation=DirectoryValidationResult(
                    code=DirectoryValidationCode.VALID,
                    path=Path(path) if path else None,
                ),
                summaries=(manual_summary,),
            )

        window = create_main_window(
            qt_app,
            loader=lambda: [initial_summary],
            manual_save_loader=manual_loader,
            on_slot_selected=received_summaries.append,
        )
        button = window.findChild(QPushButton, "load_saves_button")
        list_widget = window.findChild(QListWidget, "save_slots_list")

        assert button is not None
        assert list_widget is not None

        button.click()
        list_widget.setCurrentRow(0)
        QApplication.processEvents()

        assert received_summaries == [manual_summary]
