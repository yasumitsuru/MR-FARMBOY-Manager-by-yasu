"""Parser estrutural sanitizado para Text Resources do Godot 4 (.tres).

Reconhece a serializacao ResourceFormatSaverText do Godot 4 e produz apenas
metadados estruturais agregados. Nunca expoe nomes de propriedades, valores,
identificadores, caminhos ou conteudo do arquivo.

Seguranca:
- Scanner deterministico de linhas logicas (sem eval/exec/pickle/ast.literal_eval).
- Limites conservadores de tamanho de linha, profundidade, propriedades e secoes.
- Erros com mensagens estaticas sanitizadas (sem conteudo do arquivo).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
    - atributo format presente e numerico.
    """
    prefix = "[gd_resource"
    if not line.startswith(prefix):
        return False
    rest = line[len(prefix):]
    if rest and not (rest[0].isspace() or rest[0] == "]"):
        return False
    if not line.endswith("]"):
        return False
    # Detector Godot 4 desta tarefa: exige format == 3 fora de strings
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


# ---------------------------------------------------------------------------
# Scanner de linhas logicas
# ---------------------------------------------------------------------------

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


class _TresParser:
    """Scanner deterministico de linhas logicas de um documento .tres."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.warnings: list[str] = []
        self.format_version: int | None = None
        self.has_header = False
        self.header_seen = False
        self.total_sections = 0
        self.ext_count = 0
        self.sub_count = 0
        self.resource_count = 0
        self.property_count = 0
        self.comment_count = 0
        self.blank_line_count = 0
        self.category_counts: dict[str, int] = {}
        self.current_section: str | None = None
        # estado do scanner
        self.logical: list[str] = []
        self.logical_len = 0
        self.in_single = False
        self.in_double = False
        self.escaped = False
        self.depth_stack: list[str] = []
        self.max_depth = 0

    # -- limites -----------------------------------------------------------
    def _check_limits(self) -> None:
        if self.logical_len > MAX_GODOT_LOGICAL_LINE_LENGTH:
            raise GodotTresParseError("Linha lógica acima do limite")
        if self.max_depth > MAX_GODOT_NESTING_DEPTH:
            raise GodotTresParseError("Profundidade de aninhamento excedida")

    def _check_section_limit(self) -> None:
        if self.total_sections > MAX_GODOT_SECTION_COUNT:
            raise GodotTresParseError("Limite de seções excedido")

    def _check_property_limit(self) -> None:
        if self.property_count > MAX_GODOT_PROPERTY_COUNT:
            raise GodotTresParseError("Limite de propriedades excedido")

    # -- processamento de linha lógica completa ----------------------------
    def _handle_section(self, line: str) -> None:
        self.total_sections += 1
        self._check_section_limit()
        keyword = _section_keyword(line)
        if keyword == "gd_resource":
            if self.header_seen:
                raise GodotTresParseError("Cabeçalho gd_resource duplicado")
            self.header_seen = True
            self.has_header = True
            fmt = _extract_format(line)
            if fmt != 3:
                raise GodotTresParseError("Cabeçalho gd_resource inválido")
            self.format_version = fmt
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
            self.warnings.append("Seção desconhecida")
            self.current_section = None

    def _process_line(self, line: str) -> None:
        stripped = line.strip()
        if not stripped:
            return
        if not self.header_seen:
            # O cabecalho gd_resource deve ser a primeira linha estrutural
            keyword = (
                _section_keyword(stripped)
                if stripped.startswith("[") and stripped.endswith("]")
                else ""
            )
            if keyword == "gd_resource":
                self._handle_section(stripped)
                return
            if stripped.startswith("[gd_resource"):
                raise GodotTresParseError("Cabeçalho gd_resource inválido")
            raise GodotTresParseError("Conteúdo antes do cabeçalho gd_resource")
        # Linha de secao: [palavra ...] completa na propria linha logica
        if stripped.startswith("[") and stripped.endswith("]"):
            self._handle_section(stripped)
            return
        # Propriedade: chave = valor com '=' em profundidade 0
        eq_index = _find_top_level_equals(stripped)
        if eq_index is not None:
            key_part = stripped[:eq_index].strip()
            rhs = stripped[eq_index + 1:]
            if not key_part:
                self.warnings.append("Propriedade sem chave")
                return
            # Propriedades validas apenas em secoes [resource] ou [sub_resource]
            if self.current_section not in ("resource", "sub_resource"):
                self.warnings.append("Propriedade fora de seção")
            self.property_count += 1
            self._check_property_limit()
            category = _classify_rhs(rhs)
            self.category_counts[category] = self.category_counts.get(category, 0) + 1
            return
        self.warnings.append("Linha fora de seção")

    def _flush_logical(self) -> None:
        if not self.logical:
            return
        line = "".join(self.logical)
        self.logical = []
        self.logical_len = 0
        self._process_line(line)

    # -- scan principal ------------------------------------------------------
    def run(self) -> GodotTresProfile:
        # splitlines() nao gera elemento vazio extra para o \n final
        for line in self.text.splitlines():
            if not self.logical:
                stripped = line.strip()
                if not stripped:
                    self.blank_line_count += 1
                    continue
                if stripped.startswith("#"):
                    # Linha de comentario: conta e segue em frente
                    self.comment_count += 1
                    continue
            self._scan_physical(line)
            if not self.depth_stack and not self.in_double and not self.in_single:
                self._flush_logical()
            else:
                self.logical.append("\n")
                self.logical_len += 1
                self._check_limits()

        if self.logical:
            if self.depth_stack or self.in_double or self.in_single:
                raise GodotTresParseError("Estrutura não fechada")
            self._flush_logical()

        if not self.header_seen:
            raise GodotTresParseError("Cabeçalho gd_resource ausente")

        return GodotTresProfile(
            format_version=self.format_version,
            total_section_count=self.total_sections,
            ext_resource_count=self.ext_count,
            sub_resource_count=self.sub_count,
            resource_section_count=self.resource_count,
            property_count=self.property_count,
            comment_count=self.comment_count,
            blank_line_count=self.blank_line_count,
            variant_category_counts=tuple(sorted(self.category_counts.items())),
            has_gd_resource_header=self.has_header,
            is_valid=True,
            sanitized_warnings=tuple(self.warnings),
        )

    def _scan_physical(self, line: str) -> None:
        """Escaneia uma linha fisica atualizando strings, escapes e profundidade."""
        index = 0
        length = len(line)
        while index < length:
            char = line[index]
            if self.escaped:
                self.logical.append(char)
                self.logical_len += 1
                self.escaped = False
                index += 1
                self._check_limits()
                continue
            if self.in_double:
                self.logical.append(char)
                self.logical_len += 1
                if char == "\\":
                    self.escaped = True
                elif char == '"':
                    self.in_double = False
                index += 1
                self._check_limits()
                continue
            if self.in_single:
                self.logical.append(char)
                self.logical_len += 1
                if char == "\\":
                    self.escaped = True
                elif char == "'":
                    self.in_single = False
                index += 1
                self._check_limits()
                continue
            if char == "#":
                # Comentario fora de string: vai ate o fim da linha fisica
                self.comment_count += 1
                break
            if char == '"':
                self.in_double = True
                self.logical.append(char)
                self.logical_len += 1
            elif char == "'":
                self.in_single = True
                self.logical.append(char)
                self.logical_len += 1
            elif char in "([{":
                self.depth_stack.append(char)
                self.max_depth = max(self.max_depth, len(self.depth_stack))
                self.logical.append(char)
                self.logical_len += 1
            elif char in ")]}":
                if self.depth_stack:
                    opener = self.depth_stack.pop()
                    if _PAIRS.get(opener) != char:
                        raise GodotTresParseError("Estrutura incompatível")
                else:
                    raise GodotTresParseError("Estrutura desbalanceada")
                self.logical.append(char)
                self.logical_len += 1
            else:
                self.logical.append(char)
                self.logical_len += 1
            index += 1
            self._check_limits()


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
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise GodotTresParseError("Arquivo não é texto UTF-8")
    parser = _TresParser(text)
    return parser.run()


__all__ = [
    "GodotTresProfile",
    "GodotTresParseError",
    "is_godot_tres_text",
    "parse_godot_tres_structure",
]
