"""Tests for the Godot 4 .tres structural parser - Tarefa 2.5.

Todos os exemplos sao sinteticos e pequenos. Nenhum conteudo, nome de
propriedade ou valor proveniente de saves reais e usado aqui.
"""

import gzip
import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from mr_farmboy_manager.godot_tres import (
    GodotTresParseError,
    GodotTresProfile,
    is_godot_tres_text,
    parse_godot_tres_document,
    parse_godot_tres_structure,
)
from mr_farmboy_manager.save_discovery import (
    SavedFormat as SaveDiscoverySavedFormat,
    discover_save_structure,
    format_sanitized_report,
)

HEADER = '[gd_resource type="Resource" load_steps=2 format=3]'


def make_tres(body: str = '', header: str = HEADER) -> bytes:
    return (header + "\n" + body).encode('utf-8')


def profile_of(body: str = '', header: str = HEADER) -> GodotTresProfile:
    return parse_godot_tres_structure(make_tres(body=body, header=header))


def cat_counts(profile: GodotTresProfile) -> dict:
    return dict(profile.variant_category_counts)


class TestHeaderDetection:
    """Testes 1-8: deteccao do cabecalho gd_resource."""

    def test_valid_godot4_header(self):
        data = make_tres('money = 100')
        assert is_godot_tres_text(data) is True
        profile = parse_godot_tres_structure(data)
        assert profile.is_valid is True
        assert profile.format_version == 3
        assert profile.has_gd_resource_header is True

    def test_utf8_bom_accepted(self):
        data = b'\xef\xbb\xbf' + make_tres('money = 100')
        assert is_godot_tres_text(data) is True
        profile = parse_godot_tres_structure(data)
        assert profile.format_version == 3

    def test_crlf_accepted(self):
        data = '[gd_resource type="Resource" format=3]\r\nmoney = 100\r\n'.encode('utf-8')
        assert is_godot_tres_text(data) is True
        profile = parse_godot_tres_structure(data)
        assert profile.format_version == 3
        assert profile.property_count == 1

    def test_comments_before_header(self):
        data = (
            "# arquivo de save sintetico\n"
            "# gerado para testes\n"
            "\n"
            "[gd_resource type=\"Resource\" format=3]\n"
            "money = 100\n"
        ).encode('utf-8')
        assert is_godot_tres_text(data) is True
        profile = parse_godot_tres_structure(data)
        assert profile.format_version == 3
        assert profile.comment_count == 2
        assert profile.blank_line_count == 1

    def test_incomplete_header_rejected(self):
        data = '[gd_resource type="Resource" format=3'.encode('utf-8')
        assert is_godot_tres_text(data) is False
        with pytest.raises(GodotTresParseError):
            parse_godot_tres_structure(data)

    def test_missing_format_rejected(self):
        data = '[gd_resource type="Resource"]\nmoney = 100\n'.encode('utf-8')
        assert is_godot_tres_text(data) is False
        with pytest.raises(GodotTresParseError):
            parse_godot_tres_structure(data)

    def test_non_numeric_format_rejected(self):
        data = '[gd_resource type="Resource" format=abc]\n'.encode('utf-8')
        assert is_godot_tres_text(data) is False
        with pytest.raises(GodotTresParseError):
            parse_godot_tres_structure(data)

    def test_plain_text_containing_word_gd_resource_rejected(self):
        data = "este arquivo fala sobre gd_resource mas nao e um save\n".encode('utf-8')
        assert is_godot_tres_text(data) is False

    def test_header_requires_format_and_brackets(self):
        # Palavra isolada nao basta; [gd_resourcex ...] tambem nao e cabecalho
        assert is_godot_tres_text(b'gd_resource') is False
        assert is_godot_tres_text(b'[gd_resourcex type="A" format=3]') is False

    def test_format_inside_string_rejected(self):
        # O atributo format deve ser analisado fora de strings
        data = '[gd_resource type="format=3"]\nmoney = 100\n'.encode('utf-8')
        assert is_godot_tres_text(data) is False
        with pytest.raises(GodotTresParseError):
            parse_godot_tres_structure(data)

    def test_format_2_rejected(self):
        # Detector Godot 4 desta tarefa: exige format == 3
        data = '[gd_resource type="Resource" format=2]\n'.encode('utf-8')
        assert is_godot_tres_text(data) is False
        with pytest.raises(GodotTresParseError):
            parse_godot_tres_structure(data)

    def test_format_with_trailing_garbage_rejected(self):
        # Qualquer caractere nao permitido apos o inteiro rejeita o cabecalho
        for bad in ('format=3.0', 'format=3abc', 'format=3_0'):
            data = f'[gd_resource type="Resource" {bad}]\n'.encode('utf-8')
            assert is_godot_tres_text(data) is False, f"'{bad}' deveria ser rejeitado"
            with pytest.raises(GodotTresParseError):
                parse_godot_tres_structure(data)

    def test_format_accepted_variants(self):
        # format=3, format = 3 (espacos) e format=+3 continuam validos
        for good in ('format=3', 'format = 3', 'format=+3'):
            data = f'[gd_resource type="Resource" {good}]\n'.encode('utf-8')
            assert is_godot_tres_text(data) is True, f"'{good}' deveria ser aceito"
            profile = parse_godot_tres_structure(data)
            assert profile.format_version == 3

    def test_content_before_header_raises(self):
        data = 'money = 1\n[gd_resource type="Resource" format=3]\n'.encode('utf-8')
        assert is_godot_tres_text(data) is False
        with pytest.raises(GodotTresParseError):
            parse_godot_tres_structure(data)

    def test_section_before_header_raises(self):
        data = '[resource]\n[gd_resource type="Resource" format=3]\n'.encode('utf-8')
        assert is_godot_tres_text(data) is False
        with pytest.raises(GodotTresParseError):
            parse_godot_tres_structure(data)


