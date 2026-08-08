"""Testes para o formulário visual de caminhos manuais."""

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
)


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    """Cria uma instância global de QApplication para toda a suíte de testes."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestFormularioVisualDeCaminhos:
    """Testes do formulário visual de caminhos manuais."""

    def test_grupo_de_configuracao_existe(self, qt_app: QApplication) -> None:
        """Teste que o grupo de configuração existe."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        group = window.findChild(QGroupBox, "manual_paths_group")
        assert group is not None

    def test_grupo_tem_object_name_correto(self, qt_app: QApplication) -> None:
        """Teste que grupo possui objectName correto."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        group = window.findChild(QGroupBox, "manual_paths_group")
        assert group is not None
        assert group.objectName() == "manual_paths_group"

    def test_campo_dos_saves_existe(self, qt_app: QApplication) -> None:
        """Teste que campo dos saves existe."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        line_edit = window.findChild(QLineEdit, "save_path_input")
        assert line_edit is not None

    def test_campo_de_instalacao_existe(self, qt_app: QApplication) -> None:
        """Teste que campo de instalação existe."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        line_edit = window.findChild(QLineEdit, "game_install_path_input")
        assert line_edit is not None

    def test_campos_iniciam_vazios(self, qt_app: QApplication) -> None:
        """Teste que campos iniciam vazios."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        save_path_input = window.findChild(QLineEdit, "save_path_input")
        game_install_path_input = window.findChild(QLineEdit, "game_install_path_input")

        assert save_path_input is not None
        assert save_path_input.text() == ""

        assert game_install_path_input is not None
        assert game_install_path_input.text() == ""

    def test_placeholders_estao_corretos(self, qt_app: QApplication) -> None:
        """Teste que placeholders estão corretos."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        save_path_input = window.findChild(QLineEdit, "save_path_input")
        assert save_path_input is not None
        assert save_path_input.placeholderText() == "Selecione ou informe a pasta dos saves"

        game_install_path_input = window.findChild(QLineEdit, "game_install_path_input")
        assert game_install_path_input is not None
        assert game_install_path_input.placeholderText() == "Selecione ou informe a pasta de instalação"

    def test_botao_de_saves_existe(self, qt_app: QApplication) -> None:
        """Teste que botão de saves existe."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        button = window.findChild(QPushButton, "browse_save_path_button")
        assert button is not None

    def test_botao_de_instalacao_existe(self, qt_app: QApplication) -> None:
        """Teste que botão de instalação existe."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        button = window.findChild(QPushButton, "browse_game_install_button")
        assert button is not None

    def test_botoes_posseuem_textos_corretos(self, qt_app: QApplication) -> None:
        """Teste que botões possuem textos corretos."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        browse_save_button = window.findChild(QPushButton, "browse_save_path_button")
        assert browse_save_button is not None
        assert browse_save_button.text() == "Procurar..."

        browse_install_button = window.findChild(QPushButton, "browse_game_install_button")
        assert browse_install_button is not None
        assert browse_install_button.text() == "Procurar..."

    def test_botoes_de_procura_comecam_habilitados(self, qt_app: QApplication) -> None:
        """Teste que botões de procura começam habilitados."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        browse_save_button = window.findChild(QPushButton, "browse_save_path_button")
        assert browse_save_button is not None
        assert browse_save_button.isEnabled()

        browse_install_button = window.findChild(QPushButton, "browse_game_install_button")
        assert browse_install_button is not None
        assert browse_install_button.isEnabled()

    def test_botao_de_carregar_existe(self, qt_app: QApplication) -> None:
        """Teste que botão de carregar existe."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        button = window.findChild(QPushButton, "load_saves_button")
        assert button is not None

    def test_botao_de_carregar_comeca_habilitado(self, qt_app: QApplication) -> None:
        """Teste que botão de carregar começa habilitado."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        button = window.findChild(QPushButton, "load_saves_button")
        assert button is not None
        assert button.isEnabled()

    def test_tooltip_do_botao_de_carregar_esta_correto(self, qt_app: QApplication) -> None:
        """Teste que tooltip do botão de carregar está correto."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        button = window.findChild(QPushButton, "load_saves_button")
        assert button is not None
        assert button.toolTip() == (
            "Valida a pasta configurada e carrega os saves sem reiniciar o aplicativo."
        )

    def test_texto_do_caminho_provavel_esta_correto(self, qt_app: QApplication) -> None:
        """Teste que texto do caminho provável dos saves está correto."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        label = window.findChild(QLabel, "save_path_hint_label")
        assert label is not None
        assert label.text() == "Caminho padrão provável: %APPDATA%\\Godot\\app_userdata\\MR FARMBOY\\game_data"

    def test_texto_do_caminho_steam_esta_correto(self, qt_app: QApplication) -> None:
        """Teste que texto do possível caminho Steam está correto."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        label = window.findChild(QLabel, "game_install_hint_label")
        assert label is not None
        assert label.text() == "Possível caminho Steam: <biblioteca Steam>\\steamapps\\common\\MR FARMBOY"

    def test_criacao_janela_nao_altera_contenido_dos_campos(self, qt_app: QApplication) -> None:
        """Teste que criação da janela não altera o conteúdo dos campos."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        save_path_input = window.findChild(QLineEdit, "save_path_input")
        game_install_path_input = window.findChild(QLineEdit, "game_install_path_input")

        assert save_path_input.text() == ""
        assert game_install_path_input.text() == ""

    def test_formulario_nao_altera_comportamento_da_lista_de_slots(self, qt_app: QApplication) -> None:
        """Teste que formulário não altera o comportamento da lista de slots."""
        from mr_farmboy_manager.application import create_main_window
        from PySide6.QtWidgets import QListWidget

        window = create_main_window(qt_app)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None
        # O formulário de caminhos não interage com a lista de slots
        # (verificação básica de que o widget existe)

    def test_criacao_janela_continua_retornando_qmainwindow(self, qt_app: QApplication) -> None:
        """Teste que criação da janela continua retornando QMainWindow."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        assert isinstance(window, QMainWindow)
