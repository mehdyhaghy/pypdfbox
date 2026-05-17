"""Wave 1347 coverage-boost tests for six pdmodel examples.

Targets the residual uncovered branches in:

* ``create_patterns_pdf`` — ctor, COSStream guard, usage-error.
* ``embedded_fonts`` — ctor, TTF-load path, glyph-fallback path.
* ``print_bookmarks`` — item-level unknown-destination branch and the
  action-level PDNamedDestination branch (both dead via normal API,
  driven here through a monkey-patched action).
* ``print_document_meta_data`` — embedded ``/Metadata`` stream branch
  and the ``format_date`` non-None branch.
* ``add_message_to_each_page`` — rotated-page text-matrix branch.
* ``create_bookmarks`` — encrypted-doc short-circuit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.examples.pdmodel.add_message_to_each_page import AddMessageToEachPage
from pypdfbox.examples.pdmodel.create_bookmarks import CreateBookmarks
from pypdfbox.examples.pdmodel.create_patterns_pdf import (
    CreatePatternsPDF,
    _set_tile_contents,
)
from pypdfbox.examples.pdmodel.embedded_fonts import EmbeddedFonts
from pypdfbox.examples.pdmodel.print_bookmarks import PrintBookmarks
from pypdfbox.examples.pdmodel.print_document_meta_data import PrintDocumentMetaData
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern import PDTilingPattern
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_document_outline import (
    PDDocumentOutline,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
    PDOutlineItem,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# ---------------------------------------------------------------------------
# create_patterns_pdf
# ---------------------------------------------------------------------------


def test_create_patterns_pdf_constructor_is_a_no_op() -> None:
    """Exercises the ``__init__`` body (line 47)."""
    assert isinstance(CreatePatternsPDF(), CreatePatternsPDF)


def test_create_patterns_pdf_main_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Two-arg ``main`` is the usage-error path (lines 65-68)."""
    with pytest.raises(SystemExit) as excinfo:
        CreatePatternsPDF.main(["a", "b"])
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Usage" in err and "CreatePatternsPDF" in err


def test_set_tile_contents_rejects_non_stream_pattern() -> None:
    """A tiling pattern whose backing COS object is not a COSStream raises
    TypeError (lines 35-39 — line 36 is the raise)."""

    class FakePattern:
        def get_cos_object(self) -> Any:
            return object()  # neither COSStream nor None

    with pytest.raises(TypeError, match="COSStream"):
        _set_tile_contents(FakePattern(), "x")


def test_set_tile_contents_writes_to_real_stream() -> None:
    """Happy path — covered indirectly by the wave1286_3 round-trip, but
    pin it here so the helper's contract stays unambiguous."""
    pattern = PDTilingPattern()
    _set_tile_contents(pattern, "M\n")
    raw = pattern.get_cos_object().to_byte_array()
    assert b"M" in raw


# ---------------------------------------------------------------------------
# embedded_fonts
# ---------------------------------------------------------------------------


def test_embedded_fonts_constructor_is_a_no_op() -> None:
    """Exercises the ``__init__`` body (line 47)."""
    assert isinstance(EmbeddedFonts(), EmbeddedFonts)


def test_embedded_fonts_demo_with_font_uses_ttf_path(tmp_path: Path) -> None:
    """When a TTF path is provided ``demo_with_font`` switches to the
    upstream-faithful ``PDType0Font.load`` branch (line 81)."""
    ttf = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "ttf" / (
        "LiberationSans-Regular.ttf"
    )
    assert ttf.exists(), "wave1347 fixture missing"
    out = tmp_path / "ttf-embedded.pdf"
    EmbeddedFonts.demo_with_font(out, ttf)
    assert out.exists() and out.read_bytes()[:4] == b"%PDF"