class TestSectionCounting:
    """Testes 9-11: contagem de secoes."""

    def test_ext_resource_count(self):
        body = (
            '[ext_resource type="Script" path="res://player.gd" id="1"]\n'
            '[ext_resource type="Texture2D" path="res://icon.png" id="2"]\n'
            '[resource]\n'
            'money = 100\n'
        )
        profile = profile_of(body)
        assert profile.ext_resource_count == 2
        assert profile.total_section_count == 4  # header + 2 ext + resource

    def test_sub_resource_count(self):
        body = (
            '[sub_resource type="Animation" id="1"]\n'
            'length = 1.0\n'
            '[sub_resource type="Animation" id="2"]\n'
            'length = 2.0\n'
            '[resource]\n'
            'anim = SubResource("2")\n'
        )
        profile = profile_of(body)
        assert profile.sub_resource_count == 2
        assert profile.resource_section_count == 1
        assert profile.property_count == 3

    def test_resource_section_count(self):
        body = (
            '[sub_resource type="Animation" id="1"]\n'
            'length = 1.0\n'
            '[resource]\n'
            'anim = SubResource("1")\n'
        )
        profile = profile_of(body)
        assert profile.resource_section_count == 1

    def test_second_resource_section_raises(self):
        body = (
            '[resource]\n'
            'a = 1\n'
            '[resource]\n'
            'b = 2\n'
        )
        with pytest.raises(GodotTresParseError):
            profile_of(body)

    def test_duplicate_gd_resource_header_raises(self):
        data = (
            '[gd_resource type="Resource" format=3]\n'
            '[gd_resource type="Resource" format=3]\n'
        ).encode('utf-8')
        with pytest.raises(GodotTresParseError):
            parse_godot_tres_structure(data)

    def test_unknown_section_warns_without_name(self):
        body = (
            '[resource]\n'
            '[coisa_estranha xyz]\n'
            'a = 1\n'
        )
        profile = profile_of(body)
        assert any('Seção' in w for w in profile.sanitized_warnings)
        assert 'coisa_estranha' not in str(profile.sanitized_warnings)


