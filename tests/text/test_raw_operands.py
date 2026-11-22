"""The raw-operand walk of :class:`PDFTextStripper` (``_walk_raw`` over
``PDFStreamParser._raw_operations``) against the COS token loop.

``_raw_operations`` hands out Python numbers and bytes in place of
``COSNumber`` / ``COSString`` / ``COSArray`` objects. These tests pin that
the operators, the values the stripper reads from the operands and the log
records match the token parse on edge tokens, that extraction gives the same
text and positions either way, and that a subclass or instance replacing a
hook the walk stands in for keeps the token loop.
"""

import dataclasses
import logging
import math
import random

import pytest

from pypdfbox.cos import (
    COSArray,
    COSName,
    COSNumber,
    COSStream,
    COSString,
)
from pypdfbox.cos import (
    COSArray as _COSArray,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.text import PDFTextStripper

# Tokens whose reference parse has a quirk, or that sit at an edge of the
# fast token shapes.
_EDGE_TOKENS = [
    b"0",
    b"-0",
    b"0.0",
    b"-0.0",
    b".5",
    b"-.5",
    b"5.",
    b"-5.",
    b"--5",
    b"+5",
    b"1.2.3",
    b"-",
    b".",
    b"007",
    b"1e5",
    b"16777217",
    b"-16777217",
    b"123456789012345678",
    b"1234567890123456789",
    b"-99999999999999999999999",
    b"0.000000000000000000000000000000000000000001",
    b"1" * 45 + b".5",
    b"9" * 70,
    b"9" * 70 + b".0",
    b"3.4028236e38",
    b"340282356779733661637539395458142568448.0",
    b"()",
    b"(a)",
    b"(a\\)b)",
    b"(x(y)z)",
    b"(\\101\\n\\\r\n\\q)",
    b"(\\",
    b"<>",
    b"<414>",
    b"<4 1 4 2>",
    b"<zz>",
    b"/N",
    b"/",
    b"/A#20B",
    b"true",
    b"false",
    b"null",
    b"]",
    b">",
    b"{",
    b"%c\n",
    b"\x00",
    b"[]",
    b"[1 (a) <41> -2.5]",
    b"[(a\\)b) 3]",
    b"[/N 1]",
    b"[[1] 2]",
    b"[" + b"7" * 70 + b"]",
    b"[1 %c\n 2]",
    b"[\x001]",
    b"[1.5.5]",
    b"<</MCID 3>>",
    b"<</ActualText (x)>>",
    b"<</A [1]>>",
    b"<<>>",
    b"<</A 1 0 R>>",
    b"<< /MCID -0 >>",
    b"<</MCID 123456789012345678>>",
    b"<</MCID 12345678901234567>>",
    b"<</MCID 1 2>>",
    b"<</MC#49D 1>>",
    b"<</MCID 1.5>>",
    b"<</MCID\x001>>",
    b"<</ 1>>",
]
_OPERATORS = [
    b"Tj",
    b"TJ",
    b"'",
    b'"',
    b"Td",
    b"TD",
    b"Tm",
    b"cm",
    b"Tf",
    b"Tc",
    b"Tw",
    b"Tz",
    b"Ts",
    b"TL",
    b"T*",
    b"BT",
    b"ET",
    b"q",
    b"Q",
    b"BDC",
    b"BMC",
    b"EMC",
    b"Do",
    b"re",
    b"f",
    b"d0",
    b"BX",
    b"EX",
    b"ID",
    b"BI",
    b"EI",
    b"Tfx",
]


def _normalize(value: object) -> object:
    """What the stripper can read from an operand: a number by its
    ``float_value`` bits, a string by its bytes, an array by its elements;
    anything else by its type and repr."""
    if type(value) is int:
        return ("n", float(value).hex())
    if type(value) is float:
        return ("n", value.hex())
    if type(value) is bytes:
        return ("s", value)
    if type(value) is list:
        return ("a", tuple(_normalize(item) for item in value))
    if isinstance(value, COSNumber):
        return ("n", value.float_value().hex())
    if isinstance(value, COSString):
        return ("s", value.get_bytes())
    if isinstance(value, _COSArray):
        return ("a", tuple(_normalize(item) for item in value))
    return (type(value).__name__, repr(value))


def _token_operations(data: bytes) -> list[tuple[str, tuple]]:
    operations: list = []
    operands: list = []
    with RandomAccessReadBuffer(data) as src:
        try:
            for token in PDFStreamParser(src).tokens():
                if isinstance(token, Operator):
                    operations.append((token.get_name(), tuple(map(_normalize, operands))))
                    operands = []
                else:
                    operands.append(token)
        except Exception as exc:  # the same error must surface
            operations.append(("raised", type(exc).__name__, str(exc)))
    return operations


def _raw_operations(data: bytes, wanted=None) -> list[tuple[str, tuple]]:
    operations: list = []
    with RandomAccessReadBuffer(data) as src:
        try:
            for name, operands in PDFStreamParser(src)._raw_operations(wanted):
                operations.append((name, tuple(map(_normalize, operands))))
        except Exception as exc:
            operations.append(("raised", type(exc).__name__, str(exc)))
    return operations


def _logs(caplog) -> list[tuple]:
    # (Leaving out the unclosed-document warnings of other tests' garbage.)
    records = [
        (r.name, r.levelno, r.getMessage())
        for r in caplog.records
        if r.name != "pypdfbox.cos.cos_document"
    ]
    caplog.clear()
    return records


def _random_stream(rng: random.Random) -> bytes:
    pieces = []
    for _ in range(rng.randint(1, 40)):
        if rng.random() < 0.55:
            pieces.append(rng.choice(_EDGE_TOKENS))
        else:
            pieces.append(rng.choice(_OPERATORS))
        pieces.append(rng.choice([b" ", b"\n", b"", b"\r\n", b"\x00", b"  ", b"%k\n"]))
    return b"".join(pieces)


@pytest.mark.parametrize("token", _EDGE_TOKENS, ids=range(len(_EDGE_TOKENS)))
def test_edge_token_operands_match_token_parse(token, caplog):
    caplog.set_level(logging.DEBUG, logger="pypdfbox")
    for data in (
        token + b" Tj",
        b"1 " + token + b" 2 Td",
        b"[" + token + b" (x)] TJ",
        b"/T " + token + b" BDC",
        token + b"Tc",
        b"BT " + token + b" " + token + b" Tw ET",
    ):
        expected = _token_operations(data)
        expected_logs = _logs(caplog)
        assert _raw_operations(data) == expected, data
        assert _logs(caplog) == expected_logs, data


@pytest.mark.parametrize("seed", range(300))
def test_random_streams_match_token_parse(seed, caplog):
    caplog.set_level(logging.DEBUG, logger="pypdfbox")
    data = _random_stream(random.Random(seed))
    expected = _token_operations(data)
    expected_logs = _logs(caplog)
    assert _raw_operations(data) == expected
    assert _logs(caplog) == expected_logs
    wanted = frozenset({"Tj", "TJ", "Td", "BDC"})
    assert _raw_operations(data, wanted) == [
        op for op in expected if op[0] in wanted or op[0] == "raised"
    ]
    assert _logs(caplog) == expected_logs


def test_inline_image_is_skipped_like_the_token_parse():
    data = b"BT 1 2 Td (a) Tj ET\nBI /W 2 /H 1 /BPC 8 /CS /G ID \x00\xff(]Tj EI\n3 4 Td [(b) -5] TJ"
    assert _raw_operations(data) == _token_operations(data)


def test_raw_values():
    data = b"12 -0 0.0 -.5 1234567890123456789 (a\\051) <414> [1 (b) 2.5] /N true X"
    with RandomAccessReadBuffer(data) as src:
        ((name, operands),) = list(PDFStreamParser(src)._raw_operations())
    assert name == "X"
    assert operands[:4] == [12, 0, 0.0, -0.5]
    assert type(operands[0]) is int and type(operands[3]) is float
    assert math.copysign(1.0, operands[2]) == 1.0
    assert isinstance(operands[4], COSNumber)
    assert operands[5:8] == [b"a)", b"A@", [1, b"b", 2.5]]
    assert operands[8] is COSName.get_pdf_name("N")


# ---------------------------------------------------------------------------
# extraction: raw walk against the token loop
# ---------------------------------------------------------------------------


def _form(body: bytes, resources: PDResources) -> PDFormXObject:
    stream = COSStream()
    stream.set_data(body)
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form"))
    stream.set_item(COSName.get_pdf_name("BBox"), COSArray([]))
    form = PDFormXObject(stream)
    form.set_resources(resources)
    return form


def _show_stream(rng: random.Random, font_keys: list[bytes], form_key: bytes) -> bytes:
    ops = [b"BT", b"/" + rng.choice(font_keys) + b" 10 Tf", b"72 700 Td"]
    for _ in range(rng.randint(5, 40)):
        r = rng.random()
        if r < 0.3:
            ops.append(
                rng.choice([b"(Hello) Tj", b"(a\\)b) Tj", b"<48656c6c6f> Tj", b"(x\xe9) Tj"])
            )
        elif r < 0.5:
            ops.append(
                b"["
                + rng.choice(
                    [
                        b"(Wor) -250 (ld)",
                        b"(a) 16777217 (b)",
                        b"(c\\(d) 3.5",
                        b"(e) " + b"1" * 30 + b" (f)",
                        b"(g) /N (h)",
                        b"<41> -0.0 ()",
                    ]
                )
                + b"] TJ"
            )
        elif r < 0.6:
            ops.append(
                rng.choice(
                    [
                        b"0 -12 Td",
                        b"1.5 -0 TD",
                        b"--3 4 Td",
                        b"T*",
                        b"(q) '",
                        b'1 2 (r) "',
                        b"12 TL",
                        b"5 Td",
                    ]
                )
            )
        elif r < 0.7:
            ops.append(
                rng.choice(
                    [
                        b"0 Tc",
                        b"0.25 Tc",
                        b"-0 Tw",
                        b"3 Tw",
                        b"80 Tz",
                        b"2 Ts",
                        b"0 Ts",
                        b"Tc",
                        b"(x) Tw",
                    ]
                )
            )
        elif r < 0.8:
            ops.append(
                rng.choice(
                    [
                        b"1 0 0 1 72 600 Tm",
                        b"10 0 0 10 50 500 Tm",
                        b"1 0 0 Tm",
                        b"/"
                        + rng.choice(font_keys)
                        + b" 0.000000000000000000000000000000000000000001 Tf",
                        b"/" + rng.choice(font_keys) + b" 9 Tf",
                        b"/Missing 8 Tf",
                    ]
                )
            )
        elif r < 0.9:
            ops.append(
                rng.choice(
                    [
                        b"/Span <</ActualText (ACT)>> BDC (zz) Tj EMC",
                        b"/P <</MCID 3>> BDC",
                        b"EMC",
                        b"/Span BMC",
                        b"1 /X BMC",
                        b"/Span /Prop BDC",
                    ]
                )
            )
        else:
            ops.append(
                rng.choice(
                    [
                        b"ET q 1 0 0 1 5 5 cm /" + form_key + b" Do Q BT",
                        b"ET BI /W 1 /H 1 /BPC 8 /CS /G ID \x80 EI BT",
                        b"% comment\n",
                        b"ET (stranded) Tj BT",
                        b"1 2 re f",
                    ]
                )
            )
    ops.append(b"ET")
    return b"\n".join(ops)


def _document(seed: int) -> PDDocument:
    rng = random.Random(seed)
    doc = PDDocument()
    resources = PDResources()
    font_keys = [
        resources.add(PDFontFactory.create_default_font(name)).get_name().encode("ascii")
        for name in ("Helvetica", "Times-Roman", "Courier")
    ]
    form = _form(_show_stream(rng, font_keys, b"Nope"), resources)
    form_key = resources.add_x_object(form).get_name().encode("ascii")
    for _ in range(3):
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        page.set_resources(resources)
        content = COSStream()
        content.set_data(_show_stream(rng, font_keys, form_key))
        page.set_contents(content)
        doc.add_page(page)
    return doc


class _Collector(PDFTextStripper):
    def __init__(self) -> None:
        super().__init__()
        self.pages: list = []

    def end_page(self, page) -> None:
        self.pages.append(
            [
                [tuple(repr(getattr(p, f.name)) for f in dataclasses.fields(p)) for p in article]
                for article in self.get_characters_by_article()
            ]
        )


def _extract(seed: int, caplog, options: dict) -> tuple:
    caplog.clear()
    doc = _document(seed)
    try:
        stripper = _Collector()
        for name, value in options.items():
            getattr(stripper, name)(value)
        text = stripper.get_text(doc)
    finally:
        doc.close()
    return text, stripper.pages, _logs(caplog)


@pytest.mark.parametrize("seed", range(30))
@pytest.mark.parametrize(
    "options",
    [{}, {"set_sort_by_position": True}, {"set_suppress_duplicate_overlapping_text": False}],
    ids=["default", "sort", "nodedup"],
)
def test_raw_walk_matches_token_loop(seed, options, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG, logger="pypdfbox")
    walks = []
    original = PDFStreamParser._raw_operations

    def counting(self, *args):
        walks.append(1)
        return original(self, *args)

    monkeypatch.setattr(PDFStreamParser, "_raw_operations", counting)
    raw = _extract(seed, caplog, options)
    assert walks, "the raw walk was not taken"
    monkeypatch.setattr(PDFTextStripper, "_raw_operands_ok", lambda self: False)
    walks.clear()
    classic = _extract(seed, caplog, options)
    assert not walks
    assert raw == classic


# ---------------------------------------------------------------------------
# the guard
# ---------------------------------------------------------------------------


def _simple_doc() -> PDDocument:
    doc = PDDocument()
    resources = PDResources()
    key = resources.add(PDFontFactory.create_default_font("Helvetica")).get_name()
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    page.set_resources(resources)
    content = COSStream()
    content.set_data(b"BT /" + key.encode("ascii") + b" 12 Tf 72 700 Td [(Hel) -20 (lo)] TJ ET")
    page.set_contents(content)
    doc.add_page(page)
    return doc


def _fail_walk(self, *args):
    raise AssertionError("raw walk taken")


@pytest.mark.parametrize(
    "hook", ["_dispatch", "_show_fast", "_show_form_xobject", "_emit_plain", "_emit"]
)
def test_overridden_hook_keeps_token_loop(hook, monkeypatch):
    calls = []
    stock = getattr(PDFTextStripper, hook)

    def override(self, *args, **kwargs):
        calls.append(hook)
        return stock(self, *args, **kwargs)

    subclass = type("Sub", (PDFTextStripper,), {hook: override})
    monkeypatch.setattr(PDFStreamParser, "_raw_operations", _fail_walk)
    doc = _simple_doc()
    try:
        with pytest.raises(AssertionError, match="raw walk taken"):
            PDFTextStripper().get_text(doc)
        assert subclass().get_text(doc) == "Hello\n"
    finally:
        doc.close()
    assert calls or hook == "_show_form_xobject"


def test_instance_override_keeps_token_loop(monkeypatch):
    seen = []
    stripper = PDFTextStripper()
    stock = stripper._dispatch

    def dispatch(op, operands, state, positions):
        seen.append((op, [type(v) for v in operands]))
        return stock(op, operands, state, positions)

    stripper._dispatch = dispatch
    doc = _simple_doc()
    try:
        assert stripper.get_text(doc) == "Hello\n"
    finally:
        doc.close()
    # The token loop hands COS operands to the hook.
    assert ("TJ", [_COSArray]) in seen
