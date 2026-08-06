"""Testes para a função de renderização de slots de save."""

from __future__ import annotations

import pytest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QListWidget, QLabel, QListWidgetItem

from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    """Cria uma instância global de QApplication para toda a suíte de testes."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(scope="function")
def save_slots_list(qt_app: QApplication) -> QListWidget:
    """Cria uma lista de slots para os testes."""
    list_widget = QListWidget()
    return list_widget


@pytest.fixture(scope="function")
def empty_label(qt_app: QApplication) -> QLabel:
    """Cria um label vazio para os testes."""
    label = QLabel("Nenhum save encontrado")
    return label


def render_save_slot_summaries(
    summaries_to_render: list[SaveSlotSummary],
    save_slots_list: QListWidget,
    empty_label: QLabel,
) -> None:
    """Renderiza os resumos dos slots de save na interface."""
    if not summaries_to_render:
        empty_label.show()
        save_slots_list.hide()
        return

    empty_label.hide()
    save_slots_list.show()

    for summary in summaries_to_render:
        line_text = (
            f"save_{summary.slot.number} — "
            f"Slot {summary.slot.number} — "
            f"{summary.tres_file_count} arquivos .tres"
        )
        save_slots_list.addItem(QListWidgetItem(line_text))


class TestSaveSlotsRenderHelperUI:
    """Testes de regressão para a função de renderização de slots de save."""

    def test_carregamento_inicial_com_um_resumo_mostra_um_item(
        self, qt_app: QApplication, save_slots_list: QListWidget, empty_label: QLabel
    ) -> None:
        """Verifica que um resumo mostra um item na lista."""
        slot = SaveSlot(number=1, path=Path("save_1"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=5)

        render_save_slot_summaries([summary], save_slots_list, empty_label)

        assert save_slots_list.count() == 1
        assert save_slots_list.item(0).text() == "save_1 — Slot 1 — 5 arquivos .tres"
        assert empty_label.isVisible() is False

    def test_carregamento_inicial_com_dois_resumos_preserva_ordem(
        self, qt_app: QApplication, save_slots_list: QListWidget, empty_label: QLabel
    ) -> None:
        """Verifica que dois resumos preservam a ordem na lista."""
        slot1 = SaveSlot(number=2, path=Path("save_2"))
        slot2 = SaveSlot(number=5, path=Path("save_5"))
        summary1 = SaveSlotSummary(slot=slot1, tres_file_count=3)
        summary2 = SaveSlotSummary(slot=slot2, tres_file_count=7)

        render_save_slot_summaries([summary1, summary2], save_slots_list, empty_label)

        assert save_slots_list.count() == 2
        assert save_slots_list.item(0).text() == "save_2 — Slot 2 — 3 arquivos .tres"
        assert save_slots_list.item(1).text() == "save_5 — Slot 5 — 7 arquivos .tres"
        assert empty_label.isVisible() is False

    def test_carregamento_inicial_vazio_mostra_empty_save_slots_label(
        self, qt_app: QApplication, save_slots_list: QListWidget, empty_label: QLabel
    ) -> None:
        """Verifica que lista vazia mostra o label de nenhum save."""
        render_save_slot_summaries([], save_slots_list, empty_label)

        assert save_slots_list.count() == 0
        assert empty_label.isVisible() is True

    def test_carregamento_inicial_vazio_esconde_save_slots_list(
        self, qt_app: QApplication, save_slots_list: QListWidget, empty_label: QLabel
    ) -> None:
        """Verifica que lista vazia esconde a lista de slots."""
        render_save_slot_summaries([], save_slots_list, empty_label)

        assert save_slots_list.isVisible() is False
        assert empty_label.isVisible() is True
