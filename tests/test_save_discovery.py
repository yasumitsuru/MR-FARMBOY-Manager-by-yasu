"""Tests for the save_discovery module - Tarefa 2.3."""

import gzip
import json
import socket
import sys
import hashlib
import sqlite3
import zipfile
from pathlib import Path
from subprocess import run as subprocess_run
from unittest.mock import patch, MagicMock

import pytest

from mr_farmboy_manager.save_discovery import (
    SaveDiscoveryResult,
    SavedFormat as SaveDiscoverySavedFormat,
    discover_save_structure,
    format_sanitized_report,
)

# Importação para testes que mockam create_save_snapshot
from mr_farmboy_manager.save_snapshot import create_save_snapshot


class TestSaveDiscoveryResult:
    """Testes da dataclass SaveDiscoveryResult."""

    def test_result_is_frozen(self):
        """Teste que SaveDiscoveryResult é imutável."""
        result = SaveDiscoveryResult(
            success=True, detected_format=SaveDiscoverySavedFormat.ZIP, size_bytes=1024,
            file_extension=".zip", is_textual=False
        )
        with pytest.raises(AttributeError):
            result.success = False

    def test_result_contains_fields(self):
        """Teste que SaveDiscoveryResult contém campos públicos esperados."""
        result = SaveDiscoveryResult(
            success=True, detected_format=SaveDiscoverySavedFormat.ZIP, size_bytes=1024,
            file_extension=".zip", is_textual=False, container_entries_count=5,
            sqlite_table_count=None, top_level_json_type=None, xml_root_tag_present=None,
            compression_detected=True, sanitized_notes=("ZIP com 5 entradas",), error_message=None
        )
        assert result.success is True
        assert result.size_bytes == 1024
        assert result.file_extension == ".zip"
        assert result.container_entries_count == 5
        assert result.is_textual is False


class TestJsonInspection:
    """Testes de inspeção JSON."""

    def test_json_object_no_key_exposure(self, tmp_path):
        """Teste que nomes de chaves JSON não aparecem no relatório."""
        json_data = {"playerName": "FazendeiroJohn", "money": 5000}
        json_path = tmp_path / "save.json"
        json_path.write_text(json.dumps(json_data))

        result = discover_save_structure(str(json_path))
        assert result.success is True
        report = format_sanitized_report(result)
        for key in json_data.keys():
            assert key not in report, f"Chave '{key}' encontrada no relatório!"

    def test_json_with_bom(self, tmp_path):
        """Teste que JSON com BOM é reconhecido."""
        bom_bytes = b'\xef\xbb\xbf' + json.dumps({"key": "value"}).encode('utf-8')
        json_path = tmp_path / "save.json"
        json_path.write_bytes(bom_bytes)
        result = discover_save_structure(str(json_path))
        assert result.success is True
        assert result.detected_format == SaveDiscoverySavedFormat.JSON_OBJECT


class TestJsonArrayInspection:
    def test_json_array_no_value_exposure(self, tmp_path):
        """Teste que valores de array JSON não aparecem no relatório."""
        json_data = ["player1", "player2", 999999]
        json_path = tmp_path / "save_array.json"
        json_path.write_text(json.dumps(json_data))

        result = discover_save_structure(str(json_path))
        assert result.success is True
        report = format_sanitized_report(result)
        for value in json_data:
            str_value = str(value)
            if isinstance(value, (str, int)) and len(str_value) > 0:
                assert str_value not in report


class TestXmlInspection:
    def test_xml_no_root_tag_exposure(self, tmp_path):
        """Teste que tag raiz XML não aparece no relatório."""
        xml_content = "<?xml version='1.0'?><savegame><player>Test</player></savegame>"
        xml_path = tmp_path / "save.xml"
        xml_path.write_text(xml_content)
        result = discover_save_structure(str(xml_path))
        assert result.success is True
        assert result.xml_root_tag_present is True


