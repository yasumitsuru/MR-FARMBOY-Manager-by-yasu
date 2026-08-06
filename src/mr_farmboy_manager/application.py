"""Aplicação principal do MR FARMBOY Manager."""

from __future__ import annotations

from collections.abc import Callable

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QLabel,
    QGroupBox,
)
from PySide6.QtCore import Qt

from mr_farmboy_manager.save_slots import SaveSlotSummary, build_save_slot_summaries


def create_application() -> QApplication:
    """Cria ou retorna uma instância da aplicação Qt.

    Consultará QApplication.instance() primeiro para reutilizar uma instância
    já existente, garantindo que apenas uma instância de QApplication exista
    por processo.

    Returns:
        Instância de QApplication (nova se não existir, ou a existente).
    """
    # Tenta reutilizar instância existente
    app = QApplication.instance()

    if app is None:
        # Cria nova instância apenas se não houver aplicação existente
        app = QApplication([])

    return app


SaveSlotsLoader = Callable[[], list[SaveSlotSummary]]


def create_main_window(
    app: QApplication | None = None,
    loader: SaveSlotsLoader | None = None,
) -> QMainWindow:
    """Cria a janela principal da aplicação.

    Args:
        app: Instância de QApplication opcional. Se None, será buscada automaticamente.
        loader: Função que retorna resumos de slots de save. Se None, usa build_save_slot_summaries.

    Returns:
        Instância de QMainWindow configurada com interface básica.
    """
    if app is None:
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication não disponível e não foi fornecida.")

    window = QMainWindow()
    window.setWindowTitle("MR FARMBOY Manager by yasu")
    window.resize(1000, 650)

    central_widget = QWidget()
    window.setCentralWidget(central_widget)

    layout = QVBoxLayout()
    central_widget.setLayout(layout)

    label_development = QLabel("Projeto em desenvolvimento")
    label_development.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label_development.setWordWrap(True)
    layout.addWidget(label_development)

    # Seção de slots de save
    save_slots_group = QGroupBox("Slots de Save")
    save_slots_group.setObjectName("save_slots_group")

    save_slots_layout = QVBoxLayout()
    save_slots_group.setLayout(save_slots_layout)

    empty_label = QLabel("Nenhum save encontrado")
    empty_label.setObjectName("empty_save_slots_label")
    empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    save_slots_layout.addWidget(empty_label)

    save_slots_list = QLabel()
    save_slots_list.setObjectName("save_slots_list")
    save_slots_list.setWordWrap(True)
    save_slots_layout.addWidget(save_slots_list)

    layout.addWidget(save_slots_group)

    # Carrega os resumos dos slots
    if loader is None:
        summaries = build_save_slot_summaries()
    else:
        summaries = loader()

    save_slots_list.setText("")

    for summary in summaries:
        line_text = f"save_{summary.slot.number} — Slot {summary.slot.number} — {summary.tres_file_count} arquivos .tres"
        label = QLabel(line_text)
        save_slots_layout.addWidget(label)

    if not summaries:
        empty_label.show()
        save_slots_list.hide()
    else:
        empty_label.hide()
        save_slots_list.show()

    return window


def run() -> int:
    """Inicializa e executa a aplicação.

    Returns:
        Código de saída da aplicação (0 para sucesso).
    """
    app = create_application()
    window = create_main_window(app)
    window.show()
    return app.exec()