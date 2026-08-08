"""Aplicação principal do MR FARMBOY Manager."""

from __future__ import annotations

from collections.abc import Callable

from pathlib import Path

DirectoryChooser = Callable[[], Path | None]

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QGroupBox,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
)
from PySide6.QtCore import Qt, QTimer

from mr_farmboy_manager.manual_paths import SaveSlotsLoadResult, DirectoryValidationCode, load_save_slot_summaries
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


ManualSaveLoader = Callable[[str], SaveSlotsLoadResult]


SaveSlotSelectedCallback = Callable[[SaveSlotSummary], None] | None


def create_main_window(
    app: QApplication | None = None,
    loader: SaveSlotsLoader | None = None,
    on_slot_selected: SaveSlotSelectedCallback = None,
    save_directory_chooser: DirectoryChooser | None = None,
    game_install_directory_chooser: DirectoryChooser | None = None,
    manual_save_loader: ManualSaveLoader | None = None,
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

    # Seção de configuração de caminhos manuais
    manual_paths_group = QGroupBox("Configuração de caminhos")
    manual_paths_group.setObjectName("manual_paths_group")

    manual_paths_layout = QVBoxLayout()
    manual_paths_group.setLayout(manual_paths_layout)

    # Pasta dos saves
    save_path_label = QLabel("Pasta dos saves")
    manual_paths_layout.addWidget(save_path_label)

    save_path_input = QLineEdit()
    save_path_input.setObjectName("save_path_input")
    save_path_input.setPlaceholderText("Selecione ou informe a pasta dos saves")
    manual_paths_layout.addWidget(save_path_input)

    browse_save_path_button = QPushButton("Procurar...")
    browse_save_path_button.setObjectName("browse_save_path_button")
    browse_save_path_button.setEnabled(True)
    manual_paths_layout.addWidget(browse_save_path_button)

    def choose_save_directory() -> None:
        if save_directory_chooser is not None:
            selected = save_directory_chooser()

            if selected is not None:
                save_path_input.setText(str(selected))

            return

        selected_path = QFileDialog.getExistingDirectory(
            window,
            "Selecionar pasta dos saves",
            save_path_input.text(),
        )

        if selected_path:
            save_path_input.setText(selected_path)

    browse_save_path_button.clicked.connect(choose_save_directory)

    save_path_hint_label = QLabel("Caminho padrão provável: %APPDATA%\\Godot\\app_userdata\\MR FARMBOY\\game_data")
    save_path_hint_label.setObjectName("save_path_hint_label")
    manual_paths_layout.addWidget(save_path_hint_label)

    # Pasta de instalação do jogo
    game_install_path_label = QLabel("Pasta de instalação do jogo")
    manual_paths_layout.addWidget(game_install_path_label)

    game_install_path_input = QLineEdit()
    game_install_path_input.setObjectName("game_install_path_input")
    game_install_path_input.setPlaceholderText("Selecione ou informe a pasta de instalação")
    manual_paths_layout.addWidget(game_install_path_input)

    browse_game_install_button = QPushButton("Procurar...")
    browse_game_install_button.setObjectName("browse_game_install_button")
    browse_game_install_button.setEnabled(True)
    manual_paths_layout.addWidget(browse_game_install_button)

    def choose_game_install_directory() -> None:
        if game_install_directory_chooser is not None:
            selected = game_install_directory_chooser()

            if selected is not None:
                game_install_path_input.setText(str(selected))

            return

        selected_path = QFileDialog.getExistingDirectory(
            window,
            "Selecionar pasta de instalação do jogo",
            game_install_path_input.text(),
        )

        if selected_path:
            game_install_path_input.setText(selected_path)

    browse_game_install_button.clicked.connect(choose_game_install_directory)

    game_install_hint_label = QLabel("Possível caminho Steam: <biblioteca Steam>\\steamapps\\common\\MR FARMBOY")
    game_install_hint_label.setObjectName("game_install_hint_label")
    manual_paths_layout.addWidget(game_install_hint_label)

    # Botão de ação futuro
    load_saves_button = QPushButton("Carregar saves")
    load_saves_button.setObjectName("load_saves_button")
    load_saves_button.setEnabled(True)
    load_saves_button.setToolTip("O carregamento será habilitado após a integração com a validação de caminhos.")
    manual_paths_layout.addWidget(load_saves_button)

    active_manual_save_path: str | None = None

    def load_manual_summaries(path: str) -> SaveSlotsLoadResult:
        if manual_save_loader is not None:
            return manual_save_loader(path)

        return load_save_slot_summaries(path)

    def on_load_saves_clicked() -> None:
        nonlocal active_manual_save_path

        requested_path = save_path_input.text()
        result = load_manual_summaries(requested_path)

        if apply_manual_load_result(result):
            active_manual_save_path = requested_path

    load_saves_button.clicked.connect(on_load_saves_clicked)

    layout.addWidget(manual_paths_group)

    # Seção de slots de save
    save_slots_group = QGroupBox("Slots de Save")
    save_slots_group.setObjectName("save_slots_group")

    save_slots_layout = QVBoxLayout()
    save_slots_group.setLayout(save_slots_layout)

    empty_label = QLabel("Nenhum save encontrado")
    empty_label.setObjectName("empty_save_slots_label")
    empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    empty_label.hide()
    save_slots_layout.addWidget(empty_label)

    save_slots_list = QListWidget()
    save_slots_list.setObjectName("save_slots_list")
    save_slots_list.hide()
    save_slots_layout.addWidget(save_slots_list)

    layout.addWidget(save_slots_group)

    # Carrega os resumos dos slots
    save_slots_loader = loader if loader is not None else build_save_slot_summaries
    summaries = save_slots_loader()

    # Armazena a lista de resumos para mapeamento com os itens da lista
    _summaries_for_selection: list[SaveSlotSummary] = summaries

    def replace_save_slot_summaries(new_summaries: list[SaveSlotSummary]) -> None:
        """Substitui os resumos renderizados e usados pela selecao."""
        nonlocal _summaries_for_selection

        _summaries_for_selection = new_summaries
        render_save_slot_summaries(empty_label, save_slots_list, new_summaries)

    def apply_manual_load_result(result: SaveSlotsLoadResult) -> bool:
        """Aplica um resultado manual e informa se ele e valido."""
        error_messages = {
            DirectoryValidationCode.EMPTY: "Informe a pasta dos saves.",
            DirectoryValidationCode.NOT_FOUND: "A pasta dos saves não existe.",
            DirectoryValidationCode.NOT_DIRECTORY: "O caminho dos saves não é uma pasta.",
        }
        error_message = error_messages.get(result.validation.code)

        if error_message is not None:
            replace_save_slot_summaries([])
            empty_label.setText(error_message)
            return False

        if not result.is_success:
            return False

        empty_label.setText("Nenhum save encontrado")
        replace_save_slot_summaries(list(result.summaries))
        return True

    def on_item_selected():
        """Callback chamado quando um item é selecionado."""
        current_row = save_slots_list.currentRow()
        if current_row >= 0 and current_row < len(_summaries_for_selection):
            summary = _summaries_for_selection[current_row]
            if on_slot_selected is not None:
                on_slot_selected(summary)

    save_slots_list.itemSelectionChanged.connect(on_item_selected)

    render_save_slot_summaries(empty_label, save_slots_list, summaries)

    def refresh_save_slots() -> None:
        if active_manual_save_path is None:
            replace_save_slot_summaries(save_slots_loader())
            return

        result = load_manual_summaries(active_manual_save_path)
        apply_manual_load_result(result)

    auto_refresh_timer = QTimer(window)
    auto_refresh_timer.setObjectName("save_auto_refresh_timer")
    auto_refresh_timer.setInterval(300_000)
    auto_refresh_timer.timeout.connect(refresh_save_slots)
    auto_refresh_timer.start()

    return window


def render_save_slot_summaries(
    empty_label: QLabel,
    save_slots_list: QListWidget,
    summaries_to_render: list[SaveSlotSummary],
) -> None:
    """Renderiza os resumos dos slots de save na interface.

    Args:
        empty_label: Label a ser mostrado quando não há saves.
        save_slots_list: Lista de widgets onde os slots serão exibidos.
        summaries_to_render: Lista de resumos a serem renderizados.
    """
    if not summaries_to_render:
        save_slots_list.clear()
        empty_label.show()
        save_slots_list.hide()
        return

    empty_label.hide()
    save_slots_list.show()
    save_slots_list.clear()

    for summary in summaries_to_render:
        line_text = (
            f"save_{summary.slot.number} — "
            f"Slot {summary.slot.number} — "
            f"{summary.tres_file_count} arquivos .tres"
        )
        save_slots_list.addItem(QListWidgetItem(line_text))


def run() -> int:
    """Inicializa e executa a aplicação.

    Returns:
        Código de saída da aplicação (0 para sucesso).
    """
    app = create_application()
    window = create_main_window(app)
    window.show()
    return app.exec()
