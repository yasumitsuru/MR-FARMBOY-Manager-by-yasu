"""Parsers estrutural e tipado para Text Resources do Godot 4 (.tres).

Reconhece a serializacao ResourceFormatSaverText do Godot 4 e produz:

- GodotTresProfile: metadados estruturais agregados (sanitizado);
- GodotTresDocument: modelo tipado com propriedades e valores GodotVariant
  (repr sempre redigido), base para parsers de dominio futuros.

Nunca expoe nomes de propriedades, valores, identificadores, caminhos ou
conteudo do arquivo em relatorios, reprs ou mensagens de erro.

Seguranca:
- Scanner deterministico compartilhado de linhas logicas (sem eval/exec/pickle).
- Limites conservadores de tamanho de linha, profundidade, propriedades e
  secoes.
- Erros com mensagens estaticas sanitizadas (sem conteudo do arquivo).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto

from .godot_variant import (
    GodotVariant,
    GodotVariantKind,
    GodotVariantLimitError,
    GodotVariantParseError,
    parse_godot_variant,
)

# ---------------------------------------------------------------------------
# Limites de seguranca (valores conservadores que permitem arquivos de ~2,4 MB)
# ---------------------------------------------------------------------------
MAX_GODOT_LOGICAL_LINE_LENGTH = 4 * 1024 * 1024  # 4 MB de texto por linha lógica
MAX_GODOT_NESTING_DEPTH = 128  # profundidade maxima de (), [] e {}
MAX_GODOT_PROPERTY_COUNT = 1_000_000  # propriedades max. por arquivo
MAX_GODOT_SECTION_COUNT = 100_000  # secoes max. por arquivo


class GodotTresParseError(ValueError):
    """Erro estrutural sanitizado no parsing de .tres.

    A mensagem nunca contem conteudo, chave, valor, caminho ou nome de arquivo.
    """


@dataclass(frozen=True)
class GodotTresProfile:
    """Metadados estruturais sanitizados de um arquivo .tres.

    Contem apenas contagens e categorias agregadas. Nenhum nome de propriedade,
    valor, identificador, caminho ou string do jogador e armazenado.
    """

    format_version: int | None = None
    total_section_count: int = 0
    ext_resource_count: int = 0
    sub_resource_count: int = 0
    resource_section_count: int = 0
    property_count: int = 0
    comment_count: int = 0
    blank_line_count: int = 0
    variant_category_counts: tuple[tuple[str, int], ...] = ()
    has_gd_resource_header: bool = False
    is_valid: bool = False
    sanitized_warnings: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Helpers de deteccao do cabecalho
# ---------------------------------------------------------------------------

_PAIRS = {"(": ")", "[": "]", "{": "}"}

_KNOWN_SECTIONS = ("gd_resource", "ext_resource", "sub_resource", "resource")


def _decode_text(data: bytes) -> str:
    """Decodifica UTF-8 (com BOM) e lanca erro sanitizado se invalido."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise GodotTresParseError("Arquivo não é texto UTF-8")