class TestProperties:
    """Testes 12-18: propriedades e linhas logicas."""

    def test_property_count(self):
        body = (
            '[resource]\n'
            'money = 100\n'
            'name = "Fazenda"\n'
            'enabled = true\n'
        )
        profile = profile_of(body)
        assert profile.property_count == 3

    def test_string_containing_equals_counts_one_property(self):
        body = '[resource]\ntexto = "a=b"\n'
        profile = profile_of(body)
        assert profile.property_count == 1
        assert cat_counts(profile)['string'] == 1

    def test_string_containing_brackets_counts_one_property(self):
        body = '[resource]\ntexto = "[x, y]"\n'
        profile = profile_of(body)
        assert profile.property_count == 1
        assert cat_counts(profile)['string'] == 1

    def test_multiline_array_counts_one_property(self):
        body = (
            '[resource]\n'
            'items = [\n'
            '    1,\n'
            '    2,\n'
            '    3\n'
            ']\n'
        )
        profile = profile_of(body)
        assert profile.property_count == 1
        assert cat_counts(profile)['array'] == 1

    def test_multiline_dictionary_counts_one_property(self):
        body = (
            '[resource]\n'
            'data = {\n'
            '    "a": 1,\n'
            '    "b": 2\n'
            '}\n'
        )
        profile = profile_of(body)
        assert profile.property_count == 1
        assert cat_counts(profile)['dictionary'] == 1

    def test_string_escapes_handled(self):
        body = '[resource]\ns = "a\\"b\\\\c"\n'
        profile = profile_of(body)
        assert profile.property_count == 1
        assert cat_counts(profile)['string'] == 1

    def test_nested_parentheses_handled(self):
        body = '[resource]\nx = Wrap(Wrap(1))\n'
        profile = profile_of(body)
        assert profile.property_count == 1
        assert cat_counts(profile)['constructor_other'] == 1
        assert not profile.sanitized_warnings

    def test_equals_inside_string_does_not_split(self):
        body = (
            '[resource]\n'
            'a = "x=1"\n'
            'b = 2\n'
        )
        profile = profile_of(body)
        assert profile.property_count == 2


class TestLimits:
    """Testes 19-22: limites de seguranca (monkeypatch)."""

    def test_nesting_depth_limit(self, monkeypatch):
        import mr_farmboy_manager.godot_tres as gt
        monkeypatch.setattr(gt, 'MAX_GODOT_NESTING_DEPTH', 3)
        data = make_tres('x = A(B(C(D(1))))\n')
        with pytest.raises(GodotTresParseError):
            parse_godot_tres_structure(data)

    def test_logical_line_length_limit(self, monkeypatch):
        import mr_farmboy_manager.godot_tres as gt
        # cabecalho tem ~40 chars; limite 50 permite o cabecalho mas nao a linha longa
        monkeypatch.setattr(gt, 'MAX_GODOT_LOGICAL_LINE_LENGTH', 50)
        data = make_tres('long_property = "' + 'x' * 120 + '"\n')
        with pytest.raises(GodotTresParseError):
            parse_godot_tres_structure(data)

    def test_property_count_limit(self, monkeypatch):
        import mr_farmboy_manager.godot_tres as gt
        monkeypatch.setattr(gt, 'MAX_GODOT_PROPERTY_COUNT', 2)
        data = make_tres('[resource]\na = 1\nb = 2\nc = 3\n')
        with pytest.raises(GodotTresParseError):
            parse_godot_tres_structure(data)

    def test_section_count_limit(self, monkeypatch):
        import mr_farmboy_manager.godot_tres as gt
        monkeypatch.setattr(gt, 'MAX_GODOT_SECTION_COUNT', 1)
        data = make_tres('[ext_resource type="Script" path="res://a.gd" id="1"]\n')
        with pytest.raises(GodotTresParseError):
            parse_godot_tres_structure(data)

    def test_limit_error_message_is_sanitized(self, monkeypatch):
        import mr_farmboy_manager.godot_tres as gt
        monkeypatch.setattr(gt, 'MAX_GODOT_SECTION_COUNT', 1)
        data = make_tres('[ext_resource type="Script" path="res://secret.gd" id="9"]\n')
        with pytest.raises(GodotTresParseError) as excinfo:
            parse_godot_tres_structure(data)
        msg = str(excinfo.value)
        assert 'secret' not in msg
        assert 'res://' not in msg
        assert '9' not in msg