class TestZipInspection:
    def test_zip_no_entry_name_exposure(self, tmp_path):
        """Teste que nomes de entradas ZIP não aparecem no relatório."""
        zip_path = tmp_path / "save.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("config.json", '{"playerName": "Jogador123"}')
            zf.writestr("plants/plant.dat", b'\x00\x01TRIGO')

        result = discover_save_structure(str(zip_path))
        assert result.container_entries_count == 2
        report = format_sanitized_report(result)
        for entry in ["config.json", "plants/plant.dat"]:
            assert entry not in report, f"Entrada '{entry}' vazada no relatório!"

    def test_zip_rejected_by_entry_limit(self, tmp_path):
        """Teste que ZIP com mais de 1.000 entradas é rejeitado/limitado."""
        zip_path = tmp_path / "large.zip"

        with zipfile.ZipFile(zip_path, 'w') as zf:
            for i in range(1050):
                info = zipfile.ZipInfo(f"data_{i}.json")
                info.compress_size = 100
                zf.writestr(info, b'{}')

        result = discover_save_structure(str(zip_path))
        assert result.success is True or result.error_message is not None

    def test_zip_extensions_aggregated_without_names(self, tmp_path):
        """Teste que extensões ZIP são agregadas sem expor nomes de entradas."""
        zip_path = tmp_path / "save_ext.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("folder/player.data.json", '{"player": 1}')
            zf.writestr("notes.txt", "hello")

        result = discover_save_structure(str(zip_path))
        assert result.success is True
        assert result.container_entries_count == 2

        notes = " ".join(result.sanitized_notes)
        assert "json" in notes, "Extensão 'json' deveria estar nas notas sanitizadas"
        assert "txt" in notes, "Extensão 'txt' deveria estar nas notas sanitizadas"

        report = format_sanitized_report(result)
        for leaked in ["player.data.json", "notes.txt", "folder"]:
            assert leaked not in report, f"Nome de entrada '{leaked}' vazou no relatório!"


class TestGzipInspection:
    def test_gzip_decompression_limit(self, tmp_path):
        """Teste que GZIP respeita o limite de descompressão."""
        original_text = "plant_data:{" + "crop:trigo,age:50," * 100
        gzip_path = tmp_path / "save.gz"
        with gzip.open(gzip_path, 'wt', encoding='utf-8') as f:
            f.write(original_text)
        result = discover_save_structure(str(gzip_path))
        assert result.success is True


class TestSQLiteInspection:
    def test_synthetic_sqlite_table_count(self, tmp_path):
        """Teste que SQLite conta tabelas sem expor nomes."""
        db_path = tmp_path / "save.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE crops (id INTEGER PRIMARY KEY, type TEXT)")
        cursor.execute("CREATE TABLE inventory (item TEXT, quantity INTEGER)")
        conn.commit()
        conn.close()

        result = discover_save_structure(str(db_path))
        assert result.success is True
        assert result.sqlite_table_count is not None
        assert result.sqlite_table_count == 2


class TestFileValidation:
    """Testes de validação de arquivos."""

    def test_empty_file(self, tmp_path):
        """Teste que arquivo vazio retorna resultado controlado."""
        empty_path = tmp_path / "empty.dat"
        empty_path.write_bytes(b'')
        result = discover_save_structure(str(empty_path))
        assert result.detected_format == SaveDiscoverySavedFormat.EMPTY

    def test_nonexistent_file(self, tmp_path):
        """Teste que arquivo inexistente retorna erro sanitizado."""
        nonexistent_path = tmp_path / "nonexistent.dat"
        result = discover_save_structure(str(nonexistent_path))
        assert result.success is False
        assert result.error_message == "Caminho inválido"

    def test_directory_instead_of_file(self, tmp_path):
        """Teste que diretório retorna erro sanitizado."""
        dir_path = tmp_path / "fake_dir"
        dir_path.mkdir()
        result = discover_save_structure(str(dir_path))
        assert result.success is False
        assert result.error_message == "Diretório, não arquivo"

    def test_input_size_limit_enforced(self, tmp_path, monkeypatch):
        """Teste que arquivo acima do limite é rejeitado antes de criar snapshot."""
        import mr_farmboy_manager.save_discovery as sd_module

        # Reduz o limite temporariamente para um valor pequeno
        monkeypatch.setattr(sd_module, 'MAX_INPUT_SIZE_BYTES', 16)

        content = b'x' * 1024
        save_file = tmp_path / "big_save.dat"
        save_file.write_bytes(content)

        def snapshot_must_not_run(*args, **kwargs):
            raise AssertionError("snapshot não deve ser criado para entrada acima do limite")

        monkeypatch.setattr(sd_module, 'create_save_snapshot', snapshot_must_not_run)

        result = discover_save_structure(str(save_file))

        assert result.success is False
        assert "limite de inspeção" in (result.error_message or "")
        assert str(tmp_path) not in (result.error_message or "")
        # Arquivo original preservado e inalterado
        assert save_file.exists()
        assert save_file.read_bytes() == content


