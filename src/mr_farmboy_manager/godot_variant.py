"""Parser tipado e seguro de Variants do Godot 4.

Interpreta valores do lado direito de propriedades de Text Resources (.tres)
sem executar construtores, sem importar classes Godot e sem expor conteudo
em representacoes textuais.

Seguranca:
- Recursive descent com cursor explicito (sem eval/exec/pickle/ast.literal_eval).
- Limites conservadores de entrada, profundidade, nos, itens, strings e
  argumentos.
- repr/str sempre redigidos (nunca expoem texto, numeros, chaves, IDs, nomes
  de construtores ou caminhos).
- Erros com mensagens estaticas sanitizadas (sem parte da entrada).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto

# ---------------------------------------------------------------------------
# Limites de seguranca (permitem os saves reais validados: ~2,4 MB)
# ---------------------------------------------------------------------------
MAX_VARIANT_INPUT_LENGTH = 8 * 1024 * 1024  # 8 MB de texto por valor
MAX_VARIANT_NUMBER_LENGTH = 4096  # caracteres max. do token numerico
MAX_VARIANT_NESTING_DEPTH = 128  # profundidade maxima de containers
MAX_VARIANT_NODE_COUNT = 2_000_000  # nos max. por valor
MAX_VARIANT_CONTAINER_ITEMS = 2_000_000  # itens/entradas max. por container
MAX_VARIANT_STRING_LENGTH = 1_000_000  # caracteres max. por string
MAX_VARIANT_CONSTRUCTOR_ARGUMENTS = 2_000_000  # argumentos max. por construtor


class GodotVariantParseError(ValueError):
    """Erro sanitizado no parsing de um Variant Godot.

    A mensagem nunca contem parte da entrada (texto, numero, chave ou valor).
    """


class GodotVariantLimitError(GodotVariantParseError):
    """Erro de limite sanitizado no parsing de um Variant Godot.

    Subclasse especifica para erros excedendo limites de seguranca.
    A mensagem nunca contem parte da entrada (texto, numero, chave ou valor).
    """


class GodotVariantKind(Enum):
    """Categorias tipadas de um Variant Godot."""

    NULL = auto()
    BOOL = auto()
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()
    STRING_NAME = auto()
    NODE_PATH_LITERAL = auto()
    ARRAY = auto()
    DICTIONARY = auto()
    EXT_RESOURCE_REFERENCE = auto()
    SUB_RESOURCE_REFERENCE = auto()
    NODE_PATH = auto()
    VECTOR = auto()
    COLOR = auto()
    PACKED_ARRAY = auto()
    CONSTRUCTOR = auto()
    OPAQUE = auto()


@dataclass(frozen=True, repr=False)
class GodotVariant:
    """Representacao imutavel e tipada de um Variant Godot.

    Os valores sao armazenados internamente para uso futuro por parsers de
    dominio, mas repr() e str() sao sempre redigidos (apenas kind e contagens).
    """

    kind: GodotVariantKind
    value: object = None
    items: tuple = ()
    entries: tuple = ()
    arguments: tuple = ()
    name: str | None = None

    def __repr__(self) -> str:
        if self.kind is GodotVariantKind.ARRAY:
            return f"GodotVariant(kind=ARRAY, item_count={len(self.items)})"
        if self.kind is GodotVariantKind.DICTIONARY:
            return f"GodotVariant(kind=DICTIONARY, entry_count={len(self.entries)})"
        if self.kind in (
            GodotVariantKind.CONSTRUCTOR,
            GodotVariantKind.VECTOR,
            GodotVariantKind.COLOR,
            GodotVariantKind.PACKED_ARRAY,
            GodotVariantKind.EXT_RESOURCE_REFERENCE,
            GodotVariantKind.SUB_RESOURCE_REFERENCE,
            GodotVariantKind.NODE_PATH,
        ):
            return (
                f"GodotVariant(kind={self.kind.name}, "
                f"argument_count={len(self.arguments)})"
            )
        return f"GodotVariant(kind={self.kind.name}, redacted=True)"

    __str__ = __repr__


_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    '"': '"',
    "'": "'",
    "\\": "\\",
    "b": "\b",
    "f": "\f",
    "0": "\0",
}


def _is_valid_typed_array_type(text: str) -> bool:
    """Valida TYPE := IDENTIFIER | Array[TYPE]."""
    source = text.strip()
    if not source:
        return False

    pos = 0
    length = len(source)

    def _is_identifier_start(char: str) -> bool:
        return (
            "A" <= char <= "Z"
            or "a" <= char <= "z"
            or char == "_"
        )

    def _is_identifier_part(char: str) -> bool:
        return _is_identifier_start(char) or "0" <= char <= "9"

    def _parse_type(depth: int) -> bool:
        nonlocal pos

        if depth > MAX_VARIANT_NESTING_DEPTH:
            raise GodotVariantLimitError("Profundidade excedida")

        if pos >= length or not _is_identifier_start(source[pos]):
            return False

        start = pos
        pos += 1

        while pos < length and _is_identifier_part(source[pos]):
            pos += 1

        identifier = source[start:pos]

        if (
            identifier == "Array"
            and pos < length
            and source[pos] == "["
        ):
            pos += 1

            if not _parse_type(depth + 1):
                return False

            if pos >= length or source[pos] != "]":
                return False

            pos += 1

        return True

    return _parse_type(1) and pos == length


class _VariantParser:
    """Parser recursive descent com cursor explicito."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.node_count = 0
        self.depth = 0

    # -- utilitarios --------------------------------------------------------
    def _peek(self) -> str:
        if self.pos >= len(self.text):
            return ""
        return self.text[self.pos]

    def _skip_ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def _count_node(self) -> None:
        self.node_count += 1
        if self.node_count > MAX_VARIANT_NODE_COUNT:
            raise GodotVariantLimitError("Limite de nós excedido")

    def _enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_VARIANT_NESTING_DEPTH:
            raise GodotVariantLimitError("Profundidade excedida")

    def _leave(self) -> None:
        self.depth -= 1

    def _match_keyword(self, word: str) -> bool:
        if self.text.startswith(word, self.pos):
            end = self.pos + len(word)
            if end >= len(self.text) or not (
                self.text[end].isalnum() or self.text[end] == "_"
            ):
                self.pos = end
                return True
        return False

    # -- valor raiz ----------------------------------------------------------
    def parse(self) -> GodotVariant:
        if len(self.text) > MAX_VARIANT_INPUT_LENGTH:
            raise GodotVariantLimitError("Limite de entrada excedido")
        value = self._parse_value()
        self._skip_ws()
        if self.pos != len(self.text):
            raise GodotVariantParseError("Conteudo residual")
        return value

    # -- dispatch ------------------------------------------------------------
    def _parse_value(self) -> GodotVariant:
        self._skip_ws()
        char = self._peek()
        if not char:
            raise GodotVariantParseError("Valor vazio")
        if char in ('"', "'"):
            parsed = GodotVariant(
                kind=GodotVariantKind.STRING, value=self._parse_string(char)
            )
        elif char == "&":
            self.pos += 1
            if self._peek() != '"':
                raise GodotVariantParseError("Token desconhecido")
            parsed = GodotVariant(
                kind=GodotVariantKind.STRING_NAME, value=self._parse_string('"')
            )
        elif char == "^":
            self.pos += 1
            if self._peek() != '"':
                raise GodotVariantParseError("Token desconhecido")
            parsed = GodotVariant(
                kind=GodotVariantKind.NODE_PATH_LITERAL, value=self._parse_string('"')
            )
        elif char == "[":
            parsed = self._parse_array()
        elif char == "{":
            parsed = self._parse_dictionary()
        elif char in "+-." or char.isdigit():
            parsed = self._parse_number()
        elif self._match_keyword("null"):
            parsed = GodotVariant(kind=GodotVariantKind.NULL)
        elif self._match_keyword("true"):
            parsed = GodotVariant(kind=GodotVariantKind.BOOL, value=True)
        elif self._match_keyword("false"):
            parsed = GodotVariant(kind=GodotVariantKind.BOOL, value=False)
        elif char.isalpha() or char == "_":
            parsed = self._parse_constructor()
        else:
            raise GodotVariantParseError("Token desconhecido")
        self._count_node()
        return parsed

    # -- numeros -------------------------------------------------------------
    def _scan_digits(self) -> int:
        count = 0
        while self.pos < len(self.text) and self.text[self.pos].isdigit():
            self.pos += 1
            count += 1
        return count

    def _parse_number(self) -> GodotVariant:
        start = self.pos
        char = self._peek()
        if char in ("+", "-"):
            self.pos += 1
        digits_before = self._scan_digits()
        is_float = False
        char = self._peek()
        if char == ".":
            is_float = True
            self.pos += 1
            digits_after = self._scan_digits()
            if digits_before == 0 and digits_after == 0:
                raise GodotVariantParseError("Numero invalido")
        char = self._peek()
        if char in ("e", "E"):
            is_float = True
            self.pos += 1
            char = self._peek()
            if char in ("+", "-"):
                self.pos += 1
            if self._scan_digits() == 0:
                raise GodotVariantParseError("Numero invalido")
        token = self.text[start:self.pos]
        if len(token) > MAX_VARIANT_NUMBER_LENGTH:
            raise GodotVariantLimitError("Limite de numero excedido")
        if not any(ch.isdigit() for ch in token):
            raise GodotVariantParseError("Numero invalido")
        try:
            if is_float:
                value = float(token)
                if not math.isfinite(value):
                    raise GodotVariantParseError("Numero invalido")
                return GodotVariant(kind=GodotVariantKind.FLOAT, value=value)
            value = int(token)
            return GodotVariant(kind=GodotVariantKind.INTEGER, value=value)
        except (ValueError, OverflowError):
            raise GodotVariantLimitError("Limite de numero excedido") from None

    # -- strings -------------------------------------------------------------
    def _parse_string(self, quote: str) -> str:
        self.pos += 1
        chars: list[str] = []
        while True:
            if self.pos >= len(self.text):
                raise GodotVariantParseError("String nao fechada")
            char = self.text[self.pos]
            if char == "\\":
                self.pos += 1
                if self.pos >= len(self.text):
                    raise GodotVariantParseError("String nao fechada")
                escape = self.text[self.pos]
                if escape == "u":
                    hex_part = self.text[self.pos + 1:self.pos + 5]
                    if len(hex_part) != 4 or not all(
                        char in "0123456789abcdefABCDEF" for char in hex_part
                    ):
                        raise GodotVariantParseError("Escape invalido")
                    chars.append(chr(int(hex_part, 16)))
                    self.pos += 4
                elif escape in _ESCAPES:
                    chars.append(_ESCAPES[escape])
                else:
                    raise GodotVariantParseError("Escape invalido")
                self.pos += 1
            elif char == quote:
                self.pos += 1
                break
            else:
                chars.append(char)
                self.pos += 1
            if len(chars) > MAX_VARIANT_STRING_LENGTH:
                raise GodotVariantLimitError("Limite de string excedido")
        return "".join(chars)

    # -- arrays ---------------------------------------------------------------
    def _parse_array(self) -> GodotVariant:
        self._enter()
        try:
            self.pos += 1
            items: list[GodotVariant] = []
            self._skip_ws()
            if self._peek() == "]":
                self.pos += 1
                return GodotVariant(kind=GodotVariantKind.ARRAY, items=())
            while True:
                if len(items) >= MAX_VARIANT_CONTAINER_ITEMS:
                    raise GodotVariantLimitError("Limite de itens excedido")
                if self._peek() in (",", "]"):
                    raise GodotVariantParseError("Item ausente")
                items.append(self._parse_value())
                self._skip_ws()
                char = self._peek()
                if char == ",":
                    self.pos += 1
                    self._skip_ws()
                    if self._peek() == "]":
                        self.pos += 1
                        break
                    continue
                if char == "]":
                    self.pos += 1
                    break
                raise GodotVariantParseError("Delimitador incompativel")
            return GodotVariant(kind=GodotVariantKind.ARRAY, items=tuple(items))
        finally:
            self._leave()

    # -- dicionarios ----------------------------------------------------------
    def _parse_dictionary(self) -> GodotVariant:
        self._enter()
        try:
            self.pos += 1
            entries: list[tuple[GodotVariant, GodotVariant]] = []
            self._skip_ws()
            if self._peek() == "}":
                self.pos += 1
                return GodotVariant(kind=GodotVariantKind.DICTIONARY, entries=())
            while True:
                if len(entries) >= MAX_VARIANT_CONTAINER_ITEMS:
                    raise GodotVariantLimitError("Limite de entradas excedido")
                if self._peek() in (",", "}"):
                    raise GodotVariantParseError("Entrada ausente")
                key = self._parse_value()
                self._skip_ws()
                if self._peek() != ":":
                    raise GodotVariantParseError("Dois-pontos ausente")
                self.pos += 1
                value = self._parse_value()
                entries.append((key, value))
                self._skip_ws()
                char = self._peek()
                if char == ",":
                    self.pos += 1
                    self._skip_ws()
                    if self._peek() == "}":
                        self.pos += 1
                        break
                    continue
                if char == "}":
                    self.pos += 1
                    break
                raise GodotVariantParseError("Delimitador incompativel")
            return GodotVariant(
                kind=GodotVariantKind.DICTIONARY,
                entries=tuple(entries),
            )
        finally:
            self._leave()

    # -- construtores ----------------------------------------------------------
    def _scan_identifier(self) -> str:
        start = self.pos
        while self.pos < len(self.text) and (
            self.text[self.pos].isalnum() or self.text[self.pos] == "_"
        ):
            self.pos += 1
        return self.text[start:self.pos]

    def _parse_constructor(self) -> GodotVariant:
        name = self._scan_identifier()
        self._skip_ws()
        typed_array = False
        if self._peek() == "[":
            if name != "Array":
                raise GodotVariantParseError("Token desconhecido")
            typed_array = True
            self._enter()
            self.pos += 1
            type_depth = 1
            type_start = self.pos
            while type_depth > 0:
                if self.pos >= len(self.text):
                    raise GodotVariantParseError("Estrutura nao fechada")
                char = self.text[self.pos]
                if char == "[":
                    type_depth += 1
                    self._enter()
                elif char == "]":
                    type_depth -= 1
                    self._leave()
                self.pos += 1
            type_content = self.text[type_start:self.pos - 1].strip()
            if not _is_valid_typed_array_type(type_content):
                raise GodotVariantParseError("Token desconhecido")
            name = f"{name}[{type_content}]"
            self._skip_ws()
        if self._peek() != "(":
            raise GodotVariantParseError("Token desconhecido")
        self._enter()
        try:
            self.pos += 1
            arguments: list[GodotVariant] = []
            self._skip_ws()
            if self._peek() == ")":
                self.pos += 1
                if typed_array:
                    return GodotVariant(
                        kind=GodotVariantKind.ARRAY,
                        items=(),
                        name=name,
                    )
                return self._make_constructor(name, ())
            while True:
                if typed_array and len(arguments) >= MAX_VARIANT_CONTAINER_ITEMS:
                    raise GodotVariantLimitError("Limite de itens excedido")
                if len(arguments) >= MAX_VARIANT_CONSTRUCTOR_ARGUMENTS:
                    raise GodotVariantLimitError("Limite de argumentos excedido")
                if self._peek() == ",":
                    raise GodotVariantParseError("Argumento ausente")
                arguments.append(self._parse_value())
                self._skip_ws()
                char = self._peek()
                if char == ",":
                    self.pos += 1
                    self._skip_ws()
                    if self._peek() == ")":
                        self.pos += 1
                        break
                    continue
                if char == ")":
                    self.pos += 1
                    break
                raise GodotVariantParseError("Delimitador incompativel")
            if typed_array:
                if len(arguments) > MAX_VARIANT_CONTAINER_ITEMS:
                    raise GodotVariantLimitError("Limite de itens excedido")
                if (
                    len(arguments) == 1
                    and arguments[0].kind is GodotVariantKind.ARRAY
                ):
                    items = arguments[0].items
                else:
                    items = tuple(arguments)
                return GodotVariant(
                    kind=GodotVariantKind.ARRAY,
                    items=items,
                    name=name,
                )
            return self._make_constructor(name, tuple(arguments))
        finally:
            self._leave()

    @staticmethod
    def _make_constructor(name: str, arguments: tuple) -> GodotVariant:
        if name == "ExtResource":
            kind = GodotVariantKind.EXT_RESOURCE_REFERENCE
        elif name == "SubResource":
            kind = GodotVariantKind.SUB_RESOURCE_REFERENCE
        elif name == "NodePath":
            kind = GodotVariantKind.NODE_PATH
        elif name.startswith("Vector"):
            kind = GodotVariantKind.VECTOR
        elif name == "Color":
            kind = GodotVariantKind.COLOR
        elif name.startswith("Packed") and name.endswith("Array"):
            kind = GodotVariantKind.PACKED_ARRAY
        else:
            kind = GodotVariantKind.CONSTRUCTOR
        return GodotVariant(kind=kind, arguments=arguments, name=name)


def parse_godot_variant(text: str) -> GodotVariant:
    """Interpreta um valor Variant Godot consumindo toda a entrada."""
    parser = _VariantParser(text)
    return parser.parse()


__all__ = [
    "GodotVariant",
    "GodotVariantKind",
    "GodotVariantParseError",
    "GodotVariantLimitError",
    "parse_godot_variant",
]