class TestVariantClassification:
    """Testes 23-35: classificacao estrutural de Variants."""

    def test_bool(self):
        profile = profile_of('[resource]\na = true\nb = false\n')
        counts = cat_counts(profile)
        assert counts['bool'] == 2

    def test_integer(self):
        profile = profile_of('[resource]\na = 42\nb = -7\n')
        counts = cat_counts(profile)
        assert counts['integer'] == 2

    def test_float(self):
        profile = profile_of('[resource]\na = 1.5\nb = -0.25\n')
        counts = cat_counts(profile)
        assert counts['float'] == 2

    def test_string(self):
        profile = profile_of('[resource]\na = "texto"\n')
        counts = cat_counts(profile)
        assert counts['string'] == 1

    def test_array(self):
        profile = profile_of('[resource]\na = []\n')
        counts = cat_counts(profile)
        assert counts['array'] == 1

    def test_dictionary(self):
        profile = profile_of('[resource]\na = {}\n')
        counts = cat_counts(profile)
        assert counts['dictionary'] == 1

    def test_ext_resource_reference(self):
        profile = profile_of('[resource]\na = ExtResource("1")\n')
        counts = cat_counts(profile)
        assert counts['ext_resource_reference'] == 1

    def test_sub_resource_reference(self):
        profile = profile_of('[resource]\na = SubResource("2")\n')
        counts = cat_counts(profile)
        assert counts['sub_resource_reference'] == 1

    def test_node_path(self):
        profile = profile_of('[resource]\na = NodePath("Fazenda/Campo")\n')
        counts = cat_counts(profile)
        assert counts['node_path'] == 1

    def test_vector(self):
        profile = profile_of('[resource]\na = Vector2(1, 2)\nb = Vector3(1, 2, 3)\n')
        counts = cat_counts(profile)
        assert counts['vector'] == 2

    def test_color(self):
        profile = profile_of('[resource]\na = Color(1, 0, 0, 1)\n')
        counts = cat_counts(profile)
        assert counts['color'] == 1

    def test_packed_array(self):
        profile = profile_of(
            '[resource]\na = PackedInt32Array(1, 2, 3)\nb = PackedStringArray("x", "y")\n'
        )
        counts = cat_counts(profile)
        assert counts['packed_array'] == 2

    def test_null(self):
        profile = profile_of('[resource]\na = null\n')
        counts = cat_counts(profile)
        assert counts['null'] == 1

    def test_constructor_other(self):
        profile = profile_of('[resource]\na = StringName("classe")\n')
        counts = cat_counts(profile)
        assert counts['constructor_other'] == 1

    def test_unknown_variant(self):
        profile = profile_of('[resource]\na = 12abc\n')
        counts = cat_counts(profile)
        assert counts['unknown'] == 1

    def test_category_counts_sorted_and_deterministic(self):
        body = '[resource]\na = true\nb = 5\nc = "x"\n'
        p1 = profile_of(body)
        p2 = profile_of(body)
        assert p1.variant_category_counts == p2.variant_category_counts
        names = [name for name, _ in p1.variant_category_counts]
        assert names == sorted(names)


class TestSanitization:
    """Testes 36-39: nenhum dado sensivel no perfil ou relatorio."""

    def test_no_names_or_values_in_profile(self):
        body = (
            '[resource]\n'
            'playerName = "SuperJogadorSecreto"\n'
            'secretCode = 987654321\n'
            'res = ExtResource("9a1b2c")\n'
        )
        profile = profile_of(body)
        text = repr(profile)
        for token in ['playerName', 'SuperJogadorSecreto', 'secretCode', '987654321', '9a1b2c']:
            assert token not in text, f"'{token}' vazou no perfil!"

    def test_no_content_in_report(self, tmp_path):
        tres_path = tmp_path / "save.tres"
        tres_path.write_text(
            HEADER + "\n[resource]\n"
            'secretPlayerName = "CarlosSecreto"\n'
            'secretBankBalance = 99999999\n',
            encoding='utf-8',
        )
        result = discover_save_structure(str(tres_path))
        assert result.success is True
        report = format_sanitized_report(result)
        for token in ['secretPlayerName', 'CarlosSecreto', 'secretBankBalance', '99999999']:
            assert token not in report, f"'{token}' vazou no relatorio!"

    def test_report_no_absolute_path(self, tmp_path):
        tres_path = tmp_path / "save.tres"
        tres_path.write_text(HEADER + "\n[resource]\nmoney = 1\n", encoding='utf-8')
        result = discover_save_structure(str(tres_path))
        report = format_sanitized_report(result)
        assert 'C:' not in report
        assert '\\\\' not in report
        assert str(tmp_path) not in report

    def test_report_no_filename(self, tmp_path):
        tres_path = tmp_path / "savegame_2024_secret.tres"
        tres_path.write_text(HEADER + "\n[resource]\nmoney = 1\n", encoding='utf-8')
        result = discover_save_structure(str(tres_path))
        report = format_sanitized_report(result)
        assert 'savegame_2024_secret.tres' not in report

    def test_no_property_names_in_notes(self, tmp_path):
        tres_path = tmp_path / "save.tres"
        tres_path.write_text(
            HEADER + "\n[resource]\nflagInternoSecreto = true\n",
            encoding='utf-8',
        )
        result = discover_save_structure(str(tres_path))
        notes = " ".join(result.sanitized_notes)
        assert 'flagInternoSecreto' not in notes


