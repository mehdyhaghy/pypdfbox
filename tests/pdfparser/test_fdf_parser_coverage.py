"""Coverage boost for ``FDFParser`` (wave 1318).

Drives the ``parse`` entry point through its success / header-failure /
post-header missing-root branches and exercises the
``initial_parse`` public mirror plus ``parse_fdf_header`` delegation.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSDocument, COSName
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import FDFParser
from pypdfbox.pdfparser.parse_error import PDFParseError


def _parser_with_bound_document(
    source_bytes: bytes,
    trailer: COSDictionary | None,
) -> tuple[FDFParser, COSDocument]:
    """Build an ``FDFParser`` over ``source_bytes`` and bind a freshly
    built ``COSDocument`` whose trailer is ``trailer``. The caller owns
    the document lifecycle."""
    parser = FDFParser(RandomAccessReadBuffer(source_bytes))
    document = COSDocument()
    if trailer is not None:
        document.set_trailer(trailer)
    parser._document = document
    return parser, document


# ----------------------------------------------------------------------
# initial_parse / _initial_parse
# ----------------------------------------------------------------------


def test_initial_parse_succeeds_when_trailer_has_root() -> None:
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, COSDictionary())
    parser, document = _parser_with_bound_document(
        b"%FDF-1.2\n%%EOF\n", trailer
    )
    try:
        parser.initial_parse()
        assert parser.is_initial_parse_done() is True
    finally:
        document.close()


def test_initial_parse_raises_when_root_missing() -> None:
    parser, document = _parser_with_bound_document(
        b"%FDF-1.2\n%%EOF\n", COSDictionary()
    )
    try:
        with pytest.raises(PDFParseError, match="Missing root"):
            parser.initial_parse()
    finally:
        document.close()


def test_underscore_initial_parse_matches_public_mirror() -> None:
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, COSDictionary())
    parser, document = _parser_with_bound_document(
        b"%FDF-1.2\n%%EOF\n", trailer
    )
    try:
        parser._initial_parse()
        assert parser.is_initial_parse_done()
    finally:
        document.close()


# ----------------------------------------------------------------------
# parse()
# ----------------------------------------------------------------------


def test_parse_returns_fdf_document_on_happy_path() -> None:
    from pypdfbox.pdmodel.fdf import FDFDocument

    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, COSDictionary())
    parser, document = _parser_with_bound_document(
        b"%FDF-1.2\n%%EOF\n", trailer
    )
    # Upstream ``FDFParser.parse`` reads ``self.source`` for the optional
    # backing-store handed to :class:`FDFDocument`. The pypdfbox port
    # carries the source under ``_src`` so we expose it as ``source`` for
    # the round-trip below.
    parser.source = parser._src  # type: ignore[attr-defined]
    try:
        fdf = parser.parse()
        assert isinstance(fdf, FDFDocument)
        # The returned doc wraps the same COSDocument the parser held.
        assert fdf.get_document() is document
        # No exception occurred, so the parser must retain its document.
        assert parser._document is document
    finally:
        document.close()


def test_parse_raises_when_header_missing_and_clears_document() -> None:
    """``parse_fdf_header`` returns ``False`` / raises when no header is
    present — ``parse`` must wrap that as ``PDFParseError`` and drop the
    bound document via its ``finally`` cleanup."""
    parser, document = _parser_with_bound_document(
        b"no header here", COSDictionary()
    )
    try:
        with pytest.raises(PDFParseError):
            parser.parse()
        # The cleanup branch nulled the bound document.
        assert parser._document is None
    finally:
        document.close()


def test_parse_propagates_initial_parse_failure_and_clears_document() -> None:
    """Header is fine but ``/Root`` is missing — ``_initial_parse`` raises
    and ``parse`` must close + drop the bound document."""
    parser, document = _parser_with_bound_document(
        b"%FDF-1.2\n%%EOF\n", COSDictionary()
    )
    try:
        with pytest.raises(PDFParseError, match="Missing root"):
            parser.parse()
        assert parser._document is None
    finally:
        document.close()


# ----------------------------------------------------------------------
# parse_fdf_header()
# ----------------------------------------------------------------------


def test_parse_fdf_header_returns_version_for_well_formed_input() -> None:
    parser = FDFParser(RandomAccessReadBuffer(b"%FDF-1.4\n"))
    assert parser.parse_fdf_header() == pytest.approx(1.4)


def test_parse_fdf_header_raises_on_missing_marker() -> None:
    parser = FDFParser(RandomAccessReadBuffer(b"completely-unrelated"))
    with pytest.raises(PDFParseError):
        parser.parse_fdf_header()


def test_has_fdf_header_predicate_is_non_throwing() -> None:
    ok = FDFParser(RandomAccessReadBuffer(b"%FDF-1.2\n"))
    assert ok.has_fdf_header() is True
    bad = FDFParser(RandomAccessReadBuffer(b"not-fdf"))
    assert bad.has_fdf_header() is False


def test_constructor_accepts_random_access_read() -> None:
    parser = FDFParser(RandomAccessReadBuffer(b"%FDF-1.2\n%%EOF\n"))
    # Inherited COSParser surface is wired up correctly.
    assert parser.is_initial_parse_done() is False


# ----------------------------------------------------------------------
# wave 1351 — fdf_parser.py lines 62 and 86
# ----------------------------------------------------------------------


def test_parse_wraps_falsy_header_result_as_parse_error() -> None:
    """When ``parse_fdf_header`` returns a falsy value (rather than
    raising), ``parse`` must wrap that as ``PDFParseError`` (covers
    ``fdf_parser.py`` line 62 — the explicit raise inside the
    ``if not self.parse_fdf_header():`` branch)."""
    parser, document = _parser_with_bound_document(
        b"%FDF-1.2\n%%EOF\n", COSDictionary()
    )
    # Force ``parse_fdf_header`` to return ``False`` so the wrapping
    # raise on line 62 is taken (vs the upstream behaviour of raising).
    parser.parse_fdf_header = lambda: False  # type: ignore[method-assign]
    try:
        with pytest.raises(PDFParseError, match="versioninfo"):
            parser.parse()
        # ``parse`` cleanup still nulls the bound document.
        assert parser._document is None
    finally:
        document.close()


def test_parse_fdf_header_falls_back_to_parse_pdf_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the underlying :class:`COSParser` doesn't expose
    ``parse_fdf_header``, :meth:`FDFParser.parse_fdf_header` falls
    through to ``parse_pdf_header`` (covers ``fdf_parser.py`` line 86).
    """
    from pypdfbox.pdfparser.cos_parser import COSParser

    # Strip the parent's ``parse_fdf_header`` so ``getattr(super(),
    # 'parse_fdf_header', None)`` resolves to ``None`` — the fallback
    # branch must then call ``parse_pdf_header`` instead.
    monkeypatch.delattr(COSParser, "parse_fdf_header")

    # Use a ``%PDF-`` marker so the fallback ``parse_pdf_header``
    # accepts the bytes — the fallback's marker is "%PDF-", not "%FDF-".
    parser = FDFParser(RandomAccessReadBuffer(b"%PDF-1.4\n"))
    result = parser.parse_fdf_header()
    # ``parse_pdf_header`` returns the float version on success.
    assert result == pytest.approx(1.4)


def test_parse_fdf_header_fallback_branch_short_circuits_when_super_attr_not_callable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``super().parse_fdf_header`` resolves to a non-callable value
    (a defensive guard), the method must still fall through to
    ``parse_pdf_header`` — equivalent path to the ``None`` case but
    documents the ``callable()`` branch explicitly."""
    from pypdfbox.pdfparser.cos_parser import COSParser

    # Replace the inherited method with a non-callable sentinel so the
    # ``callable(parse_fdf)`` check returns ``False``.
    monkeypatch.setattr(COSParser, "parse_fdf_header", "not-a-method")
    parser = FDFParser(RandomAccessReadBuffer(b"%PDF-1.5\n"))
    assert parser.parse_fdf_header() == pytest.approx(1.5)