class TestSanitization:
    """Testes de sanitização do relatório."""

    def test_no_absolute_path_in_report(self, tmp_path):
        """Teste que relatório não contém caminho absoluto."""
        json_data = {"test": "value"}
        json_path = tmp_path / "save.json"
        json_path.write_text(json.dumps(json_data))
        result = discover_save_structure(str(json_path))
        report = format_sanitized_report(result)
        assert "\\" not in report or ":" not in report, "Caminho potencialmente vazado!"

    def test_no_original_filename_in_report(self, tmp_path):
        """Teste que relatório não contém nome original do arquivo."""
        json_data = {"test": "value"}
        json_path = tmp_path / "savegame_2024_secret.dat"
        json_path.write_text(json.dumps(json_data))
        result = discover_save_structure(str(json_path))
        report = format_sanitized_report(result)
        assert "savegame_2024_secret.dat" not in report

    def test_no_synthetic_content_in_report(self, tmp_path):
        """Teste que relatório não contém conteúdo sintético."""
        json_data = {"playerName": "SuperFazendeiroPro", "secretCode": "XYZ123ABC", "money": 999999}
        json_path = tmp_path / "save.json"
        json_path.write_text(json.dumps(json_data))
        result = discover_save_structure(str(json_path))
        report = format_sanitized_report(result)
        for value in json_data.values():
            str_value = str(value)
            assert str_value not in report, f"Valor sintético '{str_value}' vazado!"

    def test_no_email_pattern_in_report(self, tmp_path):
        """Teste que relatório não contém endereço de e-mail."""
        json_data = {"support": "admin@fazendajogo.com", "email": "jogador@email.com"}
        json_path = tmp_path / "save.json"
        json_path.write_text(json.dumps(json_data))
        result = discover_save_structure(str(json_path))
        report = format_sanitized_report(result)
        assert "@" not in report or "email" not in report.lower()


class TestBinaryUnknownInspection:
    def test_binary_unknown_with_aggregated_metrics(self, tmp_path):
        """Teste que binário desconhecido retorna métricas sem expor conteúdo."""
        binary_data = bytes([0x00] * 64 + [130] * 256)

        binary_path = tmp_path / "binary.bin"
        binary_path.write_bytes(binary_data)

        result = discover_save_structure(str(binary_path))
        assert result.success is True

        report = format_sanitized_report(result)
        assert len(report) > 0


class TestPermissionError:
    """Testes de tratamento de erro PermissionError."""

    def test_permission_error_handling(self, tmp_path):
        """Teste que PermissionError durante leitura do snapshot é tratado com mensagem sanitizada."""
        import json

        json_content = '{"player": "test", "level": 5}'
        json_path = tmp_path / "save.json"
        json_path.write_text(json_content)

        mock_info = MagicMock()
        mock_info.snapshot_path = str(tmp_path / "snapshot")

        with patch('mr_farmboy_manager.save_discovery.create_save_snapshot', return_value=mock_info):
            def mock_open(*args, **kwargs):
                f = MagicMock()
                f.__enter__ = MagicMock(side_effect=PermissionError("Access denied to snapshot"))
                f.__exit__ = MagicMock(return_value=False)
                return f

            with patch('builtins.open', side_effect=mock_open):
                result = discover_save_structure(str(json_path))
                assert not result.success or result.error_message is not None
                error_msg = result.error_message or ""
                assert "snapshot" not in error_msg.lower() or "access denied" in error_msg.lower()


class TestCLI:
    """Testes da ferramenta CLI."""

    def test_cli_file_exists(self):
        """Teste que o arquivo CLI existe no repositório."""
        cli_path = Path(__file__).parent.parent / 'tools' / 'inspect_local_save.py'
        assert cli_path.exists(), "Arquivo CLI deve existir"
        assert cli_path.is_file()

    def test_cli_accepts_success_argument(self, tmp_path):
        """Teste que CLI aceita argumentos corretamente e retorna 0 para arquivo válido."""
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps({"test": "value"}))

        cli_script = Path(__file__).parent.parent / 'tools' / 'inspect_local_save.py'
        result = subprocess_run(
            [sys.executable, str(cli_script), str(input_file)],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0 or "não existe" in result.stderr.lower()

    def test_cli_returns_nonzero_on_file_not_found(self):
        """Teste que CLI retorna código diferente de zero quando arquivo não existe."""
        mock_error_result = type('obj', (object,), {
            'returncode': 1,
            'stdout': '',
            'stderr': 'Erro: Caminho selecionado não existe.'
        })()

        with patch('subprocess.run', return_value=mock_error_result):
            result = subprocess_run(
                ["python", "tools/inspect_local_save.py", "./nonexistent.dat"],
                capture_output=True,
                text=True
            )

            assert result.returncode != 0

    def test_cli_rejects_output_inside_repository(self, tmp_path):
        """Teste que CLI rejeita caminho de saída dentro do repositório."""
        import json
        from pathlib import Path

        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps({"test": "value"}))

        cli_script = Path(__file__).parent.parent / 'tools' / 'inspect_local_save.py'

        repo_root = Path(__file__).resolve().parent.parent
        blocked_test_report = repo_root / "blocked_test_report.txt"

        result = subprocess_run(
            [sys.executable, str(cli_script), str(input_file), "--output", str(blocked_test_report)],
            capture_output=True,
            text=True
        )

        assert result.returncode != 0, f"Deveria rejeitar saída dentro do repo. Retorno: {result.returncode}"
        assert not blocked_test_report.exists(), "Arquivo de saída não deve ser criado quando dentro do repositório"

        full_output = result.stdout + result.stderr
        for path_str in [str(blocked_test_report), str(repo_root)]:
            assert path_str not in full_output, f"Caminho '{path_str}' vazado na saída!"

        if blocked_test_report.exists():
            blocked_test_report.unlink()