class TestSnapshotAndPreservation:
    """Testes 40-42: preservacao do original e remocao do snapshot."""

    def test_original_file_preserved(self, tmp_path):
        content = HEADER + "\n[resource]\nmoney = 100\n"
        tres_path = tmp_path / "save.tres"
        tres_path.write_text(content, encoding='utf-8')
        expected_size = tres_path.stat().st_size
        original_sha = hashlib.sha256(tres_path.read_bytes()).hexdigest()
        original_mtime = tres_path.stat().st_mtime_ns

        result = discover_save_structure(str(tres_path))
        assert result.success is True

        assert tres_path.exists()
        assert hashlib.sha256(tres_path.read_bytes()).hexdigest() == original_sha
        assert tres_path.stat().st_size == expected_size
        assert tres_path.stat().st_mtime_ns == original_mtime

    def test_snapshot_removed_after_success(self, tmp_path):
        import contextlib
        import mr_farmboy_manager.save_discovery as sd_module

        tres_path = tmp_path / "save.tres"
        tres_path.write_text(HEADER + "\n[resource]\nmoney = 1\n", encoding='utf-8')

        recorded = {}
        real_create = sd_module.create_save_snapshot

        @contextlib.contextmanager
        def recording_create(path):
            with real_create(path) as info:
                recorded['snapshot_path'] = info.snapshot_path
                yield info

        import unittest.mock as mock
        with mock.patch.object(sd_module, 'create_save_snapshot', recording_create):
            result = discover_save_structure(str(tres_path))

        assert result.success is True
        assert recorded.get('snapshot_path')
        assert Path(recorded['snapshot_path']).exists() is False

    def test_snapshot_removed_after_error(self, tmp_path, monkeypatch):
        import contextlib
        import mr_farmboy_manager.godot_tres as gt
        import mr_farmboy_manager.save_discovery as sd_module
        import unittest.mock as mock

        monkeypatch.setattr(gt, 'MAX_GODOT_SECTION_COUNT', 1)
        tres_path = tmp_path / "save.tres"
        # Forca um erro estrutural de limite apos o snapshot ser criado
        tres_path.write_text(
            HEADER + "\n[ext_resource type=\"Script\" path=\"res://a.gd\" id=\"1\"]\n",
            encoding='utf-8',
        )

        recorded = {}
        real_create = sd_module.create_save_snapshot

        @contextlib.contextmanager
        def recording_create(path):
            with real_create(path) as info:
                recorded['snapshot_path'] = info.snapshot_path
                yield info

        with mock.patch.object(sd_module, 'create_save_snapshot', recording_create):
            result = discover_save_structure(str(tres_path))

        assert result.success is False
        assert result.error_message is not None
        assert 'res://' not in (result.error_message or '')
        assert recorded.get('snapshot_path')
        assert Path(recorded['snapshot_path']).exists() is False