def test_embedded_fonts_main_with_ttf_arg(tmp_path: Path) -> None:
    """Second positional arg to ``main`` triggers the same TTF branch."""
    ttf = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "ttf" / (
        "LiberationSans-Regular.ttf"
    )
    out = tmp_path / "main-ttf.pdf"
    EmbeddedFonts.main([str(out), str(ttf)])
    assert out.exists() and out.read_bytes()[:4] == b"%PDF"


def test_embedded_fonts_glyph_fallback_renders_placeholder(
    tmp_path: Path,
) -> None:
    """When ``show_text`` raises for a particular glyph the demo writes
    a placeholder line so the cursor still advances (lines 102-108)."""
    import pypdfbox.examples.pdmodel.embedded_fonts as ef

    # Wrap ``show_text`` so the second invocation raises one of the
    # expected exceptions; the rest succeed.
    real_pcs = ef.PDPageContentStream
    calls: dict[str, int] = {"n": 0}

    class FlakyStream(real_pcs):  # type: ignore[misc, valid-type]
        def show_text(self, text: str) -> None:  # noqa: D401
            calls["n"] += 1
            if calls["n"] == 2:
                raise ValueError("simulated unmappable glyph")
            super().show_text(text)

    out = tmp_path / "flaky.pdf"
    with patch.object(ef, "PDPageContentStream", FlakyStream):
        EmbeddedFonts.demo_with_font(out, None)
    assert out.exists() and out.read_bytes()[:4] == b"%PDF"
    # First call raised, then ``[skipped: unsupported glyph]`` was
    # written via a follow-up ``show_text`` call — confirm we made
    # additional calls past the failed one.
    assert calls["n"] >= 3


# ---------------------------------------------------------------------------
# print_bookmarks
# ---------------------------------------------------------------------------


def test_print_bookmark_item_level_unknown_dest_branch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Lines 68-71: outline item whose ``get_destination`` returns
    something that's neither PDPageDestination nor PDNamedDestination
    (here: a plain ``str`` named destination via COSString /Dest)."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))
        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        item = PDOutlineItem()
        item.set_title("StringDest")
        # Setting a raw COSString /Dest makes ``get_destination`` return
        # PDNamedDestination — to land in the dest-class fallback we need
        # a destination type get_destination() can build but isn't a
        # PageDestination/NamedDestination. We monkey-patch the item.
        item.get_cos_object()  # touch
        outline.add_last(item)

        # Monkey-patch the item so get_destination returns a sentinel
        # that isn't a PDPageDestination or PDNamedDestination instance.
        class StubDest:
            pass

        sentinel = StubDest()
        with patch.object(PDOutlineItem, "get_destination", return_value=sentinel):
            PrintBookmarks().print_bookmark(doc, outline, "")
    finally:
        doc.close()
    out = capsys.readouterr().out
    assert "Destination class: StubDest\n" in out
    assert "StringDest\n" in out


