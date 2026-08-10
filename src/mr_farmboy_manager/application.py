"""Aplicação principal do MR FARMBOY Manager."""

from __future__ import annotations

from collections.abc import Callable

import logging
import os
from datetime import timezone
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
    QPlainTextEdit,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import QSettings, QStandardPaths, Qt, QTimer

from mr_farmboy_manager.backups import (
    BackupCreationResult,
    BackupDeletionResult,
    BackupDiscoveryResult,
    BackupErrorCode,
    BackupRecord,
    BackupRestoreResult,
    create_backup,
    delete_backup,
    discover_backups,
    restore_backup,
)
from mr_farmboy_manager.manual_paths import (
    SaveSlotsLoadResult,
    DirectoryValidationCode,
    load_save_slot_summaries,
    validate_directory_path,
)
from mr_farmboy_manager.diagnostics import configure_logging
from mr_farmboy_manager.save_slots import (
    SaveSlot,
    SaveSlotSummary,
    build_save_slot_summaries,
)
from mr_farmboy_manager.save_details import SaveSlotDetails, inspect_save_slot
from mr_farmboy_manager.settings import AppSettings, QtSettingsStore, SettingsStore


LOGGER = logging.getLogger(__name__)
RUNTIME_ROOT_ENVIRONMENT_VARIABLE = "MR_FARMBOY_RUNTIME_ROOT"


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

    app.setOrganizationName("yasu")
    app.setApplicationName("MR FARMBOY Manager")

    return app


SaveSlotsLoader = Callable[[], list[SaveSlotSummary]]

SaveDetailsLoader = Callable[[SaveSlotSummary], SaveSlotDetails]

BackupCreator = Callable[[SaveSlot, Path, Path], BackupCreationResult]

BackupLoader = Callable[[Path], BackupDiscoveryResult]

BackupRestorer = Callable[..., BackupRestoreResult]

RestoreConfirmer = Callable[[BackupRecord], bool]

BackupDeleter = Callable[..., BackupDeletionResult]

DeleteConfirmer = Callable[[BackupRecord], bool]


ManualSaveLoader = Callable[[str], SaveSlotsLoadResult]


SaveSlotSelectedCallback = Callable[[SaveSlotSummary], None] | None


def default_backup_root() -> Path:
    """Retorna a pasta local privada do aplicativo para backups persistentes."""
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    if not base:
        raise RuntimeError("Diretório local do aplicativo indisponível.")
    return Path(base) / "backups"


def runtime_root_from_environment() -> Path | None:
    """Retorna um root portátil explícito para build, smoke e diagnóstico."""
    configured = os.environ.get(RUNTIME_ROOT_ENVIRONMENT_VARIABLE, "").strip()
    if not configured:
        return None
    return Path(configured).resolve(strict=False)


