"""Module: barcode.codex

:Provided barcodes: Code 39, Code 128, PZN
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Literal

from barcode.base import Barcode
from barcode.charsets import code39
from barcode.charsets import code128
from barcode.errors import BarcodeError
from barcode.errors import IllegalCharacterError
from barcode.errors import NumberOfDigitsError

if TYPE_CHECKING:
    from collections.abc import Collection

    from PIL.Image import Image as T_Image

    from barcode.writer import BaseWriter

__docformat__ = "restructuredtext en"

# Sizes
MIN_SIZE = 0.2
MIN_QUIET_ZONE = 2.54


def check_code(code: str, name: str, allowed: Collection[str]) -> None:
    wrong = []
    for char in code:
        if char not in allowed:
            wrong.append(char)
    if wrong:
        raise IllegalCharacterError(
            "The following characters are not valid for {name}: {wrong}".format(
                name=name, wrong=", ".join(wrong)
            )
        )


class Code39(Barcode):
    """A Code39 barcode implementation"""

    name = "Code 39"

    def __init__(
        self,
        code: str,
        writer: BaseWriter | None = None,
        add_checksum: bool = True,
    ) -> None:
        r"""
        :param code: Code 39 string without \* and without checksum.
        :param writer: A ``barcode.writer`` instance used to render the barcode
            (default: SVGWriter).
        :param add_checksum: Add the checksum to code or not
        """

        self.code = code.upper()
        if add_checksum:
            self.code += self.calculate_checksum()
        self.writer = writer or self.default_writer()
        check_code(self.code, self.name, code39.REF)

    def __str__(self) -> str:
        return self.code

    def get_fullcode(self) -> str:
        """:returns: The full code as it will be encoded."""
        return self.code

    def calculate_checksum(self) -> str:
        check = sum(code39.MAP[x][0] for x in self.code) % 43
        for k, v in code39.MAP.items():
            if check == v[0]:
                return k
        raise RuntimeError(
            "All possible values for the checksum should have been included in the map."
        )

    def build(self) -> list[str]:
        chars = [code39.EDGE]
        for char in self.code:
            chars.append(code39.MAP[char][1])
        chars.append(code39.EDGE)
        result = code39.MIDDLE.join(chars)
        return [result]

    def render(
        self,
        writer_options: dict | None = None,
        text: str | None = None,
    ) -> bytes | T_Image:
        options = {"module_width": MIN_SIZE, "quiet_zone": MIN_QUIET_ZONE}
        options.update(writer_options or {})
        return super().render(options, text)


class PZN7(Code39):
    """Initializes new German number for pharmaceutical products.

    :param pzn: Code to render.
    :param writer: The writer to render the barcode (default: SVGWriter).
    """

    name = "Pharmazentralnummer"

    digits = 6

    def __init__(self, pzn: str, writer: BaseWriter | None = None) -> None:
        pzn = pzn[: self.digits]
        if not pzn.isdigit():
            raise IllegalCharacterError("PZN can only contain numbers.")
        if len(pzn) != self.digits:
            raise NumberOfDigitsError(
                f"PZN must have {self.digits} digits, not {len(pzn)}."
            )
        self.pzn = pzn
        self.pzn = f"{pzn}{self.calculate_checksum()}"
        super().__init__(f"PZN-{self.pzn}", writer, add_checksum=False)

    def get_fullcode(self) -> str:
        return f"PZN-{self.pzn}"

    def calculate_checksum(self) -> int:
        sum_ = sum(int(x) * int(y) for x, y in enumerate(self.pzn, start=2))
        checksum = sum_ % 11
        if checksum == 10:
            raise BarcodeError("Checksum can not be 10 for PZN.")

        return checksum


class PZN8(PZN7):
    """Will be fully added in v0.9."""

    digits = 7


_Charset = Literal["A", "B", "C"]
# Order matters: it is the tie-break preference when choosing a charset.
_CHARSETS: tuple[_Charset, ...] = ("C", "B", "A")
_TABLES: dict[_Charset, dict[str, int]] = {
    "A": code128.A,
    "B": code128.B,
    "C": code128.C,
}
_DIGITS = frozenset("0123456789")
_INF = float("inf")


class Code128(Barcode):
    """Initializes a new Code128 instance. The checksum is added automatically
    when building the bars.

    :param code: Code 128 string without checksum (added automatically).
    :param writer: The writer to render the barcode (default: SVGWriter).
    """

    name = "Code 128"
    code: str
    writer: BaseWriter

    def __init__(self, code: str, writer: BaseWriter | None = None) -> None:
        if not code:
            raise BarcodeError("Code 128 requires at least one character")
        self.code = code
        self.writer = writer or self.default_writer()
        check_code(self.code, self.name, code128.ALL)

    def __str__(self) -> str:
        return self.code

    @property
    def encoded(self) -> list[int]:
        return self._build()

    def get_fullcode(self) -> str:
        return self.code

    @staticmethod
    def _steps(code: str, pos: int, charset: _Charset) -> list[tuple[list[int], int]]:
        """Ways to encode the data at ``pos`` without leaving ``charset``.

        Returns ``(code_numbers, next_pos)`` pairs, most preferred first.
        """
        char = code[pos]
        if charset == "C":
            if char == code128.FNC1:
                return [([code128.C[char]], pos + 1)]
            pair = code[pos : pos + 2]
            if len(pair) == 2 and pair[0] in _DIGITS and pair[1] in _DIGITS:
                return [([int(pair)], pos + 2)]
            return []
        own = _TABLES[charset]
        other = _TABLES["B" if charset == "A" else "A"]
        if char in own:
            return [([own[char]], pos + 1)]
        if char in other:
            # A single character from the other charset: SHIFT + char.
            return [([own["SHIFT"], other[char]], pos + 1)]
        return []

    def _build(self) -> list[int]:
        """Encode the data into the shortest possible list of code numbers.

        Dynamic programming over (position, active charset): ``cost[i][s]`` is the
        minimal number of symbols needed to encode ``code[i:]`` when charset ``s``
        is active at position ``i``. The symbol list is then reconstructed from the
        start. On ties, staying in the current charset is preferred over switching,
        and charset C over B over A.
        """
        code = self.code
        n = len(code)
        cost = [dict.fromkeys(_CHARSETS, 0.0) for _ in range(n + 1)]
        stay = [dict.fromkeys(_CHARSETS, _INF) for _ in range(n + 1)]
        for i in range(n - 1, -1, -1):
            for s in _CHARSETS:
                stay[i][s] = min(
                    (len(syms) + cost[j][s] for syms, j in self._steps(code, i, s)),
                    default=_INF,
                )
            for s in _CHARSETS:
                # Switching twice in a row is never useful, so one switch suffices.
                switch = 1 + min(stay[i][t] for t in _CHARSETS if t != s)
                cost[i][s] = min(stay[i][s], switch)

        charset = min(_CHARSETS, key=lambda s: cost[0][s])
        encoded = [code128.START_CODES[charset]]
        i = 0
        while i < n:
            for syms, j in self._steps(code, i, charset):
                if len(syms) + cost[j][charset] == cost[i][charset]:
                    encoded.extend(syms)
                    i = j
                    break
            else:
                target = next(
                    t
                    for t in _CHARSETS
                    if t != charset and 1 + stay[i][t] == cost[i][charset]
                )
                encoded.append(_TABLES[charset]["TO_" + target])
                charset = target
        return encoded

    def _calculate_checksum(self, encoded: list[int]) -> int:
        cs = [encoded[0]]
        for i, code_num in enumerate(encoded[1:], start=1):
            cs.append(i * code_num)
        return sum(cs) % 103

    def build(self) -> list[str]:
        encoded = self._build()
        encoded.append(self._calculate_checksum(encoded))
        code = ""
        for code_num in encoded:
            code += code128.CODES[code_num]
        code += code128.STOP
        code += "11"
        return [code]

    def render(
        self,
        writer_options: dict | None = None,
        text: str | None = None,
    ) -> bytes | T_Image:
        options = {"module_width": MIN_SIZE, "quiet_zone": MIN_QUIET_ZONE}
        options.update(writer_options or {})
        return super().render(options, text)


class Gs1_128(Code128):  # noqa: N801
    """
    following the norm, a gs1-128 barcode is a subset of code 128 barcode,
    it can be generated by prepending the code with the FNC1 character
    https://en.wikipedia.org/wiki/GS1-128
    https://www.gs1-128.info/
    """

    name = "GS1-128"

    FNC1_CHAR = code128.FNC1

    def __init__(self, code: str, writer: BaseWriter | None = None) -> None:
        code = self.FNC1_CHAR + code
        super().__init__(code, writer)

    def get_fullcode(self) -> str:
        return super().get_fullcode()[1:]


# For pre 0.8 compatibility
PZN = PZN7