def test_print_bookmark_action_level_named_destination_branch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Lines 81-87: PDActionGoTo whose ``get_destination`` returns a real
    PDNamedDestination and the catalog resolves the name to a page.

    Driven via monkey-patching because the production code path in our
    port returns ``str`` for /D-as-name (not a PDNamedDestination)."""
    from pypdfbox.cos import COSArray, COSDictionary, COSString

    doc = PDDocument()
    try:
        for _ in range(3):
            doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))

        # /Names /Dests so find_named_destination_page resolves.
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (  # noqa: E501
            PDPageFitDestination,
        )

        named_page = PDPageFitDestination()
        named_page.set_page_number(1)  # 0-indexed → page 2 (1-based)
        names_array = COSArray()
        names_array.add(COSString("named-action"))
        names_array.add(named_page.get_cos_object())
        dests = COSDictionary()
        dests.set_item(COSName.get_pdf_name("Names"), names_array)
        names = COSDictionary()
        names.set_item(COSName.get_pdf_name("Dests"), dests)
        doc.get_document_catalog().get_cos_object().set_item(
            COSName.get_pdf_name("Names"), names
        )

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        item = PDOutlineItem()
        item.set_title("Named via Action")
        item.set_action(PDActionGoTo())
        outline.add_last(item)

        nd = PDNamedDestination("named-action")
        with patch.object(PDActionGoTo, "get_destination", return_value=nd):
            PrintBookmarks().print_bookmark(doc, outline, "")
    finally:
        doc.close()
    out = capsys.readouterr().out
    # 1-based: page index 1 → "Destination page: 2".
    assert "Destination page: 2\n" in out
    assert "Named via Action\n" in out


# ---------------------------------------------------------------------------
# print_document_meta_data
# ---------------------------------------------------------------------------


def test_print_document_meta_data_emits_metadata_and_dates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Lines 57-60 and 68 — ``/Metadata`` stream branch + non-None
    ``format_date``."""
    import datetime as _dt

    src = tmp_path / "meta.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        info = doc.get_document_information()
        info.set_creation_date(_dt.datetime(2024, 1, 2, 3, 4, 5))
        info.set_modification_date(_dt.datetime(2024, 6, 7, 8, 9, 10))
        # Attach an XML /Metadata stream so the metadata branch fires.
        meta_stream = COSStream()
        meta_stream.set_name(COSName.TYPE, "Metadata")
        meta_stream.set_name(COSName.SUBTYPE, "XML")
        with meta_stream.create_output_stream() as out:
            out.write(b"<?xpacket?><xmp/>")
        doc.get_document_catalog().set_metadata(PDMetadata(meta_stream))
        doc.save(str(src))
    finally:
        doc.close()

    PrintDocumentMetaData.main([str(src)])
    captured = capsys.readouterr().out
    assert "Metadata=" in captured  # the metadata branch ran (line 60)
    assert "<xmp/>" in captured
    # format_date non-None branch (line 68) → "01/02/24" prefix.
    assert "Creation Date=01/02/24" in captured
    assert "Modification Date=06/07/24" in captured


def test_format_date_static_helper_with_datetime() -> None:
    """Direct call exercises line 68 in isolation."""
    import datetime as _dt

    formatted = PrintDocumentMetaData.format_date(
        _dt.datetime(2024, 12, 31, 14, 30, 0),
    )
    assert formatted == "12/31/24 02:30 PM"


# ---------------------------------------------------------------------------
# add_message_to_each_page
# ---------------------------------------------------------------------------


def test_add_message_to_each_page_rotated_page(tmp_path: Path) -> None:
    """A 90°-rotated page exercises the rotate-branch text matrix
    (lines 40-42, 53-54)."""
    src = tmp_path / "rotated.pdf"
    dst = tmp_path / "rotated-out.pdf"
    doc = PDDocument()
    try:
        page = PDPage()
        page.set_rotation(90)  # triggers rotate=True
        doc.add_page(page)
        doc.save(str(src))
    finally:
        doc.close()

    AddMessageToEachPage().do_it(str(src), "DRAFT", str(dst))
    assert dst.exists()
    assert dst.read_bytes()[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# create_bookmarks
# ---------------------------------------------------------------------------


def test_create_bookmarks_constructor_is_a_no_op() -> None:
    """Exercises the ``__init__`` body (line 31)."""
    assert isinstance(CreateBookmarks(), CreateBookmarks)


def test_create_bookmarks_main_rejects_encrypted_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Lines 41-45 — encrypted source aborts with a stderr message and
    SystemExit(1)."""
    src = tmp_path / "enc.pdf"
    dst = tmp_path / "out.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.protect(
            StandardProtectionPolicy("owner-pw", "user-pw", AccessPermission()),
        )
        doc.save(str(src))
    finally:
        doc.close()

    with pytest.raises(SystemExit) as excinfo:
        CreateBookmarks.main([str(src), str(dst)])
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "encrypted" in err.lower()
    assert not dst.exists()