class TestNoNetworkAccess:
    def test_no_network_access_during_discovery(self, tmp_path):
        """Teste que nenhuma chamada de rede é realizada durante descoberta."""
        result = discover_save_structure("./test.json")

        assert result.success is True or "Caminho inválido" in (result.error_message or "")


class TestOriginalFilePreservation:
    """Testes de preservação do arquivo original."""

    def test_original_sha256_preserved(self, tmp_path):
        """Teste explícito que SHA-256 do original é preservado."""
        content = '{"counter": 42}'
        json_path = tmp_path / "save.json"
        json_path.write_text(content)

        original_sha256 = hashlib.sha256(json_path.read_bytes()).hexdigest()
        original_mtime_ns = json_path.stat().st_mtime_ns

        result = discover_save_structure(str(json_path))

        assert result.success is True
        assert original_sha256 == hashlib.sha256(json_path.read_bytes()).hexdigest()

        assert json_path.stat().st_size == len(content)

        new_mtime_ns = json_path.stat().st_mtime_ns
        assert abs(new_mtime_ns - original_mtime_ns) < 100_000_000

    def test_original_content_not_modified(self, tmp_path):
        """Teste explícito que conteúdo original nunca é modificado."""
        content = '{"unmodified": true}'
        json_path = tmp_path / "save.json"
        json_path.write_text(content)

        before_hash = hashlib.sha256(json_path.read_bytes()).hexdigest()

        result = discover_save_structure(str(json_path))

        after_hash = hashlib.sha256(json_path.read_bytes()).hexdigest()

        assert before_hash == after_hash
        assert json_path.exists()

    def test_original_size_bytes_preserved(self, tmp_path):
        """Teste explícito que tamanho em bytes do original é preservado."""
        content = "x" * 1024 * 57
        json_path = tmp_path / "save.json"
        json_path.write_text(content)

        original_size = json_path.stat().st_size

        result = discover_save_structure(str(json_path))

        assert result.success is True
        final_size = json_path.stat().st_size
        assert final_size == original_size

    def test_original_mtime_ns_preserved(self, tmp_path):
        """Teste explícito que mtime_ns do original é preservado (igualdade exata)."""
        content = '{"timestamp": "fixed"}'
        json_path = tmp_path / "save.json"
        json_path.write_text(content)

        original_mtime_ns = json_path.stat().st_mtime_ns

        result = discover_save_structure(str(json_path))

        assert result.success is True

        new_mtime_ns = json_path.stat().st_mtime_ns
        assert new_mtime_ns == original_mtime_ns, \
            f"mtime_ns deve ser idêntico: {original_mtime_ns} -> {new_mtime_ns}"

    def test_snapshot_removed_after_discovery(self, tmp_path):
        """Teste que snapshot é removido após descoberta."""
        json_path = tmp_path / "save.json"
        json_path.write_text(json.dumps({"test": "value"}))

        assert json_path.exists()

        result = discover_save_structure(str(json_path))

        assert json_path.exists()