class TestIntegration:
    """Testes 43-45: integracao com discover_save_structure."""

    def test_discover_save_structure_integration(self, tmp_path):
        tres_path = tmp_path / "save.tres"
        tres_path.write_text(
            HEADER + "\n[resource]\nmoney = 100\nname = \"Fazenda\"\n",
            encoding='utf-8',
        )
        result = discover_save_structure(str(tres_path))
        assert result.success is True
        assert result.detected_format == SaveDiscoverySavedFormat.GODOT_TRES_TEXT
        assert result.godot_format_version == 3
        assert result.godot_property_count == 2
        assert result.is_textual is True
        assert result.compression_detected is False

    def test_import_from_root(self):
        from mr_farmboy_manager import GodotTresProfile as RootProfile
        from mr_farmboy_manager import is_godot_tres_text as root_is_godot
        from mr_farmboy_manager import parse_godot_tres_structure as root_parse

        assert RootProfile is GodotTresProfile
        assert root_is_godot is is_godot_tres_text
        assert root_parse is parse_godot_tres_structure

    def test_no_regression_other_formats(self, tmp_path):
        # JSON
        json_path = tmp_path / "save.json"
        json_path.write_text(json.dumps({"a": 1}))
        result = discover_save_structure(str(json_path))
        assert result.detected_format == SaveDiscoverySavedFormat.JSON_OBJECT

        # XML
        xml_path = tmp_path / "save.xml"
        xml_path.write_text("<?xml version='1.0'?><root><a>1</a></root>")
        result = discover_save_structure(str(xml_path))
        assert result.detected_format == SaveDiscoverySavedFormat.XML_VALID

        # ZIP
        zip_path = tmp_path / "save.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("data.json", '{"a": 1}')
        result = discover_save_structure(str(zip_path))
        assert result.detected_format == SaveDiscoverySavedFormat.ZIP

        # GZIP
        gzip_path = tmp_path / "save.gz"
        with gzip.open(gzip_path, 'wt', encoding='utf-8') as f:
            f.write("conteudo textual")
        result = discover_save_structure(str(gzip_path))
        assert result.detected_format == SaveDiscoverySavedFormat.GZIP

        # SQLite
        db_path = tmp_path / "save.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        result = discover_save_structure(str(db_path))
        assert result.detected_format == SaveDiscoverySavedFormat.SQLITE


class TestWarningsAndStructure:
    """Warnings sanitizados e perfis vazios."""

    @pytest.mark.parametrize(
        "parser",
        (parse_godot_tres_structure, parse_godot_tres_document),
    )
    def test_warnings_below_cap_are_preserved(self, parser):
        """Catches a collector that drops valid diagnostics before the cap."""
        data = make_tres("linha inválida\n" * 99)

        result = parser(data)

        assert result.sanitized_warnings == ("Linha fora de seção",) * 99

    @pytest.mark.parametrize(
        "parser",
        (parse_godot_tres_structure, parse_godot_tres_document),
    )
    def test_warnings_above_cap_keep_prefix_and_report_omission(self, parser):
        """Catches unbounded diagnostic collection from malformed TRES input."""
        data = make_tres("linha inválida\n" * 101)

        result = parser(data)

        assert result.sanitized_warnings[:-1] == ("Linha fora de seção",) * 100
        assert result.sanitized_warnings[-1] == "Avisos adicionais omitidos: 1"

    def test_property_outside_section_warns(self):
        profile = profile_of('solta = 1\n[resource]\na = 2\n')
        assert profile.property_count == 2
        assert any('seção' in w.lower() for w in profile.sanitized_warnings)

    def test_balanced_empty_profile(self):
        profile = profile_of('[resource]\n')
        assert profile.is_valid is True
        assert profile.total_section_count == 2  # header + resource
        assert profile.property_count == 0
        assert profile.variant_category_counts == ()

    def test_mismatched_brackets_raise(self):
        # Delimitadores devem fechar o mesmo tipo aberto: () [] {}
        for bad in ('a = [1, 2)', 'a = {"x": 1]', 'a = Vector2(1, 2]'):
            with pytest.raises(GodotTresParseError):
                profile_of('[resource]\n' + bad + '\n')

    def test_structure_error_message_is_sanitized(self):
        with pytest.raises(GodotTresParseError) as excinfo:
            profile_of('[resource]\na = [1, 2)')
        msg = str(excinfo.value)
        assert '1' not in msg and '2' not in msg

    def test_unclosed_structure_raises(self):
        for bad in ('a = [1, 2', 'a = {"x": 1', 'a = Vector2(1, 2'):
            with pytest.raises(GodotTresParseError):
                profile_of('[resource]\n' + bad)

    def test_unclosed_string_raises(self):
        with pytest.raises(GodotTresParseError):
            profile_of('[resource]\ns = "abc')

    def test_error_message_sanitized_for_non_utf8(self):
        with pytest.raises(GodotTresParseError) as excinfo:
            parse_godot_tres_structure(b'\x00\xff\xfe binary')
        msg = str(excinfo.value)
        assert msg == "Arquivo não é texto UTF-8"
