"""Differential coverage for the columnar text layout (``_columnar``).

The columnar path must give exactly what the object pipeline gives: the
same text under every option, and the same ``charactersByArticle``
positions (built lazily). Random content streams exercise kerning, fake
bold re-paints, rises, scaling, sheared matrices, cropbox offsets, page
rotation, beads and several fonts; each page is extracted with the
columnar layout on and off.
"""

import dataclasses
import io
import random

import pytest

import pypdfbox.text.pdf_text_stripper as stripper_module
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.interactive.pagenavigation import PDThreadBead
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper import PDFTextStripper

_FONTS = ("Helvetica", "Times-Roman", "Courier", "Helvetica-Bold")
_ALPHABET = (
    b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    b"     .,;:-()[]^`'\"~_\xe9\x93\x94\x96\x97\xb0\xe4\xfc"
)


# Without the diacritics (which send a page to the object merge).
_PLAIN_ALPHABET = bytes(b for b in _ALPHABET if b not in b"^`")


def _string(rng: random.Random, alphabet: bytes) -> bytes:
    return bytes(rng.choice(alphabet) for _ in range(rng.randint(0, 9)))


def _literal(data: bytes) -> str:
    out = []
    for b in data:
        if b in b"()\\":
            out.append("\\" + chr(b))
        elif 32 <= b < 127:
            out.append(chr(b))
        else:
            out.append(f"\\{b:03o}")
    return "(" + "".join(out) + ")"


def _page_ops(rng: random.Random, alphabet: bytes) -> str:
    ops: list[str] = []
    y = rng.uniform(500, 760)
    x = rng.uniform(20, 80)
    last_show = None
    for _ in range(rng.randint(1, 4)):
        q = rng.random() < 0.15
        if q:
            ops.append("q")
            ops.append(rng.choice(["1 0 0 1 10 -20 cm", "0.5 0 0 0.5 0 0 cm", "1 0.2 0 1 0 0 cm"]))
        ops.append("BT")
        ops.append(f"/F{rng.randint(1, len(_FONTS))} {rng.choice([7, 9, 10, 12, 18])} Tf")
        if rng.random() < 0.2:
            a = rng.choice([1, 1.5, 0.75, 10])
            b = rng.choice([0, 0, 0, 0.3])
            ops.append(f"{a} {b} 0 {a} {x:.3f} {y:.3f} Tm")
        else:
            ops.append(f"{x:.3f} {y:.3f} Td")
        for _ in range(rng.randint(1, 25)):
            r = rng.random()
            if r < 0.08:
                ops.append(f"{rng.choice([0, 0.5, -0.3, 1.2])} Tc")
            elif r < 0.14:
                ops.append(f"{rng.choice([0, 2, -1, 4.5])} Tw")
            elif r < 0.17:
                ops.append(f"{rng.choice([100, 80, 120])} Tz")
            elif r < 0.19:
                ops.append(f"{rng.choice([0, 0, 3, -2])} Ts")
            elif r < 0.26:
                ops.append(f"/F{rng.randint(1, len(_FONTS))} {rng.choice([6, 9, 10, 12, 0.5])} Tf")
            elif r < 0.40:
                ops.append(
                    f"{rng.choice([0, 3, -5, 40, 0.2])} "
                    f"{rng.choice([-12, -14, 0, 0, -0.5, 2, -40])} Td"
                )
            elif r < 0.46 and last_show is not None:
                # Fake bold: the last show again, nudged.
                ops.append(f"{rng.choice([0.0, 0.2, 0.4, 1.5])} 0 Td")
                ops.append(last_show)
            elif r < 0.70:
                last_show = f"{_literal(_string(rng, alphabet))} Tj"
                ops.append(last_show)
            else:
                parts = []
                for _ in range(rng.randint(1, 6)):
                    parts.append(_literal(_string(rng, alphabet)))
                    if rng.random() < 0.7:
                        parts.append(str(rng.choice([-250, 120, -30, 0, 500, -1000, 15.5])))
                last_show = "[" + " ".join(parts) + "] TJ"
                ops.append(last_show)
            if rng.random() < 0.05:
                ops.append("T*")
        ops.append("ET")
        if q:
            ops.append("Q")
        y -= rng.uniform(0, 120)
    return "\n".join(ops) + "\n"