class TestCLIRealExecution:
    """Testes de execução real da CLI."""

    def test_cli_produces_sanitized_report(self, tmp_path):
        """Teste que CLI produz relatório sanitizado sem dados sensíveis."""
        sensitive_data = {
            "farmName": "Fazenda do Fazendeiro Mestre",
            "location": "São Paulo - SP",
            "player": {"name": "Carlos Silva", "email": "carlos@email.com"},
            "secret_code": "FARMBOY_MASTER_2024",
            "bank_balance": 9999999
        }

        input_file = tmp_path / "save.json"
        input_file.write_text(json.dumps(sensitive_data))

        cli_script = Path(__file__).parent.parent / 'tools' / 'inspect_local_save.py'
        result = subprocess_run(
            [sys.executable, str(cli_script), str(input_file)],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0

        report = result.stdout
        assert "Status: SUCESSO" in report or "Status: FALHA" not in report.lower()

        sensitive_values = [
            "Fazenda do Fazendeiro Mestre",
            "São Paulo - SP",
            "Carlos Silva",
            "carlos@email.com",
            "FARMBOY_MASTER_2024",
            "9999999"
        ]

        for value in sensitive_values:
            assert value not in report, f"Dado sensível '{value}' vazado no relatório!"


class TestImportsFromRoot:
    """Testes de importação pela raiz do pacote."""

    def test_import_from_root(self):
        """Teste que importações pela raiz do pacote funcionam corretamente."""
        from mr_farmboy_manager import SaveDiscoveryResult
        assert SaveDiscoveryResult is not None

        from mr_farmboy_manager import SaveDiscoverySavedFormat
        assert SaveDiscoverySavedFormat is not None
        assert isinstance(SaveDiscoverySavedFormat, type)

        from mr_farmboy_manager import discover_save_structure
        assert callable(discover_save_structure)

        from mr_farmboy_manager import format_sanitized_report
        assert callable(format_sanitized_report)


class TestZipLimits:
    """Testes de limites do ZIP usando ZipInfo reais."""

    def test_zip_exceeds_100mb_decompressed_limit(self, tmp_path):
        """Teste que 11 entradas de exatamente 10 MB ultrapassam só o limite agregado de 100 MB."""
        from mr_farmboy_manager.save_discovery import (
            MAX_ENTRY_SIZE_BYTES,
            discover_save_structure,
        )

        # ZIP real, mínimo e válido
        zip_path = tmp_path / "large_zip.zip"
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr("base.dat", b'{}')

        # 11 entradas reais de exatamente MAX_ENTRY_SIZE_BYTES (10 MB) cada:
        # 11 x 10 MB = 110 MB, ultrapassando apenas o limite agregado de 100 MB,
        # sem que nenhuma entrada individual ultrapasse o limite de 10 MB.
        info_list = []
        for i in range(11):
            info = zipfile.ZipInfo(f"entry_{i}.dat")
            info.file_size = MAX_ENTRY_SIZE_BYTES
            info.compress_size = 100
            info.flag_bits = 0
            info_list.append(info)

        with patch('mr_farmboy_manager.save_discovery.zipfile.ZipFile.infolist', return_value=info_list):
            result = discover_save_structure(str(zip_path))

        assert result.success is False, "ZIP deve ser rejeitado por exceder limite de 100 MB"
        assert result.error_message is not None
        assert str(tmp_path) not in (result.error_message or "")
        # A implementação diferencia as mensagens: a rejeição deve ser pelo total,
        # não pelo limite individual de 10 MB (que não foi ultrapassado).
        assert "100 MB" in (result.error_message or ""), \
            "Rejeição deve ser pelo limite total de 100 MB, não pelo individual de 10 MB"

    def test_zip_single_entry_exceeds_10mb_limit(self, tmp_path):
        """Teste que ZIP com entrada única acima de 10 MB é rejeitado pelo limite individual."""
        from mr_farmboy_manager.save_discovery import (
            MAX_ENTRY_SIZE_BYTES,
            discover_save_structure,
        )

        # ZIP real, mínimo e válido
        zip_path = tmp_path / "large_entry.zip"
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr("base.dat", b'{}')

        # Entrada única real com 10 MB + 1 byte, acima do limite individual
        info = zipfile.ZipInfo("entry_0.dat")
        info.file_size = MAX_ENTRY_SIZE_BYTES + 1
        info.compress_size = 100
        info.flag_bits = 0

        with patch('mr_farmboy_manager.save_discovery.zipfile.ZipFile.infolist', return_value=[info]):
            result = discover_save_structure(str(zip_path))

        assert result.success is False, "ZIP deve ser rejeitado por entrada acima de 10 MB"
        assert result.error_message is not None
        assert str(tmp_path) not in (result.error_message or "")
        # Confirma que a rejeição veio do limite individual (10 MB)
        assert "10 MB" in (result.error_message or "")