def format_file_size(size_bytes: int) -> str:
    """Formata uma quantidade não negativa para feedback compacto na UI."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KiB".replace(".", ",")
    return f"{size_bytes / (1024 * 1024):.1f} MiB".replace(".", ",")


def format_backup_record(record: BackupRecord) -> str:
    """Formata um resumo de backup sem reinterpretar seu manifesto."""
    created_at = record.created_at_utc.astimezone(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    plural = "arquivo" if record.file_count == 1 else "arquivos"
    return (
        f"Backup — Slot {record.slot_number} — {created_at} — "
        f"{record.file_count} {plural} — {format_file_size(record.total_size_bytes)} — "
        f"ID: {record.backup_id}"
    )


def format_save_slot_details(details: SaveSlotDetails) -> str:
    """Formata detalhes já inspecionados sem interpretar arquivos de save."""
    unavailable = "não disponível"
    modified = (
        details.latest_modified_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if details.latest_modified_at is not None
        else unavailable
    )
    failures = ", ".join(Path(name).name for name in details.failed_files) or "nenhuma"
    player = details.player_progress
    crops = details.crop_progress

    def value(item: object | None) -> str:
        return unavailable if item is None else str(item)

    lines = [
        "FICHA DO SLOT",
        f"Slot {details.summary.slot.number}",
        f"Caminho: {details.summary.slot.path}",
        f"Última modificação (UTC): {modified}",
        "",
        "ARQUIVOS ANALISADOS",
        f"Total .tres no slot: {details.summary.tres_file_count}",
        f"Arquivos principais analisados: {details.inspected_file_count}",
        f"Falhas: {failures}",
        f"Propriedades estruturadas: {details.total_property_count}",
        "",
        "PLAYER",
    ]
    if player is None:
        lines.append("Dados do player: não disponíveis")
    else:
        lines.extend(
            (
                f"Tutorial: {value(player.tutorial_stage)}",
                f"Modo do jogo (código): {value(player.game_mode_code)}",
                f"Ilha (código): {value(player.island_id)}",
                f"Destaques desbloqueados: {value(player.highlighted_unlock_count)}",
                f"Endless desbloqueados: {value(player.endless_unlock_count)}",
                f"Grupos de progresso: {value(player.advancement_group_count)}",
            )
        )
    lines.extend(("", "CULTIVOS"))
    if crops is None:
        lines.append("Dados de cultivos: indisponíveis")
    else:
        growth_states = (
            ", ".join(f"{code}: {count}" for code, count in crops.growth_state_counts)
            or unavailable
        )
        lines.extend(
            (
                f"Registros: {crops.record_count}",
                f"Plantados: {crops.planted_count}",
                f"Regados: {crops.watered_count}",
                f"Fertilizados: {crops.fertilized_count}",
                f"Maduros: {crops.matured_count}",
                f"Colhíveis: {crops.harvestable_count}",
                f"Mortos: {crops.dead_count}",
                f"Estados de crescimento: {growth_states}",
            )
        )
    lines.extend(
        (
            "",
            "Dados financeiros: não encontrados no schema analisado.",
            "Inventário detalhado: indisponível (formato opaco).",
        )
    )
    return "\n".join(lines)


def create_main_window(
    app: QApplication | None = None,
    loader: SaveSlotsLoader | None = None,
    on_slot_selected: SaveSlotSelectedCallback = None,
    save_directory_chooser: DirectoryChooser | None = None,
    game_install_directory_chooser: DirectoryChooser | None = None,
    manual_save_loader: ManualSaveLoader | None = None,
    settings_store: SettingsStore | None = None,
    save_details_loader: SaveDetailsLoader | None = None,
    backup_creator: BackupCreator | None = None,
    backup_loader: BackupLoader | None = None,
    backup_restorer: BackupRestorer | None = None,
    restore_confirmer: RestoreConfirmer | None = None,
    backup_deleter: BackupDeleter | None = None,
    delete_confirmer: DeleteConfirmer | None = None,
    backup_root: Path | str | None = None,
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

    save_path_status_label = QLabel()
    save_path_status_label.setObjectName("save_path_status_label")
    save_path_status_label.setWordWrap(True)
    manual_paths_layout.addWidget(save_path_status_label)

    browse_save_path_button = QPushButton("Procurar...")
    browse_save_path_button.setObjectName("browse_save_path_button")
    browse_save_path_button.setEnabled(True)
    manual_paths_layout.addWidget(browse_save_path_button)

    def choose_save_directory() -> None:
        if save_directory_chooser is not None:
            selected = save_directory_chooser()

            if selected is not None:
                save_path_input.setText(str(selected))
                update_save_path_status(save_path_input.text())
                on_load_saves_clicked()
            else:
                LOGGER.info("configuration.save_directory.cancelled")

            return

        selected_path = QFileDialog.getExistingDirectory(
            window,
            "Selecionar pasta dos saves",
            save_path_input.text(),
        )

        if selected_path:
            save_path_input.setText(selected_path)
            update_save_path_status(save_path_input.text())
            on_load_saves_clicked()
        else:
            LOGGER.info("configuration.save_directory.cancelled")

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

    game_install_path_status_label = QLabel()
    game_install_path_status_label.setObjectName("game_install_path_status_label")
    game_install_path_status_label.setWordWrap(True)
    manual_paths_layout.addWidget(game_install_path_status_label)

    current_settings = (
        settings_store.load() if settings_store is not None else AppSettings()
    )
    save_path_input.setText(current_settings.save_directory)
    game_install_path_input.setText(current_settings.game_install_directory)

    def status_text_for_directory(
        value: str, description: str, empty_text: str
    ) -> str:
        validation = validate_directory_path(value)
        messages = {
            DirectoryValidationCode.EMPTY: empty_text,
            DirectoryValidationCode.VALID: f"{description} válida.",
            DirectoryValidationCode.NOT_FOUND: (
                f"A {description.lower()} não existe. Corrija o caminho ou selecione uma pasta existente."
            ),
            DirectoryValidationCode.NOT_DIRECTORY: (
                f"O caminho da {description.lower()} não é uma pasta. Corrija o caminho."
            ),
        }
        return messages[validation.code]

    def update_save_path_status(value: str) -> None:
        save_path_status_label.setText(
            status_text_for_directory(
                value,
                "Pasta dos saves",
                "Nenhuma pasta dos saves configurada.",
            )
        )

    def update_game_install_path_status(value: str) -> None:
        game_install_path_status_label.setText(
            status_text_for_directory(
                value,
                "Pasta de instalação do jogo",
                "Nenhuma pasta de instalação do jogo configurada.",
            )
        )

    def persist_save_directory_if_valid(value: str) -> None:
        nonlocal current_settings
        validation = validate_directory_path(value)
        if settings_store is None or not validation.is_valid or validation.path is None:
            return

        current_settings = AppSettings(
            save_directory=str(validation.path),
            game_install_directory=current_settings.game_install_directory,
        )
        settings_store.save(current_settings)

    def persist_game_install_directory_if_valid(value: str) -> None:
        nonlocal current_settings
        validation = validate_directory_path(value)
        if settings_store is None or not validation.is_valid or validation.path is None:
            return

        current_settings = AppSettings(
            save_directory=current_settings.save_directory,
            game_install_directory=str(validation.path),
        )
        settings_store.save(current_settings)

    def on_save_path_editing_finished() -> None:
        update_save_path_status(save_path_input.text())
        on_load_saves_clicked()

    def on_game_install_path_editing_finished() -> None:
        update_game_install_path_status(game_install_path_input.text())
        persist_game_install_directory_if_valid(game_install_path_input.text())
        validation = validate_directory_path(game_install_path_input.text())
        LOGGER.info(
            "configuration.game_install_directory.changed code=%s",
            validation.code.name.lower(),
        )

    save_path_input.editingFinished.connect(on_save_path_editing_finished)

    browse_game_install_button = QPushButton("Procurar...")
    browse_game_install_button.setObjectName("browse_game_install_button")
    browse_game_install_button.setEnabled(True)
    manual_paths_layout.addWidget(browse_game_install_button)

    def choose_game_install_directory() -> None:
        if game_install_directory_chooser is not None:
            selected = game_install_directory_chooser()

            if selected is not None:
                game_install_path_input.setText(str(selected))
                update_game_install_path_status(game_install_path_input.text())
                persist_game_install_directory_if_valid(game_install_path_input.text())
                validation = validate_directory_path(game_install_path_input.text())
                LOGGER.info(
                    "configuration.game_install_directory.changed code=%s",
                    validation.code.name.lower(),
                )
            else:
                LOGGER.info("configuration.game_install_directory.cancelled")

            return

        selected_path = QFileDialog.getExistingDirectory(
            window,
            "Selecionar pasta de instalação do jogo",
            game_install_path_input.text(),
        )

        if selected_path:
            game_install_path_input.setText(selected_path)
            update_game_install_path_status(game_install_path_input.text())
            persist_game_install_directory_if_valid(game_install_path_input.text())
            validation = validate_directory_path(game_install_path_input.text())
            LOGGER.info(
                "configuration.game_install_directory.changed code=%s",
                validation.code.name.lower(),
            )
        else:
            LOGGER.info("configuration.game_install_directory.cancelled")

    browse_game_install_button.clicked.connect(choose_game_install_directory)
    game_install_path_input.editingFinished.connect(on_game_install_path_editing_finished)

    game_install_hint_label = QLabel("Possível caminho Steam: <biblioteca Steam>\\steamapps\\common\\MR FARMBOY")
    game_install_hint_label.setObjectName("game_install_hint_label")
    manual_paths_layout.addWidget(game_install_hint_label)

    # Carregamento manual de saves
    load_saves_button = QPushButton("Carregar saves")
    load_saves_button.setObjectName("load_saves_button")
    load_saves_button.setEnabled(True)
    load_saves_button.setToolTip(
        "Valida a pasta configurada e carrega os saves sem reiniciar o aplicativo."
    )
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
        applied = apply_manual_load_result(result)
        LOGGER.info(
            "configuration.save_directory.changed code=%s loaded=%s slots=%d",
            result.validation.code.name.lower(),
            applied,
            len(result.summaries),
        )

        if applied:
            active_manual_save_path = requested_path
            persist_save_directory_if_valid(requested_path)

    load_saves_button.clicked.connect(on_load_saves_clicked)

    layout.addWidget(manual_paths_group)

    # Seção de slots de save
    save_slots_group = QGroupBox("Slots de Save")
    save_slots_group.setObjectName("save_slots_group")

    save_slots_layout = QHBoxLayout()
    save_slots_group.setLayout(save_slots_layout)

    save_slots_list_layout = QVBoxLayout()
    save_slots_layout.addLayout(save_slots_list_layout)

    empty_label = QLabel("Nenhum save encontrado")
    empty_label.setObjectName("empty_save_slots_label")
    empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    empty_label.hide()
    save_slots_list_layout.addWidget(empty_label)

    save_slots_list = QListWidget()
    save_slots_list.setObjectName("save_slots_list")
    save_slots_list.hide()
    save_slots_list_layout.addWidget(save_slots_list)

    save_slot_details_group = QGroupBox("Detalhes do slot")
    save_slot_details_group.setObjectName("save_slot_details_group")
    save_slot_details_layout = QVBoxLayout(save_slot_details_group)

    save_slot_details_status_label = QLabel("Selecione um slot para consultar os detalhes.")
    save_slot_details_status_label.setObjectName("save_slot_details_status_label")
    save_slot_details_status_label.setWordWrap(True)
    save_slot_details_layout.addWidget(save_slot_details_status_label)

    save_slot_details_view = QPlainTextEdit()
    save_slot_details_view.setObjectName("save_slot_details_view")
    save_slot_details_view.setReadOnly(True)
    save_slot_details_view.setFont(
        QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    )
    save_slot_details_view.setMinimumHeight(190)
    save_slot_details_view.setMaximumHeight(220)
    save_slot_details_view.setPlainText("Selecione um slot para consultar os detalhes.")
    save_slot_details_layout.addWidget(save_slot_details_view)

    backup_group = QGroupBox("Backups")
    backup_group.setObjectName("backup_group")
    backup_layout = QVBoxLayout(backup_group)

    resolved_backup_root = (
        default_backup_root()
        if backup_root is None
        else Path(backup_root)
    )
    backup_root_label = QLabel(f"Destino dos backups: {resolved_backup_root}")
    backup_root_label.setObjectName("backup_root_label")
    backup_root_label.setWordWrap(True)
    backup_layout.addWidget(backup_root_label)

    backup_list_status_label = QLabel()
    backup_list_status_label.setObjectName("backup_list_status_label")
    backup_list_status_label.setWordWrap(True)
    backup_layout.addWidget(backup_list_status_label)

    empty_backups_label = QLabel("Nenhum backup criado")
    empty_backups_label.setObjectName("empty_backups_label")
    empty_backups_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    empty_backups_label.hide()
    backup_layout.addWidget(empty_backups_label)

    backups_list = QListWidget()
    backups_list.setObjectName("backups_list")
    backups_list.setMinimumHeight(100)
    backups_list.setMaximumHeight(150)
    backups_list.hide()
    backup_layout.addWidget(backups_list)

    create_backup_button = QPushButton("Criar backup do slot selecionado")
    create_backup_button.setObjectName("create_backup_button")
    create_backup_button.setEnabled(False)
    backup_layout.addWidget(create_backup_button)

    backup_status_label = QLabel("Selecione um slot para criar um backup.")
    backup_status_label.setObjectName("backup_status_label")
    backup_status_label.setWordWrap(True)
    backup_layout.addWidget(backup_status_label)

    restore_backup_button = QPushButton("Restaurar backup selecionado")
    restore_backup_button.setObjectName("restore_backup_button")
    restore_backup_button.setEnabled(False)
    backup_layout.addWidget(restore_backup_button)

    delete_backup_button = QPushButton("Excluir backup selecionado")
    delete_backup_button.setObjectName("delete_backup_button")
    delete_backup_button.setEnabled(False)
    backup_layout.addWidget(delete_backup_button)

    backup_management_status_label = QLabel(
        "Selecione um backup para restaurar ou excluir."
    )
    backup_management_status_label.setObjectName("backup_management_status_label")
    backup_management_status_label.setWordWrap(True)
    backup_layout.addWidget(backup_management_status_label)

    slot_side_layout = QVBoxLayout()
    slot_side_layout.addWidget(save_slot_details_group)
    slot_side_layout.addWidget(backup_group)
    save_slots_layout.addLayout(slot_side_layout)

    layout.addWidget(save_slots_group)

    # Carrega os resumos dos slots
    save_slots_loader = loader if loader is not None else build_save_slot_summaries
    summaries = save_slots_loader()

    # Armazena a lista de resumos para mapeamento com os itens da lista
    _summaries_for_selection: list[SaveSlotSummary] = summaries
    details_loader = save_details_loader if save_details_loader is not None else inspect_save_slot
    selected_summary: SaveSlotSummary | None = None
    effective_backup_creator = backup_creator if backup_creator is not None else create_backup
    effective_backup_loader = backup_loader if backup_loader is not None else discover_backups
    effective_backup_restorer = (
        backup_restorer if backup_restorer is not None else restore_backup
    )
    effective_backup_deleter = (
        backup_deleter if backup_deleter is not None else delete_backup
    )
    _backups_for_selection: list[BackupRecord] = []
    selected_backup: BackupRecord | None = None

    def active_summary_for_backup(
        record: BackupRecord,
    ) -> SaveSlotSummary | None:
        return next(
            (
                summary
                for summary in _summaries_for_selection
                if summary.slot.number == record.slot_number
            ),
            None,
        )

    def reset_backup_management() -> None:
        nonlocal selected_backup
        selected_backup = None
        restore_backup_button.setEnabled(False)
        delete_backup_button.setEnabled(False)
        backup_management_status_label.setText(
            "Selecione um backup para restaurar ou excluir."
        )

    def sync_backup_management_actions() -> None:
        record = selected_backup
        if record is None:
            restore_backup_button.setEnabled(False)
            delete_backup_button.setEnabled(False)
            return
        delete_backup_button.setEnabled(True)
        if active_summary_for_backup(record) is None:
            restore_backup_button.setEnabled(False)
            backup_management_status_label.setText(
                f"O save ativo do Slot {record.slot_number} não está disponível."
            )
            return
        restore_backup_button.setEnabled(True)
        backup_management_status_label.setText(
            f"Backup do Slot {record.slot_number} selecionado."
        )

    def apply_backup_discovery_result(result: BackupDiscoveryResult) -> None:
        nonlocal _backups_for_selection

        reset_backup_management()

        if not result.is_success:
            _backups_for_selection = []
            render_backup_records(empty_backups_label, backups_list, [])
            empty_backups_label.setText("Backups indisponíveis")
            backup_list_status_label.setText(result.public_message)
            return

        _backups_for_selection = list(result.backups)
        empty_backups_label.setText("Nenhum backup criado")
        render_backup_records(
            empty_backups_label,
            backups_list,
            _backups_for_selection,
        )
        backup_list_status_label.setText(result.public_message)

    def refresh_backups() -> None:
        try:
            result = effective_backup_loader(resolved_backup_root)
            apply_backup_discovery_result(result)
        except Exception:
            LOGGER.error("refresh.backups.failed")
            apply_backup_discovery_result(
                BackupDiscoveryResult(
                    backups=(),
                    invalid_entries=(),
                    error_code=BackupErrorCode.DISCOVERY_FAILED,
                    public_message="Não foi possível listar os backups.",
                )
            )
        else:
            LOGGER.info(
                "refresh.backups.completed success=%s backups=%d invalid=%d",
                result.is_success,
                len(result.backups),
                len(result.invalid_entries),
            )

    def reset_backup_action() -> None:
        nonlocal selected_summary
        selected_summary = None
        create_backup_button.setEnabled(False)
        backup_status_label.setText("Selecione um slot para criar um backup.")

    def reset_save_slot_details() -> None:
        reset_backup_action()
        save_slot_details_status_label.setText(
            "Selecione um slot para consultar os detalhes."
        )
        save_slot_details_view.setPlainText(
            "Selecione um slot para consultar os detalhes."
        )

    def replace_save_slot_summaries(new_summaries: list[SaveSlotSummary]) -> None:
        """Substitui os resumos renderizados e usados pela selecao."""
        nonlocal _summaries_for_selection

        _summaries_for_selection = new_summaries
        reset_save_slot_details()
        render_save_slot_summaries(empty_label, save_slots_list, new_summaries)
        sync_backup_management_actions()

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
            replace_save_slot_summaries([])
            empty_label.setText("Não foi possível carregar os saves.")
            return False

        empty_label.setText("Nenhum save encontrado")
        replace_save_slot_summaries(list(result.summaries))
        return True

    def on_item_selected() -> None:
        """Callback chamado quando um item é selecionado."""
        nonlocal selected_summary
        current_row = save_slots_list.currentRow()
        if current_row >= 0 and current_row < len(_summaries_for_selection):
            summary = _summaries_for_selection[current_row]
            selected_summary = summary
            create_backup_button.setEnabled(True)
            backup_status_label.setText(
                f"Slot {summary.slot.number} selecionado. Pronto para criar backup."
            )
            if on_slot_selected is not None:
                on_slot_selected(summary)
            LOGGER.info("parsing.started slot=%d", summary.slot.number)
            try:
                details = details_loader(summary)
                rendered_details = format_save_slot_details(details)
            except Exception:
                LOGGER.error("parsing.failed slot=%d", summary.slot.number)
                save_slot_details_status_label.setText(
                    "Não foi possível carregar os detalhes. Tente novamente com o jogo fechado."
                )
                save_slot_details_view.setPlainText(
                    "Detalhes indisponíveis. Tente novamente com o jogo fechado."
                )
                return

            LOGGER.info(
                "parsing.completed slot=%d inspected_files=%d failed_files=%d",
                summary.slot.number,
                details.inspected_file_count,
                len(details.failed_files),
            )
            save_slot_details_status_label.setText("Detalhes carregados.")
            save_slot_details_view.setPlainText(rendered_details)
            return

        reset_save_slot_details()

    def on_backup_selected() -> None:
        nonlocal selected_backup
        current_row = backups_list.currentRow()
        if current_row < 0 or current_row >= len(_backups_for_selection):
            reset_backup_management()
            return

        selected_backup = _backups_for_selection[current_row]
        sync_backup_management_actions()

    def confirm_restore(record: BackupRecord) -> bool:
        if restore_confirmer is not None:
            return restore_confirmer(record)

        created_at = record.created_at_utc.astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        answer = QMessageBox.warning(
            window,
            "Confirmar restauração",
            "Esta ação substituirá o save ativo após criar um backup preventivo.\n\n"
            f"Slot: {record.slot_number}\n"
            f"Data do backup: {created_at}\n"
            f"Tamanho: {format_file_size(record.total_size_bytes)}\n"
            f"ID: {record.backup_id}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def confirm_delete(record: BackupRecord) -> bool:
        if delete_confirmer is not None:
            return delete_confirmer(record)

        created_at = record.created_at_utc.astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        answer = QMessageBox.warning(
            window,
            "Confirmar exclusão",
            "Esta ação excluirá permanentemente o backup selecionado.\n\n"
            f"Slot: {record.slot_number}\n"
            f"Data do backup: {created_at}\n"
            f"Tamanho: {format_file_size(record.total_size_bytes)}\n"
            f"ID: {record.backup_id}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def on_restore_backup_clicked() -> None:
        record = selected_backup
        if record is None:
            reset_backup_management()
            return

        summary = active_summary_for_backup(record)
        if summary is None:
            restore_backup_button.setEnabled(False)
            backup_management_status_label.setText(
                f"O save ativo do Slot {record.slot_number} não está disponível."
            )
            LOGGER.warning(
                "backup.restore.rejected slot=%d reason=active_save_missing",
                record.slot_number,
            )
            return
        if not confirm_restore(record):
            backup_management_status_label.setText("Restauração cancelada.")
            LOGGER.info("backup.restore.cancelled slot=%d", record.slot_number)
            return

        restore_backup_button.setEnabled(False)
        LOGGER.info("backup.restore.started slot=%d", record.slot_number)
        backup_management_status_label.setText(
            f"Restaurando backup do Slot {record.slot_number}..."
        )
        try:
            result = effective_backup_restorer(
                summary.slot,
                summary.slot.path.parent,
                resolved_backup_root,
                record.backup_id,
                confirmed=True,
            )
        except Exception:
            LOGGER.error("backup.restore.failed slot=%d", record.slot_number)
            backup_management_status_label.setText(
                "Não foi possível restaurar o backup. Feche o jogo e tente novamente."
            )
        else:
            if result.is_success:
                refresh_backups()
                refresh_save_slots()
                LOGGER.info("backup.restore.completed slot=%d", record.slot_number)
            else:
                error_code = (
                    result.error_code.value
                    if result.error_code is not None
                    else "unknown"
                )
                LOGGER.warning(
                    "backup.restore.failed slot=%d code=%s",
                    record.slot_number,
                    error_code,
                )
            backup_management_status_label.setText(result.public_message)
        finally:
            if selected_backup is not None:
                restore_backup_button.setEnabled(
                    active_summary_for_backup(selected_backup) is not None
                )

    def on_delete_backup_clicked() -> None:
        record = selected_backup
        if record is None:
            reset_backup_management()
            return
        if not confirm_delete(record):
            backup_management_status_label.setText("Exclusão cancelada.")
            LOGGER.info("backup.delete.cancelled slot=%d", record.slot_number)
            return

        delete_backup_button.setEnabled(False)
        LOGGER.info("backup.delete.started slot=%d", record.slot_number)
        backup_management_status_label.setText(
            f"Excluindo backup do Slot {record.slot_number}..."
        )
        try:
            result = effective_backup_deleter(
                resolved_backup_root,
                record.backup_id,
                confirmed=True,
            )
        except Exception:
            LOGGER.error("backup.delete.failed slot=%d", record.slot_number)
            backup_management_status_label.setText(
                "Não foi possível excluir o backup."
            )
        else:
            if result.is_success:
                refresh_backups()
                LOGGER.info("backup.delete.completed slot=%d", record.slot_number)
            else:
                error_code = (
                    result.error_code.value
                    if result.error_code is not None
                    else "unknown"
                )
                LOGGER.warning(
                    "backup.delete.failed slot=%d code=%s",
                    record.slot_number,
                    error_code,
                )
            backup_management_status_label.setText(result.public_message)
        finally:
            if selected_backup is not None:
                delete_backup_button.setEnabled(True)
                restore_backup_button.setEnabled(
                    active_summary_for_backup(selected_backup) is not None
                )

    def on_create_backup_clicked() -> None:
        summary = selected_summary
        if summary is None:
            reset_backup_action()
            return

        create_backup_button.setEnabled(False)
        LOGGER.info("backup.create.started slot=%d", summary.slot.number)
        backup_status_label.setText(
            f"Criando backup do slot {summary.slot.number}..."
        )
        try:
            result = effective_backup_creator(
                summary.slot,
                summary.slot.path.parent,
                resolved_backup_root,
            )
        except Exception:
            LOGGER.error("backup.create.failed slot=%d", summary.slot.number)
            backup_status_label.setText(
                "Não foi possível criar o backup. Feche o jogo e tente novamente."
            )
        else:
            if result.is_success and result.backup is not None:
                record = result.backup
                plural = "arquivo" if record.file_count == 1 else "arquivos"
                backup_status_label.setText(
                    f"Backup {record.backup_id} criado com sucesso: "
                    f"{record.file_count} {plural}, "
                    f"{format_file_size(record.total_size_bytes)}."
                )
                refresh_backups()
                LOGGER.info("backup.create.completed slot=%d", summary.slot.number)
            else:
                error_code = (
                    result.error_code.value
                    if result.error_code is not None
                    else "unknown"
                )
                LOGGER.warning(
                    "backup.create.failed slot=%d code=%s",
                    summary.slot.number,
                    error_code,
                )
                backup_status_label.setText(result.public_message)
        finally:
            create_backup_button.setEnabled(selected_summary is not None)

    save_slots_list.itemSelectionChanged.connect(on_item_selected)
    backups_list.itemSelectionChanged.connect(on_backup_selected)
    create_backup_button.clicked.connect(on_create_backup_clicked)
    restore_backup_button.clicked.connect(on_restore_backup_clicked)
    delete_backup_button.clicked.connect(on_delete_backup_clicked)

    render_save_slot_summaries(empty_label, save_slots_list, summaries)
    LOGGER.info("refresh.saves.completed source=initial slots=%d", len(summaries))
    refresh_backups()
    update_save_path_status(save_path_input.text())
    update_game_install_path_status(game_install_path_input.text())

    if current_settings.save_directory:
        restored_save_path = current_settings.save_directory
        restored_validation = validate_directory_path(restored_save_path)
        restored_result = load_manual_summaries(restored_save_path)
        effective_restored_result = (
            restored_result
            if restored_validation.is_valid
            else SaveSlotsLoadResult(restored_validation, ())
        )
        if (
            apply_manual_load_result(effective_restored_result)
            and restored_validation.is_valid
        ):
            active_manual_save_path = restored_save_path

    def refresh_save_slots() -> None:
        try:
            if active_manual_save_path is None:
                refreshed_summaries = save_slots_loader()
                replace_save_slot_summaries(refreshed_summaries)
                LOGGER.info(
                    "refresh.saves.completed source=default slots=%d",
                    len(refreshed_summaries),
                )
                return

            result = load_manual_summaries(active_manual_save_path)
            applied = apply_manual_load_result(result)
            LOGGER.info(
                "refresh.saves.completed source=manual success=%s slots=%d",
                applied,
                len(result.summaries),
            )
        except Exception:
            LOGGER.error("refresh.saves.failed")
            raise

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


def render_backup_records(
    empty_label: QLabel,
    backups_list: QListWidget,
    records: list[BackupRecord],
) -> None:
    """Renderiza backups já descobertos, preservando sua ordenação."""
    if not records:
        backups_list.clear()
        empty_label.show()
        backups_list.hide()
        return

    empty_label.hide()
    backups_list.show()
    backups_list.clear()
    for record in records:
        backups_list.addItem(QListWidgetItem(format_backup_record(record)))


def run() -> int:
    """Inicializa e executa a aplicação.

    Returns:
        Código de saída da aplicação (0 para sucesso).
    """
    app = create_application()
    runtime_root = runtime_root_from_environment()
    configure_logging(runtime_root / "logs" if runtime_root is not None else None)
    LOGGER.info("application.startup")
    if runtime_root is None:
        settings_store = QtSettingsStore()
        backup_root = None
    else:
        settings_store = QtSettingsStore(
            QSettings(
                str(runtime_root / "settings.ini"),
                QSettings.Format.IniFormat,
            )
        )
        backup_root = runtime_root / "backups"
    window = create_main_window(
        app,
        settings_store=settings_store,
        backup_root=backup_root,
    )
    window.show()
    LOGGER.info("application.ready")
    exit_code = app.exec()
    LOGGER.info("application.shutdown exit_code=%d", exit_code)
    return exit_code