def _document(seed: int, pages: int = 4) -> bytes:
    rng = random.Random(seed)
    doc = PDDocument()
    fonts = [PDFontFactory.create_default_font(name) for name in _FONTS]
    for _ in range(pages):
        if rng.random() < 0.2:
            box = PDRectangle(rng.choice([0, 15.5, -20]), rng.choice([0, 30, -7.25]), 612, 792)
        else:
            box = PDRectangle(0.0, 0.0, 612.0, 792.0)
        page = PDPage(box)
        if rng.random() < 0.1:
            page.set_rotation(rng.choice([90, 180]))
        doc.add_page(page)
        cs = PDPageContentStream(doc, page)
        # Register the fonts as /F1../F4 (the Tf operators are discarded
        # by the raw stream below being self-contained).
        cs.begin_text()
        for font in fonts:
            cs.set_font(font, 10.0)
        cs.end_text()
        cs.append_raw_commands(_page_ops(rng, _ALPHABET if seed % 2 else _PLAIN_ALPHABET))
        cs.close()
        if rng.random() < 0.1:
            bead = PDThreadBead()
            bead.set_rectangle(PDRectangle(50, 300, 300, 700))
            page.set_thread_beads([bead])
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


class _Collector(PDFTextStripper):
    """Records each page's ``charactersByArticle`` (``end_page`` is not one
    of the hooks the columnar layout replaces)."""

    def __init__(self) -> None:
        super().__init__()
        self.pages: list = []

    def end_page(self, page) -> None:
        self.pages.append([[_snapshot(p) for p in a] for a in self.get_characters_by_article()])


def _snapshot(position) -> tuple:
    """A position's fields (its font by name: each run loads the document
    anew), run id and geometry tuple."""
    values = []
    for field in dataclasses.fields(position):
        value = getattr(position, field.name)
        if field.name == "font":
            value = None if value is None else value.get_name()
        values.append(value)
    return (
        type(position),
        tuple(values),
        getattr(position, "_run_id", None),
        getattr(position, "_java_geometry", None),
    )


_OPTIONS = {
    "default": {},
    "nodup": {"set_suppress_duplicate_overlapping_text": False},
    "nobeads": {"set_should_separate_by_beads": False},
    "more": {"set_add_more_formatting": True},
    "ignore_spaces": {"set_ignore_content_stream_space_glyphs": True},
    "range": {"set_start_page": 2, "set_end_page": 3},
}


def _extract(data: bytes, options: dict, columnar: bool, monkeypatch) -> tuple:
    monkeypatch.setattr(stripper_module, "_USE_COLUMNAR", columnar)
    with PDDocument.load(data) as doc:
        stripper = _Collector()
        for name, value in options.items():
            getattr(stripper, name)(value)
        text = stripper.get_text(doc)
    return text, stripper.pages


@pytest.mark.parametrize("seed", range(40))
def test_columnar_matches_object_pipeline(seed, monkeypatch):
    data = _document(seed)
    for options in _OPTIONS.values():
        before = dict(stripper_module._COLUMNAR_STATS)
        on = _extract(data, options, True, monkeypatch)
        off = _extract(data, options, False, monkeypatch)
        assert on[0] == off[0]
        assert on[1] == off[1]
        assert stripper_module._COLUMNAR_STATS["columnar"] >= before["columnar"]


def test_columnar_path_is_taken(monkeypatch):
    monkeypatch.setattr(stripper_module, "_USE_COLUMNAR", True)
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    doc.add_page(page)
    cs = PDPageContentStream(doc, page)
    cs.begin_text()
    cs.set_font(PDFontFactory.create_default_font("Helvetica"), 12.0)
    cs.new_line_at_offset(72, 700)
    cs.show_text("Hello columnar world")
    cs.new_line_at_offset(0, -14)
    cs.show_text("second line")
    cs.end_text()
    cs.close()
    before = stripper_module._COLUMNAR_STATS["columnar"]
    stripper = PDFTextStripper()
    assert stripper.get_text(doc) == "Hello columnar world\nsecond line\n"
    assert stripper_module._COLUMNAR_STATS["columnar"] == before + 1
    # The positions are built on demand and match the text.
    (article,) = stripper.get_characters_by_article()
    assert "".join(p.get_unicode() for p in article) == "Hello columnar worldsecond line"
    doc.close()


def test_overridden_hook_uses_object_pipeline(monkeypatch):
    monkeypatch.setattr(stripper_module, "_USE_COLUMNAR", True)

    class Upper(PDFTextStripper):
        def write_string(self, text, text_positions, sink):
            sink(text.upper())

    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    doc.add_page(page)
    cs = PDPageContentStream(doc, page)
    cs.begin_text()
    cs.set_font(PDFontFactory.create_default_font("Helvetica"), 12.0)
    cs.new_line_at_offset(72, 700)
    cs.show_text("shout")
    cs.end_text()
    cs.close()
    before = dict(stripper_module._COLUMNAR_STATS)
    assert Upper().get_text(doc) == "SHOUT\n"
    assert stripper_module._COLUMNAR_STATS["columnar"] == before["columnar"]
    doc.close()
