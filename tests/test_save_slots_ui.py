"""Testes para a interface de slots de save."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QGroupBox, QVBoxLayout, QListWidget


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    """Cria uma instância global de QApplication para toda a suíte de testes."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestSaveSlotsUI:
    """Testes da interface de slots de save."""

    def test_janela_criada_com_loader_vazio(self, qt_app: QApplication) -> None:
        """Teste que janela é criada com loader vazio."""
        from mr_farmboy_manager.application import create_main_window

        def empty_loader() -> list:
            return []

        window = create_main_window(qt_app, loader=empty_loader)
        assert isinstance(window, QMainWindow)

    def test_loader_chamado_exatamente_uma_vez(self, qt_app: QApplication) -> None:
        """Teste que loader é chamado exatamente uma vez."""
        from mr_farmboy_manager.application import create_main_window

        call_count = 0

        def counting_loader() -> list:
            nonlocal call_count
            call_count += 1
            return []

        window = create_main_window(qt_app, loader=counting_loader)
        assert call_count == 1

    def test_estado_vazio_exibido(self, qt_app: QApplication) -> None:
        """Teste que estado vazio é exibido."""
        from mr_farmboy_manager.application import create_main_window

        def empty_loader() -> list:
            return []

        window = create_main_window(qt_app, loader=empty_loader)
        labels = window.findChildren(QLabel)

        texts = [label.text() for label in labels]
        assert "Nenhum save encontrado" in texts

    def test_save_1_exibido(self, qt_app: QApplication) -> None:
        """Teste que save_1 é exibido."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot = SaveSlot(number=1, path=Path("save_1"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        def loader() -> list:
            return [summary]

        window = create_main_window(qt_app, loader=loader)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None

        item = save_slots_list.item(0)
        assert item is not None
        text = item.text()
        assert "save_1" in text

    def test_numero_do_slot_exibido(self, qt_app: QApplication) -> None:
        """Teste que número do slot é exibido."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot = SaveSlot(number=5, path=Path("save_5"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        def loader() -> list:
            return [summary]

        window = create_main_window(qt_app, loader=loader)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None

        item = save_slots_list.item(0)
        assert item is not None
        text = item.text()
        assert "Slot 5" in text

    def test_contagem_de_tres_exibida(self, qt_app: QApplication) -> None:
        """Teste que contagem de .tres é exibida."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot = SaveSlot(number=1, path=Path("save_1"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        def loader() -> list:
            return [summary]

        window = create_main_window(qt_app, loader=loader)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None

        item = save_slots_list.item(0)
        assert item is not None
        text = item.text()
        assert "4 arquivos .tres" in text

    def test_multiplos_resumos_mantem_ordem(self, qt_app: QApplication) -> None:
        """Teste que múltiplos resumos mantêm a ordem recebida."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot_1 = SaveSlot(number=3, path=Path("save_3"))
        slot_2 = SaveSlot(number=1, path=Path("save_1"))
        slot_3 = SaveSlot(number=2, path=Path("save_2"))

        summaries = [
            SaveSlotSummary(slot=slot_1, tres_file_count=4),
            SaveSlotSummary(slot=slot_2, tres_file_count=4),
            SaveSlotSummary(slot=slot_3, tres_file_count=4),
        ]

        def loader() -> list:
            return summaries

        window = create_main_window(qt_app, loader=loader)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None

        items = [save_slots_list.item(i) for i in range(save_slots_list.count())]
        texts = [item.text() for item in items if item is not None]

        assert "save_3" in texts[0]
        assert "save_1" in texts[1]
        assert "save_2" in texts[2]

    def test_estado_vazio_nao_aparece_com_resumos(self, qt_app: QApplication) -> None:
        """Teste que estado vazio não aparece quando existem resumos."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot = SaveSlot(number=1, path=Path("save_1"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        def loader() -> list:
            return [summary]

        window = create_main_window(qt_app, loader=loader)

        empty_label = window.findChild(QLabel, "empty_save_slots_label")
        assert empty_label is not None
        assert empty_label.isHidden()

    def test_widgets_tem_object_names(self, qt_app: QApplication) -> None:
        """Teste que widgets possuem os objectName definidos."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot = SaveSlot(number=1, path=Path("save_1"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        def loader() -> list:
            return [summary]

        window = create_main_window(qt_app, loader=loader)

        group = window.findChild(QGroupBox, "save_slots_group")
        assert group is not None

    def test_lista_e_vazia_com_loader_vazio(self, qt_app: QApplication) -> None:
        """Teste que lista é vazia quando loader retorna []."""
        from mr_farmboy_manager.application import create_main_window

        def empty_loader() -> list:
            return []

        window = create_main_window(qt_app, loader=empty_loader)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None
        assert save_slots_list.count() == 0

    def test_lista_contem_um_item_por_resumo(self, qt_app: QApplication) -> None:
        """Teste que lista contém um item por resumo."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot_1 = SaveSlot(number=1, path=Path("save_1"))
        slot_2 = SaveSlot(number=2, path=Path("save_2"))

        summaries = [
            SaveSlotSummary(slot=slot_1, tres_file_count=3),
            SaveSlotSummary(slot=slot_2, tres_file_count=5),
        ]

        def loader() -> list:
            return summaries

        window = create_main_window(qt_app, loader=loader)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None
        assert save_slots_list.count() == 2

    def test_texto_de_cada_item_contem_nome_numero_e_contagem(self, qt_app: QApplication) -> None:
        """Teste que texto de cada item contém nome, número e contagem."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot = SaveSlot(number=3, path=Path("save_3"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=7)

        def loader() -> list:
            return [summary]

        window = create_main_window(qt_app, loader=loader)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None

        item = save_slots_list.item(0)
        assert item is not None
        text = item.text()
        assert "save_3" in text
        assert "Slot 3" in text
        assert "7 arquivos .tres" in text

    def test_ordem_dos_itens_corresponde_a_ordem_recebida(self, qt_app: QApplication) -> None:
        """Teste que ordem dos itens corresponde à ordem recebida."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot_a = SaveSlot(number=10, path=Path("save_10"))
        slot_b = SaveSlot(number=2, path=Path("save_2"))
        slot_c = SaveSlot(number=5, path=Path("save_5"))

        summaries = [
            SaveSlotSummary(slot=slot_a, tres_file_count=1),
            SaveSlotSummary(slot=slot_b, tres_file_count=2),
            SaveSlotSummary(slot=slot_c, tres_file_count=3),
        ]

        def loader() -> list:
            return summaries

        window = create_main_window(qt_app, loader=loader)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None

        items = [save_slots_list.item(i) for i in range(save_slots_list.count())]
        texts = [item.text() for item in items if item is not None]

        assert "save_10" in texts[0]
        assert "save_2" in texts[1]
        assert "save_5" in texts[2]

    def test_nenhum_item_selecionado_automaticamente(self, qt_app: QApplication) -> None:
        """Teste que nenhum item é selecionado automaticamente."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot = SaveSlot(number=1, path=Path("save_1"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        def loader() -> list:
            return [summary]

        window = create_main_window(qt_app, loader=loader)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None

        # Verifica que nenhum item está selecionado (currentRow deve ser -1)
        current_row = save_slots_list.currentRow()
        assert current_row == -1

    def test_callback_nao_e_chamado_durante_criacao(self, qt_app: QApplication) -> None:
        """Teste que callback não é chamado durante criação."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        call_count = 0

        def counting_callback(summary: SaveSlotSummary) -> None:
            nonlocal call_count
            call_count += 1

        def loader() -> list:
            return [SaveSlotSummary(slot=SaveSlot(number=1, path=Path("save_1")), tres_file_count=4)]

        window = create_main_window(qt_app, loader=loader, on_slot_selected=counting_callback)

        assert call_count == 0

    def test_selecionar_primeiro_item_chama_callback_com_primeiro_resumo(self, qt_app: QApplication) -> None:
        """Teste que selecionar o primeiro item chama callback com o primeiro resumo."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot_1 = SaveSlot(number=1, path=Path("save_1"))
        slot_2 = SaveSlot(number=2, path=Path("save_2"))

        summary_1 = SaveSlotSummary(slot=slot_1, tres_file_count=4)
        summary_2 = SaveSlotSummary(slot=slot_2, tres_file_count=5)

        received_summary: SaveSlotSummary | None = None

        def callback(summary: SaveSlotSummary) -> None:
            nonlocal received_summary
            received_summary = summary

        def loader() -> list:
            return [summary_1, summary_2]

        window = create_main_window(qt_app, loader=loader, on_slot_selected=callback)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None

        save_slots_list.setCurrentRow(0)
        qt_app.processEvents()

        assert received_summary is not None
        assert received_summary == summary_1

    def test_selecionar_outro_item_chama_callback_com_resumo_correspondente(self, qt_app: QApplication) -> None:
        """Teste que selecionar outro item chama callback com o resumo correspondente."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot_1 = SaveSlot(number=1, path=Path("save_1"))
        slot_2 = SaveSlot(number=2, path=Path("save_2"))
        slot_3 = SaveSlot(number=3, path=Path("save_3"))

        summary_1 = SaveSlotSummary(slot=slot_1, tres_file_count=4)
        summary_2 = SaveSlotSummary(slot=slot_2, tres_file_count=5)
        summary_3 = SaveSlotSummary(slot=slot_3, tres_file_count=6)

        received_summary: SaveSlotSummary | None = None

        def callback(summary: SaveSlotSummary) -> None:
            nonlocal received_summary
            received_summary = summary

        def loader() -> list:
            return [summary_1, summary_2, summary_3]

        window = create_main_window(qt_app, loader=loader, on_slot_selected=callback)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None

        # Seleciona o terceiro item (índice 2)
        save_slots_list.setCurrentRow(2)
        qt_app.processEvents()

        assert received_summary is not None
        assert received_summary == summary_3

    def test_callback_recebe_o_mesmo_objeto_save_slot_summary(self, qt_app: QApplication) -> None:
        """Teste que callback recebe o mesmo objeto SaveSlotSummary."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot = SaveSlot(number=1, path=Path("save_1"))
        original_summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        received_summary: SaveSlotSummary | None = None

        def callback(summary: SaveSlotSummary) -> None:
            nonlocal received_summary
            received_summary = summary

        def loader() -> list:
            return [original_summary]

        window = create_main_window(qt_app, loader=loader, on_slot_selected=callback)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None

        save_slots_list.setCurrentRow(0)
        qt_app.processEvents()

        assert received_summary is not None
        assert received_summary is original_summary

    def test_absencia_de_callback_nao_causa_erro(self, qt_app: QApplication) -> None:
        """Teste que ausência de callback não causa erro."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot = SaveSlot(number=1, path=Path("save_1"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        def loader() -> list:
            return [summary]

        # Chama sem on_slot_selected
        window = create_main_window(qt_app, loader=loader)

        assert window is not None

    def test_loader_injetado_continua_sendo_chamado_uma_unica_vez(self, qt_app: QApplication) -> None:
        """Teste que loader injetado continua sendo chamado uma única vez."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        call_count = 0

        def counting_loader() -> list:
            nonlocal call_count
            call_count += 1
            return [SaveSlotSummary(slot=SaveSlot(number=1, path=Path("save_1")), tres_file_count=4)]

        window = create_main_window(qt_app, loader=counting_loader)

        assert call_count == 1

    def test_loader_padrao_nao_e_chamado_quando_loader_injetado_existente(self, qt_app: QApplication) -> None:
        """Teste que loader padrão não é chamado quando loader injetado existe."""
        from mr_farmboy_manager.application import create_main_window, build_save_slot_summaries

        original_build = build_save_slot_summaries
        call_count = 0

        def counting_wrapper() -> list:
            nonlocal call_count
            call_count += 1
            return []

        # Substitui temporariamente para contar chamadas do padrão
        import mr_farmboy_manager.application as app_module
        original_build_func = app_module.build_save_slot_summaries
        app_module.build_save_slot_summaries = counting_wrapper

        try:
            def loader() -> list:
                return []

            window = create_main_window(qt_app, loader=loader)

            assert call_count == 0
        finally:
            app_module.build_save_slot_summaries = original_build_func

    def test_item_por_item_contem_texto_completo_esperado(self, qt_app: QApplication) -> None:
        """Teste que cada item contém o texto completo esperado."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        slot = SaveSlot(number=7, path=Path("save_7"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=12)

        def loader() -> list:
            return [summary]

        window = create_main_window(qt_app, loader=loader)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None

        item = save_slots_list.item(0)
        assert item is not None
        text = item.text()

        # Verifica o formato exato esperado
        expected_text = "save_7 — Slot 7 — 12 arquivos .tres"
        assert text == expected_text

    def test_callback_chamado_exatamente_uma_vez_por_mudanca_de_selecao(self, qt_app: QApplication) -> None:
        """Teste que callback é chamado exatamente uma vez por mudança de seleção."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

        call_count = 0

        def counting_callback(summary: SaveSlotSummary) -> None:
            nonlocal call_count
            call_count += 1

        slot = SaveSlot(number=1, path=Path("save_1"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=4)

        def loader() -> list:
            return [summary]

        window = create_main_window(qt_app, loader=loader, on_slot_selected=counting_callback)

        save_slots_list = window.findChild(QListWidget, "save_slots_list")
        assert save_slots_list is not None

        # Seleciona o item (deve chamar uma vez)
        save_slots_list.setCurrentRow(0)
        qt_app.processEvents()
        assert call_count == 1

        # Seleciona novamente o mesmo item (não deve chamar mais)
        save_slots_list.setCurrentRow(0)
        qt_app.processEvents()
        assert call_count == 1
