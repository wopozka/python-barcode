from __future__ import annotations

import random
import string

import pytest

from barcode.charsets import code128
from barcode.codex import Code128
from barcode.errors import BarcodeError


def test_build_is_stable_across_repeated_calls() -> None:
    """Calling build() repeatedly on the same instance must be deterministic.

    Regression test for #143: ``_build`` mutated ``_charset`` and
    ``_digit_buffer`` without resetting them, so a second call started from
    stale state and produced a different bit string.
    """
    code = Code128("12A")
    first = code.build()
    assert code.build() == first
    assert code.build() == first


def test_encoded_is_stable_across_repeated_calls() -> None:
    """The ``encoded`` property must also be deterministic across calls."""
    code = Code128("12A")
    first = code.encoded
    assert code.encoded == first
    assert code.encoded == first


def test_reused_instance_matches_fresh_instance() -> None:
    """A reused instance must encode identically to a freshly built one."""
    reused = Code128("123ABC456")
    reused.build()  # dirties the internal charset/buffer state
    assert reused.build() == Code128("123ABC456").build()


def test_empty_code_raises_barcode_error() -> None:
    """Empty data must fail with a clear error at construction time.

    Code128("") was accepted by __init__ and then crashed with IndexError
    inside _try_to_optimize, because the encoded list holds only the start
    code. Fail fast with the library's own error type instead.
    """
    with pytest.raises(BarcodeError):
        Code128("")


def _decode(encoded: list[int]) -> str:
    """Decode a Code 128 code number list (without checksum) back to text."""
    tables = {
        "A": {v: k for k, v in code128.A.items()},
        "B": {v: k for k, v in code128.B.items()},
    }
    charset = {103: "A", 104: "B", 105: "C"}[encoded[0]]
    out = ""
    shift = False
    for value in encoded[1:]:
        if charset == "C":
            if value == code128.C["TO_A"]:
                charset = "A"
            elif value == code128.C["TO_B"]:
                charset = "B"
            elif value == code128.C[code128.FNC1]:
                out += code128.FNC1
            else:
                out += f"{value:02d}"
            continue
        if shift:
            out += tables["B" if charset == "A" else "A"][value]
            shift = False
            continue
        symbol = tables[charset][value]
        if symbol == "SHIFT":
            shift = True
        elif symbol.startswith("TO_"):
            charset = symbol[3:]
        else:
            out += symbol
    return out


@pytest.mark.parametrize(
    ("code", "length"),
    [
        ("1", 2),  # START_B 1
        ("12", 2),  # START_C 12
        ("123", 4),
        ("1234abc", 7),
        ("ab12345", 7),  # a b 1 TO_C 23 45 -- odd digit goes before charset C
        ("a\nb", 5),  # a SHIFT \n b -- no permanent switch to charset A
        ("abc1234def", 11),
        ("9912345678", 6),
    ],
)
def test_encoding_is_minimal(code: str, length: int) -> None:
    encoded = Code128(code).encoded
    assert len(encoded) == length
    assert _decode(encoded) == code


def test_encoding_roundtrips_random_data() -> None:
    rng = random.Random(1234)
    alphabet = string.digits * 4 + "ABCxyz-/\n\t" + code128.FNC1
    for _ in range(2000):
        code = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 30)))
        assert _decode(Code128(code).encoded) == code
