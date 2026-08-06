"""Tests for the typed Godot Variant parser and .tres document parser - Tarefa 2.6.

Todos os exemplos sao sinteticos e pequenos. Nenhum nome, valor, ID, caminho
ou estrutura proveniente de saves reais e usado aqui.
"""

import gzip
import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from mr_farmboy_manager.godot_variant import (
    GodotVariant,
    GodotVariantKind,
    GodotVariantLimitError,
    GodotVariantParseError,
    parse_godot_variant,
)
from mr_farmboy_manager.godot_tres import (
    GodotTresDocument,
    GodotTresParseError,
    GodotTresProperty,
    GodotTresSection,
    GodotTresSectionKind,
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


def variant(text: str) -> GodotVariant:
    return parse_godot_variant(text)


class TestScalars:
    """Testes 1-19: escalares."""

    def test_null(self):
        v = variant('null')
        assert v.kind == GodotVariantKind.NULL

    def test_true(self):
        v = variant('true')
        assert v.kind == GodotVariantKind.BOOL
        assert v.value is True

    def test_false(self):
        v = variant('false')
        assert v.kind == GodotVariantKind.BOOL
        assert v.value is False

    def test_positive_integer(self):
        v = variant('42')
        assert v.kind == GodotVariantKind.INTEGER
        assert v.value == 42

    def test_negative_integer(self):
        v = variant('-17')
        assert v.kind == GodotVariantKind.INTEGER
        assert v.value == -17

    def test_positive_sign_integer(self):
        v = variant('+8')
        assert v.kind == GodotVariantKind.INTEGER
        assert v.value == 8

    def test_decimal_float(self):
        v = variant('1.0')
        assert v.kind == GodotVariantKind.FLOAT
        assert v.value == 1.0

    def test_dot_leading_float(self):
        v = variant('.5')
        assert v.kind == GodotVariantKind.FLOAT
        assert v.value == 0.5

    def test_exponent_float(self):
        v = variant('1e3')
        assert v.kind == GodotVariantKind.FLOAT
        assert v.value == 1000.0

    def test_negative_exponent_float(self):
        v = variant('-2E-4')
        assert v.kind == GodotVariantKind.FLOAT
        assert v.value == pytest.approx(-0.0002)

    def test_empty_string(self):
        v = variant('""')
        assert v.kind == GodotVariantKind.STRING
        assert v.value == ''

    def test_common_string(self):
        v = variant('"texto"')
        assert v.kind == GodotVariantKind.STRING
        assert v.value == 'texto'

    def test_escaped_quote(self):
        v = variant('"a\\"b"')
        assert v.kind == GodotVariantKind.STRING
        assert v.value == 'a"b'

    def test_escaped_backslash(self):
        v = variant('"a\\\\b"')
        assert v.kind == GodotVariantKind.STRING
        assert v.value == 'a\\b'

    def test_escaped_newline(self):
        v = variant('"linha\\nseguinte"')
        assert v.kind == GodotVariantKind.STRING
        assert v.value == 'linha\nseguinte'

    def test_unclosed_string(self):
        with pytest.raises(GodotVariantParseError):
            variant('"abc')

    def test_invalid_escape(self):
        with pytest.raises(GodotVariantParseError):
            variant('"a\\qb"')

    def test_single_quoted_string(self):
        # Alinhamento com o classificador estrutural: aspas simples
        # tambem sao aceitas como delimitador de string (Godot usa duplas,
        # mas o parser estrutural classifica '...' como string).
        v = variant("'texto'")
        assert v.kind == GodotVariantKind.STRING
        assert v.value == 'texto'

    def test_string_name_literal(self):
        v = variant('&"identificador"')
        assert v.kind == GodotVariantKind.STRING_NAME
        assert v.value == 'identificador'

    def test_node_path_literal(self):
        v = variant('^"Caminho/Interno"')
        assert v.kind == GodotVariantKind.NODE_PATH_LITERAL
        assert v.value == 'Caminho/Interno'


class TestArrays:
    """Testes 20-25: arrays."""

    def test_empty_array(self):
        v = variant('[]')
        assert v.kind == GodotVariantKind.ARRAY
        assert len(v.items) == 0

    def test_simple_array(self):
        v = variant('[1, 2, 3]')
        assert v.kind == GodotVariantKind.ARRAY
        assert len(v.items) == 3
        assert [i.kind for i in v.items] == [GodotVariantKind.INTEGER] * 3

    def test_multiline_array(self):
        v = variant('[\n    1,\n    "texto",\n    false\n]')
        assert len(v.items) == 3
        assert v.items[1].kind == GodotVariantKind.STRING
        assert v.items[2].kind == GodotVariantKind.BOOL

    def test_nested_array(self):
        v = variant('[[1], [2]]')
        assert len(v.items) == 2
        assert v.items[0].kind == GodotVariantKind.ARRAY

    def test_trailing_comma_array(self):
        v = variant('[1, 2, ]')
        assert len(v.items) == 2

    def test_missing_item_array(self):
        with pytest.raises(GodotVariantParseError):
            variant('[1, , 2]')


class TestDictionaries:
    """Testes 26-31: dicionarios."""

    def test_empty_dict(self):
        v = variant('{}')
        assert v.kind == GodotVariantKind.DICTIONARY
        assert len(v.entries) == 0

    def test_simple_dict(self):
        v = variant('{"a": 1}')
        assert len(v.entries) == 1
        key, value = v.entries[0]
        assert key.kind == GodotVariantKind.STRING
        assert key.value == 'a'
        assert value.value == 1

    def test_nested_dict(self):
        v = variant('{"a": {"b": [true]}}')
        inner = v.entries[0][1]
        assert inner.kind == GodotVariantKind.DICTIONARY
        inner_val = inner.entries[0][1]
        assert inner_val.kind == GodotVariantKind.ARRAY

    def test_string_name_key(self):
        v = variant('{&"b": 1}')
        key, _ = v.entries[0]
        assert key.kind == GodotVariantKind.STRING_NAME
        assert key.value == 'b'

    def test_duplicate_keys_preserved(self):
        v = variant('{"a": 1, "a": 2}')
        assert len(v.entries) == 2

    def test_missing_colon(self):
        with pytest.raises(GodotVariantParseError):
            variant('{"a" 1}')


class TestConstructors:
    """Testes 32-42: construtores."""

    def test_ext_resource(self):
        v = variant('ExtResource("1")')
        assert v.kind == GodotVariantKind.EXT_RESOURCE_REFERENCE
        assert v.arguments[0].value == '1'

    def test_sub_resource(self):
        v = variant('SubResource("2")')
        assert v.kind == GodotVariantKind.SUB_RESOURCE_REFERENCE

    def test_node_path(self):
        v = variant('NodePath("A/B")')
        assert v.kind == GodotVariantKind.NODE_PATH

    def test_vector2(self):
        v = variant('Vector2(1, 2)')
        assert v.kind == GodotVariantKind.VECTOR
        assert len(v.arguments) == 2

    def test_vector3(self):
        v = variant('Vector3(1, 2, 3)')
        assert v.kind == GodotVariantKind.VECTOR
        assert len(v.arguments) == 3

    def test_color(self):
        v = variant('Color(1, 0, 0, 1)')
        assert v.kind == GodotVariantKind.COLOR
        assert len(v.arguments) == 4

    def test_packed_int32_array(self):
        v = variant('PackedInt32Array(1, 2, 3)')
        assert v.kind == GodotVariantKind.PACKED_ARRAY
        assert len(v.arguments) == 3

    def test_packed_string_array(self):
        v = variant('PackedStringArray("x", "y")')
        assert v.kind == GodotVariantKind.PACKED_ARRAY

    def test_generic_constructor(self):
        v = variant('AlgumConstrutor(1, "a")')
        assert v.kind == GodotVariantKind.CONSTRUCTOR
        assert v.name == 'AlgumConstrutor'

    def test_constructor_no_args(self):
        v = variant('Transform2D()')
        assert v.kind == GodotVariantKind.CONSTRUCTOR
        assert len(v.arguments) == 0

    def test_nested_arguments(self):
        v = variant('Color(Vector3(1, 2, 3), 1)')
        assert v.kind == GodotVariantKind.COLOR
        assert v.arguments[0].kind == GodotVariantKind.VECTOR

    def test_typed_array_constructor(self):
        # Sintaxe de array tipado do Godot 4: Array[Tipo]([...])
        v = variant('Array[String](["a", "b"])')
        assert v.kind == GodotVariantKind.ARRAY
        assert len(v.items) == 2
        assert v.items[0].kind == GodotVariantKind.STRING
        # o tipo interno e preservado (sem expor nada em repr)
        assert v.name == 'Array[String]'

    def test_typed_array_nested_type(self):
        v = variant('Array[Vector2]([Vector2(1, 2)])')
        assert v.kind == GodotVariantKind.ARRAY
        assert len(v.items) == 1
        assert v.items[0].kind == GodotVariantKind.VECTOR
        assert v.name == 'Array[Vector2]'

    def test_typed_array_no_args(self):
        v = variant('Array[String]()')
        assert v.kind == GodotVariantKind.ARRAY
        assert len(v.items) == 0
        assert v.name == 'Array[String]'


class TestErrorsAndLimits:
    """Testes 43-50 + limite de entrada: erros e limites."""

    def test_incompatible_delimiter(self):
        with pytest.raises(GodotVariantParseError):
            variant('[1, 2)')

    def test_residual_content(self):
        with pytest.raises(GodotVariantParseError):
            variant('1 2')
        with pytest.raises(GodotVariantParseError):
            variant('42abc')

    def test_unknown_token(self):
        with pytest.raises(GodotVariantParseError):
            variant('foo')

    def test_depth_limit(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv
        monkeypatch.setattr(gv, 'MAX_VARIANT_NESTING_DEPTH', 2)
        with pytest.raises(GodotVariantParseError):
            variant('[[[[1]]]]')

    def test_node_count_limit(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv
        monkeypatch.setattr(gv, 'MAX_VARIANT_NODE_COUNT', 3)
        with pytest.raises(GodotVariantParseError):
            variant('[1, 2, 3, 4]')

    def test_container_items_limit(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv
        monkeypatch.setattr(gv, 'MAX_VARIANT_CONTAINER_ITEMS', 2)
        with pytest.raises(GodotVariantParseError):
            variant('[1, 2, 3]')

    def test_string_length_limit(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv
        monkeypatch.setattr(gv, 'MAX_VARIANT_STRING_LENGTH', 3)
        with pytest.raises(GodotVariantParseError):
            variant('"abcd"')

    def test_constructor_arguments_limit(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv
        monkeypatch.setattr(gv, 'MAX_VARIANT_CONSTRUCTOR_ARGUMENTS', 2)
        with pytest.raises(GodotVariantParseError):
            variant('Vector3(1, 2, 3)')

    def test_input_length_limit(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv
        monkeypatch.setattr(gv, 'MAX_VARIANT_INPUT_LENGTH', 5)
        with pytest.raises(GodotVariantParseError):
            variant('"abcdef"')


class TestReprAndSafety:
    """Testes 51-57: repr redigido, determinismo, imutabilidade."""

    def test_repr_string_redacted(self):
        assert repr(variant('"segredo"')) == 'GodotVariant(kind=STRING, redacted=True)'

    def test_repr_integer_redacted(self):
        assert repr(variant('999999')) == 'GodotVariant(kind=INTEGER, redacted=True)'

    def test_repr_array_redacted(self):
        assert repr(variant('[1, 2, 3]')) == 'GodotVariant(kind=ARRAY, item_count=3)'

    def test_repr_dict_redacted(self):
        assert repr(variant('{"a": 1}')) == 'GodotVariant(kind=DICTIONARY, entry_count=1)'

    def test_error_message_contains_no_content(self):
        with pytest.raises(GodotVariantParseError) as excinfo:
            variant('conteudo_secreto')
        assert 'conteudo_secreto' not in str(excinfo.value)

    def test_determinism(self):
        text = '{"a": [1, 2, ExtResource("9")]}'
        assert variant(text) == variant(text)

    def test_immutability(self):
        v = variant('42')
        with pytest.raises(AttributeError):
            v.kind = GodotVariantKind.NULL


class TestDocument:
    """Testes 58-67: documento .tres."""

    def test_document_synthetic(self):
        text = (
            HEADER + '\n'
            '[ext_resource type="Script" path="res://x.gd" id="1"]\n'
            '[sub_resource type="Animation" id="1"]\n'
            'length = 1.0\n'
            '[resource]\n'
            'money = 100\n'
            'name = "Fazenda"\n'
            'items = [1, 2, 3]\n'
        )
        doc = parse_godot_tres_document(text.encode('utf-8'))
        assert isinstance(doc, GodotTresDocument)
        assert doc.format_version == 3
        assert len(doc.sections) == 4
        assert doc.total_property_count == 4
        assert doc.parsed_variant_count == 4
        assert doc.opaque_variant_count == 0

    def test_properties_associated_with_sections(self):
        text = (
            HEADER + '\n'
            '[sub_resource type="Animation" id="1"]\n'
            'length = 1.0\n'
            '[resource]\n'
            'money = 100\n'
        )
        doc = parse_godot_tres_document(text.encode('utf-8'))
        sub_section = doc.sections[1]
        res_section = doc.sections[2]
        assert sub_section.kind == GodotTresSectionKind.SUB_RESOURCE
        assert res_section.kind == GodotTresSectionKind.RESOURCE
        length_prop = sub_section.properties[0]
        money_prop = res_section.properties[0]
        assert length_prop.section_index == 1
        assert money_prop.section_index == 2
        assert length_prop.name == 'length'
        assert money_prop.name == 'money'
        assert money_prop.variant.kind == GodotVariantKind.INTEGER

    def test_sub_resource_section(self):
        text = HEADER + '\n[sub_resource type="Animation" id="1"]\nlength = 1.0\n[resource]\n'
        doc = parse_godot_tres_document(text.encode('utf-8'))
        assert any(s.kind == GodotTresSectionKind.SUB_RESOURCE for s in doc.sections)

    def test_resource_section(self):
        text = HEADER + '\n[resource]\nmoney = 1\n'
        doc = parse_godot_tres_document(text.encode('utf-8'))
        assert any(s.kind == GodotTresSectionKind.RESOURCE for s in doc.sections)

    def test_multiple_sub_resources(self):
        text = (
            HEADER + '\n'
            '[sub_resource type="Animation" id="1"]\nlength = 1.0\n'
            '[sub_resource type="Animation" id="2"]\nlength = 2.0\n'
            '[resource]\n'
        )
        doc = parse_godot_tres_document(text.encode('utf-8'))
        subs = [s for s in doc.sections if s.kind == GodotTresSectionKind.SUB_RESOURCE]
        assert len(subs) == 2

    def test_variant_counts(self):
        text = HEADER + '\n[resource]\na = 1\nb = "x"\nc = [1, 2]\n'
        doc = parse_godot_tres_document(text.encode('utf-8'))
        assert doc.parsed_variant_count == 3
        assert doc.opaque_variant_count == 0

    def test_opaque_count(self):
        text = HEADER + '\n[resource]\ngood = 1\nbad = @@coisa@@\n'
        doc = parse_godot_tres_document(text.encode('utf-8'))
        assert doc.parsed_variant_count == 1
        assert doc.opaque_variant_count == 1
        assert any('interpretado' in w for w in doc.sanitized_warnings)

    def test_property_repr_redacted(self):
        text = HEADER + '\n[resource]\nsegredo = "valor secreto"\n'
        doc = parse_godot_tres_document(text.encode('utf-8'))
        prop = doc.sections[-1].properties[0]
        assert 'segredo' not in repr(prop)
        assert 'valor secreto' not in repr(prop)
        assert str(prop) == repr(prop)

    def test_section_repr_redacted(self):
        text = HEADER + '\n[sub_resource type="Animation" id="9"]\nlength = 1.0\n[resource]\n'
        doc = parse_godot_tres_document(text.encode('utf-8'))
        sub = [s for s in doc.sections if s.kind == GodotTresSectionKind.SUB_RESOURCE][0]
        assert 'Animation' not in repr(sub)
        assert '9' not in repr(sub)

    def test_document_repr_redacted(self):
        text = HEADER + '\n[resource]\nsegredo = "valor secreto"\n'
        doc = parse_godot_tres_document(text.encode('utf-8'))
        assert 'segredo' not in repr(doc)
        assert 'valor secreto' not in repr(doc)


class TestPackageIntegration:
    """Testes 68-70: raiz, BOM, CRLF."""

    def test_import_from_root(self):
        from mr_farmboy_manager import GodotVariant as RootVariant
        from mr_farmboy_manager import GodotVariantKind as RootKind
        from mr_farmboy_manager import GodotVariantParseError as RootError
        from mr_farmboy_manager import parse_godot_variant as root_parse_variant
        from mr_farmboy_manager import GodotTresDocument as RootDoc
        from mr_farmboy_manager import GodotTresSection as RootSection
        from mr_farmboy_manager import GodotTresProperty as RootProperty
        from mr_farmboy_manager import GodotTresSectionKind as RootSectionKind
        from mr_farmboy_manager import parse_godot_tres_document as root_parse_doc

        assert RootVariant is GodotVariant
        assert RootKind is GodotVariantKind
        assert RootError is GodotVariantParseError
        assert root_parse_variant is parse_godot_variant
        assert RootDoc is GodotTresDocument
        assert RootSection is GodotTresSection
        assert RootProperty is GodotTresProperty
        assert RootSectionKind is GodotTresSectionKind
        assert root_parse_doc is parse_godot_tres_document

    def test_bom_compatibility(self):
        data = b'\xef\xbb\xbf' + (HEADER + '\n[resource]\nmoney = 1\n').encode('utf-8')
        doc = parse_godot_tres_document(data)
        assert doc.format_version == 3
        assert doc.total_property_count == 1

    def test_crlf_compatibility(self):
        text = (HEADER + '\r\n[resource]\r\nmoney = 1\r\n').encode('utf-8')
        doc = parse_godot_tres_document(text)
        assert doc.total_property_count == 1


class TestRegression:
    """Regressao: estrutura identica, descoberta, formatos, snapshots, relatorios."""

    def test_structural_parser_counts_unchanged(self):
        text = (
            HEADER + '\n'
            '[ext_resource type="Script" path="res://x.gd" id="1"]\n'
            '[sub_resource type="Animation" id="1"]\n'
            'length = 1.0\n'
            '[resource]\n'
            'money = 100\n'
        )
        profile = parse_godot_tres_structure(text.encode('utf-8'))
        assert profile.format_version == 3
        assert profile.total_section_count == 4
        assert profile.ext_resource_count == 1
        assert profile.sub_resource_count == 1
        assert profile.resource_section_count == 1
        assert profile.property_count == 2

    def test_discover_still_godot_tres(self, tmp_path):
        tres_path = tmp_path / 'save.tres'
        tres_path.write_text(HEADER + '\n[resource]\nmoney = 100\n', encoding='utf-8')
        result = discover_save_structure(str(tres_path))
        assert result.success is True
        assert result.detected_format == SaveDiscoverySavedFormat.GODOT_TRES_TEXT
        assert result.godot_format_version == 3

    def test_no_regression_other_formats(self, tmp_path):
        json_path = tmp_path / 'save.json'
        json_path.write_text(json.dumps({'a': 1}))
        assert discover_save_structure(str(json_path)).detected_format == SaveDiscoverySavedFormat.JSON_OBJECT

        xml_path = tmp_path / 'save.xml'
        xml_path.write_text("<?xml version='1.0'?><root><a>1</a></root>")
        assert discover_save_structure(str(xml_path)).detected_format == SaveDiscoverySavedFormat.XML_VALID

        zip_path = tmp_path / 'save.zip'
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('data.json', '{"a": 1}')
        assert discover_save_structure(str(zip_path)).detected_format == SaveDiscoverySavedFormat.ZIP

        gzip_path = tmp_path / 'save.gz'
        with gzip.open(gzip_path, 'wt', encoding='utf-8') as f:
            f.write('conteudo')
        assert discover_save_structure(str(gzip_path)).detected_format == SaveDiscoverySavedFormat.GZIP

        db_path = tmp_path / 'save.db'
        conn = sqlite3.connect(str(db_path))
        conn.execute('CREATE TABLE t (id INTEGER PRIMARY KEY)')
        conn.commit()
        conn.close()
        assert discover_save_structure(str(db_path)).detected_format == SaveDiscoverySavedFormat.SQLITE

    def test_snapshot_removed_after_success(self, tmp_path):
        import contextlib
        import unittest.mock as mock
        import mr_farmboy_manager.save_discovery as sd_module

        tres_path = tmp_path / 'save.tres'
        tres_path.write_text(HEADER + '\n[resource]\nmoney = 1\n', encoding='utf-8')
        recorded = {}
        real_create = sd_module.create_save_snapshot

        @contextlib.contextmanager
        def recording_create(path):
            with real_create(path) as info:
                recorded['snapshot_path'] = info.snapshot_path
                yield info

        with mock.patch.object(sd_module, 'create_save_snapshot', recording_create):
            result = discover_save_structure(str(tres_path))
        assert result.success is True
        assert Path(recorded['snapshot_path']).exists() is False

    def test_snapshot_removed_after_error(self, tmp_path, monkeypatch):
        import contextlib
        import unittest.mock as mock
        import mr_farmboy_manager.godot_tres as gt
        import mr_farmboy_manager.save_discovery as sd_module

        monkeypatch.setattr(gt, 'MAX_GODOT_SECTION_COUNT', 1)
        tres_path = tmp_path / 'save.tres'
        tres_path.write_text(
            HEADER + '\n[ext_resource type="Script" path="res://a.gd" id="1"]\n',
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
        assert Path(recorded['snapshot_path']).exists() is False

    def test_no_content_in_reports(self, tmp_path):
        tres_path = tmp_path / 'save.tres'
        tres_path.write_text(
            HEADER + '\n[resource]\nsegredoProprietario = "valorMuitoSecreto"\n',
            encoding='utf-8',
        )
        result = discover_save_structure(str(tres_path))
        report = format_sanitized_report(result)
        assert 'segredoProprietario' not in report
        assert 'valorMuitoSecreto' not in report


class TestLimitErrorIdentity:
    """Testes para corrigir identidade de GodotVariantLimitError."""

    def test_limit_error_is_parse_error_subclass(self):
        assert issubclass(
            GodotVariantLimitError,
            GodotVariantParseError,
        )

    def test_document_limit_error_is_not_converted_to_opaque(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv

        monkeypatch.setattr(gv, "MAX_VARIANT_STRING_LENGTH", 3)

        data = (
            '[gd_resource type="Resource" format=3]\n'
            '[resource]\n'
            'campo = "abcd"\n'
        ).encode("utf-8")

        with pytest.raises(
            GodotTresParseError,
            match="Limite de segurança excedido",
        ):
            parse_godot_tres_document(data)


class TestNumberLimits:
    """Testes para limites de entrada e parsing numerico seguro."""

    def test_input_length_raises_limit_error(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv

        monkeypatch.setattr(gv, "MAX_VARIANT_INPUT_LENGTH", 3)

        with pytest.raises(GodotVariantLimitError):
            parse_godot_variant('"abcd"')

    def test_large_integer_value_is_not_limited_by_node_count(self):
        value = parse_godot_variant("999999999999999999999999")
        assert value.kind is GodotVariantKind.INTEGER
        assert value.value == 999999999999999999999999

    def test_number_length_limit(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv

        monkeypatch.setattr(gv, "MAX_VARIANT_NUMBER_LENGTH", 3)

        with pytest.raises(GodotVariantLimitError):
            parse_godot_variant("1234")

    def test_number_limit_error_is_sanitized(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv

        secret = "987654"
        monkeypatch.setattr(gv, "MAX_VARIANT_NUMBER_LENGTH", 3)

        with pytest.raises(GodotVariantLimitError) as excinfo:
            parse_godot_variant(secret)

        assert secret not in str(excinfo.value)

    def test_non_finite_float_is_rejected(self):
        with pytest.raises(GodotVariantParseError):
            parse_godot_variant("1e999999")


class TestDocumentInputLimit:
    """Testes para limites de entrada em documento .tres."""

    def test_document_input_limit_is_fatal(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv

        monkeypatch.setattr(gv, "MAX_VARIANT_INPUT_LENGTH", 3)

        data = (
            '[gd_resource type="Resource" format=3]\n'
            '[resource]\n'
            'campo = "abcd"\n'
        ).encode("utf-8")

        with pytest.raises(
            GodotTresParseError,
            match="Limite de segurança excedido",
        ):
            parse_godot_tres_document(data)


class TestContainerItemLimits:
    """Testes para limites locais de containers."""

    def test_nested_arrays_have_independent_item_limits(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv

        monkeypatch.setattr(gv, "MAX_VARIANT_CONTAINER_ITEMS", 2)

        value = parse_godot_variant("[[1, 2], [3, 4]]")

        assert value.kind is GodotVariantKind.ARRAY
        assert len(value.items) == 2
        assert all(len(item.items) == 2 for item in value.items)

    def test_array_limit_precedes_parsing_next_item(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv

        monkeypatch.setattr(gv, "MAX_VARIANT_CONTAINER_ITEMS", 2)

        with pytest.raises(
            GodotVariantLimitError,
            match="Limite de itens excedido",
        ):
            parse_godot_variant("[1, 2, token_invalido]")

    def test_dictionary_limit_precedes_parsing_next_key(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv

        monkeypatch.setattr(gv, "MAX_VARIANT_CONTAINER_ITEMS", 2)

        with pytest.raises(
            GodotVariantLimitError,
            match="Limite de entradas excedido",
        ):
            parse_godot_variant(
                '{"a": 1, "b": 2, token_invalido: 3}'
            )

    def test_constructor_limit_precedes_parsing_next_argument(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv

        monkeypatch.setattr(
            gv,
            "MAX_VARIANT_CONSTRUCTOR_ARGUMENTS",
            2,
        )

        with pytest.raises(
            GodotVariantLimitError,
            match="Limite de argumentos excedido",
        ):
            parse_godot_variant(
                "Vector3(1, 2, token_invalido)"
            )

    def test_typed_array_respects_container_item_limit(self, monkeypatch):
        import mr_farmboy_manager.godot_variant as gv

        monkeypatch.setattr(gv, "MAX_VARIANT_CONTAINER_ITEMS", 2)
        monkeypatch.setattr(
            gv,
            "MAX_VARIANT_CONSTRUCTOR_ARGUMENTS",
            10,
        )

        with pytest.raises(
            GodotVariantLimitError,
            match="Limite de itens excedido",
        ):
            parse_godot_variant("Array[int](1, 2, 3)")


class TestTypedArrayIdentifierRestrictions:
    """Testes para restrição exata do identificador de arrays tipados."""

    @pytest.mark.parametrize(
        "text",
        [
            "ArrayLike[String]()",
            "Array2[String]()",
            "ARRAY[String]()",
            "array[String]()",
            "Vector2[Float](1)",
        ],
    )
    def test_only_exact_array_identifier_accepts_typed_suffix(self, text):
        with pytest.raises(GodotVariantParseError):
            parse_godot_variant(text)

    @pytest.mark.parametrize(
        "text",
        [
            "Array[String]()",
            "Array[Vector2]([Vector2(1, 2)])",
            "Array[Array[int]]([])",
        ],
    )
    def test_exact_array_identifier_accepts_valid_typed_suffix(self, text):
        value = parse_godot_variant(text)

        assert value.kind is GodotVariantKind.ARRAY
        assert value.name is not None
        assert value.name.startswith("Array[")

    def test_empty_typed_array_type_remains_rejected(self):
        with pytest.raises(GodotVariantParseError):
            parse_godot_variant("Array[]()")

    def test_whitespace_only_typed_array_type_is_rejected(self):
        with pytest.raises(GodotVariantParseError):
            parse_godot_variant("Array[   ]()")


def test_typed_array_limit_precedes_parsing_next_direct_item(
    monkeypatch,
):
    import mr_farmboy_manager.godot_variant as gv

    monkeypatch.setattr(
        gv,
        "MAX_VARIANT_CONTAINER_ITEMS",
        2,
    )
    monkeypatch.setattr(
        gv,
        "MAX_VARIANT_CONSTRUCTOR_ARGUMENTS",
        10,
    )

    with pytest.raises(
        GodotVariantLimitError,
        match="Limite de itens excedido",
    ):
        parse_godot_variant(
            "Array[int](1, 2, token_invalido)"
        )

@pytest.mark.parametrize(
    "text",
    [
        "Array[)]()",
        "Array[Foo(]()",
        'Array["Secret"]()',
        "Array[Foo,Bar]()",
        "Array[[int]]()",
        "Array[Vector2)]()",
        "Array[Foo.Bar]()",
        "Array[Array[]]()",
        "Array[123]()",
        "Array[ARRAY[int]]()",
        "Array[array[int]]()",
        "Array[Array[int]garbage]()",
        "Array[é]()",
    ],
)
def test_invalid_typed_array_type_grammar_is_rejected(text):
    with pytest.raises(GodotVariantParseError):
        parse_godot_variant(text)


@pytest.mark.parametrize(
    "text",
    [
        "Array[int]()",
        "Array[String]()",
        "Array[Vector2]([])",
        "Array[MinhaClasse]()",
        "Array[Array]()",
        "Array[Array[int]]([])",
        "Array[Array[Vector2]]([])",
        "Array[_]()",
    ],
)
def test_valid_typed_array_type_grammar_is_accepted(text):
    value = parse_godot_variant(text)

    assert value.kind is GodotVariantKind.ARRAY


def test_typed_array_type_depth_limit(monkeypatch):
    import mr_farmboy_manager.godot_variant as gv

    monkeypatch.setattr(
        gv,
        "MAX_VARIANT_NESTING_DEPTH",
        2,
    )

    with pytest.raises(GodotVariantLimitError):
        parse_godot_variant(
            "Array[Array[Array[int]]]()"
        )