def _extract_format(header_line: str) -> int | None:
    """Extrai o inteiro do atributo format, ignorando conteudo entre aspas.

    Um 'format' dentro de uma string (ex: type="format=3") nao e considerado.
    """
    in_double = False
    escaped = False
    index = 0
    length = len(header_line)
    while index < length:
        char = header_line[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if in_double:
            if char == "\\":
                escaped = True
            elif char == '"':
                in_double = False
            index += 1
            continue
        if char == '"':
            in_double = True
            index += 1
            continue
        # Token 'format' fora de string (delimitado por espaco/inicio)
        if header_line.startswith("format", index) and (
            index == 0 or header_line[index - 1].isspace()
        ):
            cursor = index + len("format")
            while cursor < length and header_line[cursor] in " \t":
                cursor += 1
            if cursor < length and header_line[cursor] == "=":
                cursor += 1
                while cursor < length and header_line[cursor] in " \t":
                    cursor += 1
                sign = 0
                if cursor < length and header_line[cursor] in "+-":
                    sign = 1
                    cursor += 1
                start = cursor
                while cursor < length and header_line[cursor].isdigit():
                    cursor += 1
                if cursor > start:
                    # Token inteiro completo: rejeita qualquer caractere nao
                    # permitido apos os digitos (ex: format=3.0, 3abc, 3_0)
                    if cursor >= length or (
                        header_line[cursor].isspace() or header_line[cursor] == "]"
                    ):
                        return int(header_line[start - sign:cursor])
                return None
            # 'format' sem '=' (ex: formatting) - token diferente, continua
        index += 1
    return None


def _looks_like_gd_resource_header(line: str) -> bool:
    """Verifica se uma linha e um cabecalho gd_resource sintaticamente valido.

    Exige:
    - inicio exato [gd_resource seguido de espaco ou ];
    - fechamento com ] na mesma linha;
    - atributo format presente e igual a 3 (Godot 4), fora de strings.
    """
    prefix = "[gd_resource"
    if not line.startswith(prefix):
        return False
    rest = line[len(prefix):]
    if rest and not (rest[0].isspace() or rest[0] == "]"):
        return False
    if not line.endswith("]"):
        return False
    return _extract_format(line) == 3


def is_godot_tres_text(data: bytes) -> bool:
    """Detecta pelo conteudo se os dados sao um Text Resource do Godot 4.

    Aceita BOM UTF-8, CRLF/LF, linhas vazias e comentarios (#) iniciais.
    A primeira linha estrutural deve ser um cabecalho gd_resource valido.
    """
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    for line in text.split("\n"):
        stripped = line.rstrip("\r").strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        return _looks_like_gd_resource_header(stripped)
    return False


def _extract_quoted_attribute(line: str, attr: str) -> str | None:
    """Extrai o valor entre aspas de um atributo (ex: type="X"), fora de strings.

    Usado apenas internamente para atributos de secoes; nunca exposto em repr.
    """
    in_double = False
    escaped = False
    index = 0
    length = len(line)
    while index < length:
        char = line[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if in_double:
            if char == "\\":
                escaped = True
            elif char == '"':
                in_double = False
            index += 1
            continue
        if char == '"':
            in_double = True
            index += 1
            continue
        if line.startswith(attr, index) and (
            index == 0 or line[index - 1].isspace() or line[index - 1] == "["
        ):
            cursor = index + len(attr)
            while cursor < length and line[cursor] in " \t":
                cursor += 1
            if cursor < length and line[cursor] == "=":
                cursor += 1
                while cursor < length and line[cursor] in " \t":
                    cursor += 1
                if cursor < length and line[cursor] == '"':
                    cursor += 1
                    start = cursor
                    while cursor < length and line[cursor] != '"':
                        if line[cursor] == "\\":
                            cursor += 1
                        cursor += 1
                    if cursor < length:
                        return line[start:cursor]
            return None
        index += 1
    return None


# ---------------------------------------------------------------------------
# Classificacao estrutural do lado direito de propriedades
# ---------------------------------------------------------------------------

_INT_RE = re.compile(r"[+-]?\d+\Z")
_FLOAT_RE = re.compile(r"[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?\Z")
_CONSTRUCTOR_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _classify_rhs(rhs: str) -> str:
    """Classifica apenas a categoria estrutural do lado direito, sem avaliar.

    Nunca converte ou expoe argumentos, strings ou IDs.
    """
    value = rhs.strip()
    if not value:
        return "unknown"
    lowered = value.lower()
    if lowered == "null":
        return "null"
    if lowered in ("true", "false"):
        return "bool"
    if _INT_RE.match(value):
        return "integer"
    if _FLOAT_RE.match(value):
        return "float"
    if value.startswith('"') or value.startswith("'"):
        return "string"
    if value.startswith("["):
        return "array"
    if value.startswith("{"):
        return "dictionary"
    match = _CONSTRUCTOR_RE.match(value)
    if match is not None:
        name = match.group(1)
        if name == "ExtResource":
            return "ext_resource_reference"
        if name == "SubResource":
            return "sub_resource_reference"
        if name == "NodePath":
            return "node_path"
        if name.startswith("Vector"):
            return "vector"
        if name == "Color":
            return "color"
        if name.startswith("Packed") and name.endswith("Array"):
            return "packed_array"
        return "constructor_other"
    return "unknown"


def _find_top_level_equals(logical: str) -> int | None:
    """Indice do primeiro '=' em profundidade 0, fora de strings e estruturas."""
    in_single = False
    in_double = False
    escaped = False
    depth = 0
    for index, char in enumerate(logical):
        if escaped:
            escaped = False
            continue
        if in_double or in_single:
            if char == "\\":
                escaped = True
            elif in_double and char == '"':
                in_double = False
            elif in_single and char == "'":
                in_single = False
            continue
        if char == '"':
            in_double = True
        elif char == "'":
            in_single = True
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == "=" and depth == 0:
            return index
    return None


def _section_keyword(line: str) -> str:
    """Extrai a palavra-chave de uma linha de secao [palavra ...]."""
    inner = line[1:].lstrip()
    match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", inner)
    return match.group(1) if match else ""


def _is_section_line(stripped: str) -> bool:
    return stripped.startswith("[") and stripped.endswith("]")


# ---------------------------------------------------------------------------
# Scanner compartilhado de linhas logicas
# ---------------------------------------------------------------------------


class _LogicalLineScanner:
    """Scanner deterministico compartilhado de linhas logicas .tres.

    Gera as linhas logicas completas (Variants multilinha unificados) e
    acumula contagens de comentarios, linhas em branco e profundidade maxima.
    Valida strings, escapes, delimitadores e limites estruturais.
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self.comment_count = 0
        self.blank_line_count = 0
        self.max_depth = 0
        self._logical: list[str] = []
        self._logical_len = 0
        self._in_single = False
        self._in_double = False
        self._escaped = False
        self._depth_stack: list[str] = []

    def _check_limits(self) -> None:
        if self._logical_len > MAX_GODOT_LOGICAL_LINE_LENGTH:
            raise GodotTresParseError("Linha lógica acima do limite")
        if self.max_depth > MAX_GODOT_NESTING_DEPTH:
            raise GodotTresParseError("Profundidade de aninhamento excedida")

    def _scan_physical(self, line: str) -> None:
        """Escaneia uma linha fisica atualizando strings, escapes e profundidade."""
        index = 0
        length = len(line)
        while index < length:
            char = line[index]
            if self._escaped:
                self._logical.append(char)
                self._logical_len += 1
                self._escaped = False
                index += 1
                self._check_limits()
                continue
            if self._in_double:
                self._logical.append(char)
                self._logical_len += 1
                if char == "\\":
                    self._escaped = True
                elif char == '"':
                    self._in_double = False
                index += 1
                self._check_limits()
                continue
            if self._in_single:
                self._logical.append(char)
                self._logical_len += 1
                if char == "\\":
                    self._escaped = True
                elif char == "'":
                    self._in_single = False
                index += 1
                self._check_limits()
                continue
            if char == "#":
                # Comentario fora de string: vai ate o fim da linha fisica
                self.comment_count += 1
                break
            if char == '"':
                self._in_double = True
                self._logical.append(char)
                self._logical_len += 1
            elif char == "'":
                self._in_single = True
                self._logical.append(char)
                self._logical_len += 1
            elif char in "([{":
                self._depth_stack.append(char)
                self.max_depth = max(self.max_depth, len(self._depth_stack))
                self._logical.append(char)
                self._logical_len += 1
            elif char in ")]}":
                if self._depth_stack:
                    opener = self._depth_stack.pop()
                    if _PAIRS.get(opener) != char:
                        raise GodotTresParseError("Estrutura incompatível")
                else:
                    raise GodotTresParseError("Estrutura desbalanceada")
                self._logical.append(char)
                self._logical_len += 1
            else:
                self._logical.append(char)
                self._logical_len += 1
            index += 1
            self._check_limits()

    def __iter__(self):
        # splitlines() nao gera elemento vazio extra para o \n final
        for physical in self.text.splitlines():
            if not self._logical:
                stripped = physical.strip()
                if not stripped:
                    self.blank_line_count += 1
                    continue
                if stripped.startswith("#"):
                    self.comment_count += 1
                    continue
            self._scan_physical(physical)
            if not self._depth_stack and not self._in_double and not self._in_single:
                yield "".join(self._logical)
                self._logical = []
                self._logical_len = 0
            else:
                self._logical.append("\n")
                self._logical_len += 1
                self._check_limits()
        if self._logical:
            if self._depth_stack or self._in_double or self._in_single:
                raise GodotTresParseError("Estrutura não fechada")
            yield "".join(self._logical)
            self._logical = []


class _SharedSectionTracker:
    """Estado compartilhado de secoes entre os parsers estrutural e tipado."""

    def __init__(self) -> None:
        self.header_seen = False
        self.has_header = False
        self.format_version: int | None = None
        self.total_sections = 0
        self.ext_count = 0
        self.sub_count = 0
        self.resource_count = 0
        self.property_count = 0
        self.current_section: str | None = None

    def handle(self, keyword: str, line: str) -> None:
        self.total_sections += 1
        if self.total_sections > MAX_GODOT_SECTION_COUNT:
            raise GodotTresParseError("Limite de seções excedido")
        if keyword == "gd_resource":
            if self.header_seen:
                raise GodotTresParseError("Cabeçalho gd_resource duplicado")
            self.header_seen = True
            self.has_header = True
            if _extract_format(line) != 3:
                raise GodotTresParseError("Cabeçalho gd_resource inválido")
            self.format_version = 3
            self.current_section = "gd_resource"
        elif keyword == "ext_resource":
            self.ext_count += 1
            self.current_section = "ext_resource"
        elif keyword == "sub_resource":
            self.sub_count += 1
            self.current_section = "sub_resource"
        elif keyword == "resource":
            self.resource_count += 1
            if self.resource_count > 1:
                raise GodotTresParseError("Múltiplas seções de recurso")
            self.current_section = "resource"
        else:
            self.current_section = None

    def property_in_valid_section(self) -> bool:
        return self.current_section in ("resource", "sub_resource")

    def bump_property(self) -> None:
        self.property_count += 1
        if self.property_count > MAX_GODOT_PROPERTY_COUNT:
            raise GodotTresParseError("Limite de propriedades excedido")


def _ensure_header_or_raise(
    stripped: str, tracker: _SharedSectionTracker
) -> bool:
    """Valida a primeira linha estrutural. True se era o cabecalho gd_resource."""
    keyword = (
        _section_keyword(stripped)
        if _is_section_line(stripped)
        else ""
    )
    if keyword == "gd_resource":
        tracker.handle("gd_resource", stripped)
        return True
    if stripped.startswith("[gd_resource"):
        raise GodotTresParseError("Cabeçalho gd_resource inválido")
    raise GodotTresParseError("Conteúdo antes do cabeçalho gd_resource")


# ---------------------------------------------------------------------------
# Modelos tipados do documento (repr sempre redigido)
# ---------------------------------------------------------------------------


class GodotTresSectionKind(Enum):
    GD_RESOURCE = auto()
    EXT_RESOURCE = auto()
    SUB_RESOURCE = auto()
    RESOURCE = auto()
    UNKNOWN = auto()


@dataclass(frozen=True, repr=False)
class GodotTresProperty:
    """Propriedade tipada de uma secao .tres.

    O nome e armazenado internamente para uso futuro por parsers de dominio,
    mas repr()/str() nunca o expoem.
    """

    _name: str
    variant: GodotVariant
    section_index: int
    ordinal_index: int

    @property
    def name(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return (
            f"GodotTresProperty(ordinal_index={self.ordinal_index}, "
            f"section_index={self.section_index})"
        )

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class GodotTresSection:
    """Secao estrutural .tres com suas propriedades tipadas.

    Atributos internos (tipo/identificador) sao armazenados para uso futuro,
    mas nunca aparecem em repr()/str().
    """

    kind: GodotTresSectionKind
    ordinal_index: int
    properties: tuple[GodotTresProperty, ...]
    _type_name: str | None = None
    _identifier: str | None = None

    def __repr__(self) -> str:
        return (
            f"GodotTresSection(kind={self.kind.name}, "
            f"ordinal_index={self.ordinal_index}, "
            f"property_count={len(self.properties)})"
        )

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class GodotTresDocument:
    """Documento .tres tipado e sanitizado.

    repr()/str() exibem apenas metadados agregados (formatos, contagens).
    """

    format_version: int | None
    sections: tuple[GodotTresSection, ...]
    total_property_count: int
    parsed_variant_count: int
    opaque_variant_count: int
    max_nesting_depth: int
    sanitized_warnings: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            f"GodotTresDocument(format_version={self.format_version}, "
            f"section_count={len(self.sections)}, "
            f"property_count={self.total_property_count}, "
            f"parsed_variant_count={self.parsed_variant_count}, "
            f"opaque_variant_count={self.opaque_variant_count})"
        )

    __str__ = __repr__


# ---------------------------------------------------------------------------
# Parser estrutural (sanitizado)
# ---------------------------------------------------------------------------


def parse_godot_tres_structure(data: bytes) -> GodotTresProfile:
    """Analisa a estrutura sanitizada de um Text Resource do Godot 4.

    Args:
        data: Conteudo bruto do arquivo (ja limitado pelo chamador).

    Returns:
        GodotTresProfile com metadados estruturais agregados.

    Raises:
        GodotTresParseError: documento invalido ou limite excedido.
            A mensagem e sempre sanitizada (sem conteudo, chave, valor, caminho).
    """
    text = _decode_text(data)
    scanner = _LogicalLineScanner(text)
    tracker = _SharedSectionTracker()
    warnings: list[str] = []
    category_counts: dict[str, int] = {}

    for line in scanner:
        stripped = line.strip()
        if not stripped:
            continue
        if not tracker.header_seen:
            if _ensure_header_or_raise(stripped, tracker):
                continue
        if _is_section_line(stripped):
            keyword = _section_keyword(stripped)
            if keyword not in _KNOWN_SECTIONS:
                warnings.append("Seção desconhecida")
            tracker.handle(keyword, stripped)
            continue
        eq_index = _find_top_level_equals(stripped)
        if eq_index is not None:
            key_part = stripped[:eq_index].strip()
            rhs = stripped[eq_index + 1:]
            if not key_part:
                warnings.append("Propriedade sem chave")
                continue
            # Propriedades validas apenas em secoes [resource] ou [sub_resource]
            if not tracker.property_in_valid_section():
                warnings.append("Propriedade fora de seção")
            tracker.bump_property()
            category = _classify_rhs(rhs)
            category_counts[category] = category_counts.get(category, 0) + 1
            continue
        warnings.append("Linha fora de seção")

    if not tracker.header_seen:
        raise GodotTresParseError("Cabeçalho gd_resource ausente")

    return GodotTresProfile(
        format_version=tracker.format_version,
        total_section_count=tracker.total_sections,
        ext_resource_count=tracker.ext_count,
        sub_resource_count=tracker.sub_count,
        resource_section_count=tracker.resource_count,
        property_count=tracker.property_count,
        comment_count=scanner.comment_count,
        blank_line_count=scanner.blank_line_count,
        variant_category_counts=tuple(sorted(category_counts.items())),
        has_gd_resource_header=tracker.has_header,
        is_valid=True,
        sanitized_warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Parser tipado de documento
# ---------------------------------------------------------------------------


def parse_godot_tres_document(data: bytes) -> GodotTresDocument:
    """Analisa um Text Resource do Godot 4 em um modelo tipado sanitizado.

    Compartilha o scanner de linhas logicas com parse_godot_tres_structure.
    Valores nao interpretaveis viram GodotVariantKind.OPAQUE (com warning
    sanitizado) e o documento continua, desde que a estrutura externa esteja
    balanceada e dentro dos limites.

    Raises:
        GodotTresParseError: erros estruturais graves do documento.
    """
    text = _decode_text(data)
    scanner = _LogicalLineScanner(text)
    tracker = _SharedSectionTracker()
    warnings: list[str] = []
    sections: list[GodotTresSection] = []
    property_lists: list[list[GodotTresProperty]] = []
    property_ordinal = 0
    parsed_count = 0
    opaque_count = 0

    def _append_section(kind: GodotTresSectionKind, line: str) -> None:
        sections.append(
            GodotTresSection(
                kind=kind,
                ordinal_index=len(sections),
                properties=(),
                _type_name=_extract_quoted_attribute(line, "type"),
                _identifier=_extract_quoted_attribute(line, "id"),
            )
        )
        property_lists.append([])

    for line in scanner:
        stripped = line.strip()
        if not stripped:
            continue
        if not tracker.header_seen:
            if _ensure_header_or_raise(stripped, tracker):
                _append_section(GodotTresSectionKind.GD_RESOURCE, stripped)
                continue
        if _is_section_line(stripped):
            keyword = _section_keyword(stripped)
            if keyword not in _KNOWN_SECTIONS:
                warnings.append("Seção desconhecida")
            tracker.handle(keyword, stripped)
            if keyword == "ext_resource":
                _append_section(GodotTresSectionKind.EXT_RESOURCE, stripped)
            elif keyword == "sub_resource":
                _append_section(GodotTresSectionKind.SUB_RESOURCE, stripped)
            elif keyword == "resource":
                _append_section(GodotTresSectionKind.RESOURCE, stripped)
            else:
                _append_section(GodotTresSectionKind.UNKNOWN, stripped)
            continue
        eq_index = _find_top_level_equals(stripped)
        if eq_index is not None:
            key = stripped[:eq_index].strip()
            rhs = stripped[eq_index + 1:]
            if not key:
                warnings.append("Propriedade sem chave")
                continue
            if not tracker.property_in_valid_section():
                warnings.append("Propriedade fora de seção")
            tracker.bump_property()
            try:
                value = parse_godot_variant(rhs)
                parsed_count += 1
            except GodotVariantLimitError:
                # Limites devem interromper com erro estrutural, nao OPAQUE
                raise GodotTresParseError("Limite de segurança excedido") from None
            except GodotVariantParseError:
                # Apenas erros de sintaxe/valores nao suportados recuperaveis viram OPAQUE
                value = GodotVariant(kind=GodotVariantKind.OPAQUE)
                opaque_count += 1
                warnings.append("Valor não interpretado")
            if property_lists:
                property_lists[-1].append(
                    GodotTresProperty(
                        _name=key,
                        variant=value,
                        section_index=len(sections) - 1,
                        ordinal_index=property_ordinal,
                    )
                )
            property_ordinal += 1
            continue
        warnings.append("Linha fora de seção")

    if not tracker.header_seen:
        raise GodotTresParseError("Cabeçalho gd_resource ausente")

    final_sections = tuple(
        GodotTresSection(
            kind=section.kind,
            ordinal_index=section.ordinal_index,
            properties=tuple(property_lists[index]),
            _type_name=section._type_name,
            _identifier=section._identifier,
        )
        for index, section in enumerate(sections)
    )

    return GodotTresDocument(
        format_version=tracker.format_version,
        sections=final_sections,
        total_property_count=tracker.property_count,
        parsed_variant_count=parsed_count,
        opaque_variant_count=opaque_count,
        max_nesting_depth=scanner.max_depth,
        sanitized_warnings=tuple(warnings),
    )


__all__ = [
    "GodotTresProfile",
    "GodotTresParseError",
    "GodotTresDocument",
    "GodotTresSection",
    "GodotTresProperty",
    "GodotTresSectionKind",
    "is_godot_tres_text",
    "parse_godot_tres_structure",
    "parse_godot_tres_document",
]
