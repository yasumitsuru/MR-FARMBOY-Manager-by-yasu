"""Testes para o módulo save_slot_summaries - Tarefa 3.2."""

from pathlib import Path

import pytest

from mr_farmboy_manager.save_slots import (
    SaveSlot,
    SaveSlotSummary,
    build_save_slot_summaries,
)


class TestSaveSlotSummary:
    """Testes da dataclass SaveSlotSummary."""

    def test_save_slot_summary_is_frozen(self):
        """Teste que SaveSlotSummary é imutável."""
        slot = SaveSlot(number=1, path=Path("save_1"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=5)

        with pytest.raises(AttributeError):
            summary.tres_file_count = 10

    def test_save_slot_summary_preserves_slot_object(self):
        """Teste que SaveSlotSummary mantém o mesmo objeto SaveSlot."""
        slot = SaveSlot(number=3, path=Path("save_3"))
        summary = SaveSlotSummary(slot=slot, tres_file_count=7)

        assert summary.slot is slot
        assert summary.slot.number == 3
        assert summary.slot.path.name == "save_3"


class TestBuildSaveSlotSummaries:
    """Testes da função build_save_slot_summaries."""

    def test_build_save_slot_summaries_empty_directory(self, tmp_path):
        """Teste que retorna lista vazia quando diretório inexistente."""
        result = build_save_slot_summaries(base_path=tmp_path / "nonexistent")

        assert len(result) == 0

    def test_build_save_slot_summaries_no_slots(self, tmp_path):
        """Teste que retorna lista vazia quando diretório existe sem slots."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        result = build_save_slot_summaries(base_path=game_data_dir)

        assert len(result) == 0

    def test_build_save_slot_summaries_multiple_slots(self, tmp_path):
        """Teste que múltiplos slots geram múltiplos resumos."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        # Cria slots
        (game_data_dir / "save_1").mkdir()
        (game_data_dir / "save_2").mkdir()
        (game_data_dir / "save_3").mkdir()

        result = build_save_slot_summaries(base_path=game_data_dir)

        assert len(result) == 3
        assert result[0].slot.number == 1
        assert result[1].slot.number == 2
        assert result[2].slot.number == 3

    def test_build_save_slot_summaries_orders_numerically(self, tmp_path):
        """Teste que slots são retornados na ordem numérica (1, 2, 10)."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        # Cria slots com números variados
        (game_data_dir / "save_1").mkdir()
        (game_data_dir / "save_2").mkdir()
        (game_data_dir / "save_10").mkdir()
        (game_data_dir / "save_3").mkdir()

        result = build_save_slot_summaries(base_path=game_data_dir)

        assert len(result) == 4
        assert result[0].slot.number == 1
        assert result[1].slot.number == 2
        assert result[2].slot.number == 3
        assert result[3].slot.number == 10

    def test_build_save_slot_summaries_counts_tres_recursively(self, tmp_path):
        """Teste que arquivos .tres são contados recursivamente."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        slot_dir = game_data_dir / "save_1"
        slot_dir.mkdir()

        subpasta = slot_dir / "subpasta"
        subpasta.mkdir()

        # Cria arquivos .tres em diferentes níveis
        (slot_dir / "root.tres").touch()
        (subpasta / "nested.tres").touch()
        deep_dir = subpasta / "mais_nivel" / "deep.tres"
        deep_dir.parent.mkdir(parents=True, exist_ok=True)
        deep_dir.touch()

        result = build_save_slot_summaries(base_path=game_data_dir)

        assert len(result) == 1
        assert result[0].slot.number == 1
        assert result[0].tres_file_count == 3

    def test_build_save_slot_summaries_ignores_non_tres_files(self, tmp_path):
        """Teste que arquivos com outras extensões não são contados."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        slot_dir = game_data_dir / "save_1"
        slot_dir.mkdir()

        # Cria arquivos mistos
        (slot_dir / "dados.json").touch()
        (slot_dir / "config.dat").touch()
        (slot_dir / "plantas.tres").touch()
        (slot_dir / "animacao.TRES").touch()  # Case-insensitive

        result = build_save_slot_summaries(base_path=game_data_dir)

        assert len(result) == 1
        assert result[0].tres_file_count == 2

    def test_build_save_slot_summaries_preserves_slot_object(self, tmp_path):
        """Teste que o resumo mantém o mesmo objeto SaveSlot retornado pela descoberta."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        slot_dir = game_data_dir / "save_5"
        slot_dir.mkdir()

        result = build_save_slot_summaries(base_path=game_data_dir)

        assert len(result) == 1
        summary = result[0]
        assert summary.slot is not None
        assert summary.slot.number == 5
        assert summary.slot.path.name == "save_5"

    def test_build_save_slot_summaries_summary_is_immutable(self, tmp_path):
        """Teste que SaveSlotSummary é imutável."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        slot_dir = game_data_dir / "save_1"
        slot_dir.mkdir()

        (slot_dir / "test.tres").touch()

        result = build_save_slot_summaries(base_path=game_data_dir)

        summary = result[0]

        with pytest.raises(AttributeError):
            summary.tres_file_count = 100
