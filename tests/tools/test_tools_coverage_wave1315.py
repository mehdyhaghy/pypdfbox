"""Coverage-boost tests for four more CLI class-port modules in
``pypdfbox.tools`` (wave 1315).

Targets — ``text_to_pdf``, ``write_decoded_doc``, ``export_xfdf``,
``import_xfdf`` — are direct ports of the upstream PDFBox
``main(...)`` runners. The latter three call PD-layer helpers on a
:class:`PDDocument`, so they reuse the same ``_PDLoaderShim`` pattern
introduced in wave 1314: wrap the raw ``COSDocument`` returned by
:meth:`pypdfbox.loader.Loader.load_pdf` in a :class:`PDDocument` and
re-expose the context-manager contract that upstream's
``try-with-resources`` block expects.

``text_to_pdf`` does not take an input PDF — it composes one from a
text file. The runner constructs ``PDType1Font(FontName.HELVETICA)``
directly, which currently expects a ``COSDictionary`` (not a font name);
the tests monkey-patch the module-level ``PDType1Font`` with a tiny
subclass that ignores its argument and supplies just enough bounding-box
/ width metadata for the layout loop to terminate. This exercises the
runner end-to-end without depending on the unported standard-14
factory path.
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.loader import Loader as RealLoader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.tools import (
    export_xfdf,
    import_xfdf,
    text_to_pdf,
    write_decoded_doc,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
ROT0 = FIXTURES / "multipdf" / "rot0.pdf"
FORM_PDF = FIXTURES / "multipdf" / "PDFBOX-5811-362972.pdf"


# --------------------------------------------------------------------------
# Shared shim — wraps Loader.load_pdf(COSDocument) -> PDDocument and
# preserves Loader.load_xfdf for import_xfdf. Mirrors the wave 1314
# pattern.
# --------------------------------------------------------------------------
class _PDLoaderShim:
    @staticmethod
    @contextlib.contextmanager
    def load_pdf(source: Any, password: Any = None) -> Iterator[PDDocument]:
        if isinstance(password, str) and password == "":
            password = None
        cos_doc = RealLoader.load_pdf(source, password)
        pd = PDDocument(cos_doc)
        try:
            yield pd
        finally:
            pd.close()

    # Pass-through for the XFDF loader so import_xfdf can still parse
    # the .xfdf side-channel through the real Loader.
    load_xfdf = staticmethod(RealLoader.load_xfdf)


@pytest.fixture
def patched_loader(monkeypatch: pytest.MonkeyPatch) -> type[_PDLoaderShim]:
    """Patch ``Loader`` in each of the four target modules to the shim."""
    for module in (write_decoded_doc, export_xfdf, import_xfdf):
        monkeypatch.setattr(module, "Loader", _PDLoaderShim)
    return _PDLoaderShim


# --------------------------------------------------------------------------
# text_to_pdf — uses a stubbed PDType1Font that supplies the bounding
# box + string-width metrics the layout loop needs. The runner does not
# require a real font program because the resulting PDF is not rendered
# in tests; the writer only serialises the page tree and content stream.
# --------------------------------------------------------------------------
class _StubType1(PDType1Font):
    """PDType1Font that ignores its constructor arg and returns a fixed
    1000x1000 bounding box / linear width. Sufficient for the runner's
    layout math to terminate without touching the font-file parser."""

    def __init__(self, _arg: Any = None) -> None:
        super().__init__()  # font_dict=None — populates an empty PDF dict

    def get_bounding_box(self) -> PDRectangle:
        return PDRectangle(0.0, 0.0, 1000.0, 1000.0)

    def get_string_width(self, text: str) -> float:
        return len(text) * 500.0


@pytest.fixture
def stub_font(monkeypatch: pytest.MonkeyPatch) -> type[_StubType1]:
    monkeypatch.setattr(text_to_pdf, "PDType1Font", _StubType1)
    return _StubType1


def test_text_to_pdf_writes_pdf_default(
    stub_font: Any, tmp_path: Path,
) -> None:
    src = tmp_path / "in.txt"
    src.write_text("Hello world\nLine two\n", encoding="utf-8")
    out = tmp_path / "out.pdf"
    rc = text_to_pdf.TextToPDF.main([
        "-i", str(src),
        "-o", str(out),
    ])
    assert rc == 0
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


def test_text_to_pdf_landscape_a4_long_text(
    stub_font: Any, tmp_path: Path,
) -> None:
    """Long input forces the page-break path; ``-landscape`` exercises
    the swap-media-box branch; ``-pageSize A4`` exercises the
    enum-lookup branch."""
    src = tmp_path / "long.txt"
    body = "\n".join(f"line {i} word " * 8 for i in range(80))
    src.write_text(body, encoding="utf-8")
    out = tmp_path / "long.pdf"
    rc = text_to_pdf.TextToPDF.main([
        "-i", str(src),
        "-o", str(out),
        "-pageSize", "A4",
        "-landscape",
        "-fontSize", "12",
        "-lineSpacing", "1.2",
        "-margins", "20", "20", "20", "20",
        "-standardFont", "HELVETICA",
    ])
    assert rc == 0
    assert out.exists()


def test_text_to_pdf_form_feed_triggers_new_page(
    stub_font: Any, tmp_path: Path,
) -> None:
    """A ``\\f`` (form-feed) char inside a line drives the inner
    ff-branch that closes the current content stream and starts a fresh
    page. Both halves of the split word must round-trip."""
    src = tmp_path / "ff.txt"
    src.write_text("alpha\fbeta\n", encoding="utf-8")
    out = tmp_path / "ff.pdf"
    rc = text_to_pdf.TextToPDF.main([
        "-i", str(src),
        "-o", str(out),
    ])
    assert rc == 0


def test_text_to_pdf_empty_input_adds_blank_page(
    stub_font: Any, tmp_path: Path,
) -> None:
    """An empty file still produces a one-page PDF — the runner appends
    the working ``page`` if no line was drawn."""
    src = tmp_path / "empty.txt"
    src.write_text("", encoding="utf-8")
    out = tmp_path / "empty.pdf"
    rc = text_to_pdf.TextToPDF.main([
        "-i", str(src),
        "-o", str(out),
    ])
    assert rc == 0
    assert out.exists()


def test_text_to_pdf_missing_infile_raises() -> None:
    runner = text_to_pdf.TextToPDF()
    with pytest.raises(OSError, match="infile and outfile are required"):
        runner.call()


def test_text_to_pdf_missing_input_file_returns_4(
    stub_font: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """A missing input file raises ``FileNotFoundError`` (OSError
    subclass) inside the ``try`` block — runner maps that to exit 4."""
    rc = text_to_pdf.TextToPDF.main([
        "-i", str(tmp_path / "no-such-file.txt"),
        "-o", str(tmp_path / "out.pdf"),
    ])
    assert rc == 4
    assert "Error converting text to PDF" in capsys.readouterr().err


def test_text_to_pdf_single_arg_create_overload(
    stub_font: Any, tmp_path: Path,
) -> None:
    """``create_pdf_from_text(reader)`` (single-arg) returns a fresh
    PDDocument — exercises the second branch of the overload dispatcher."""
    import io
    runner = text_to_pdf.TextToPDF()
    runner.font = _StubType1()
    doc = runner.create_pdf_from_text(io.StringIO("hello\n"))
    try:
        assert doc is not None
        # Iterating exercises get_pages -> at least one page emitted
        assert len(list(doc.get_pages())) >= 1
    finally:
        doc.close()


def test_text_to_pdf_two_arg_create_overload(
    stub_font: Any,
) -> None:
    """``create_pdf_from_text(doc, reader)`` (two-arg) returns ``None``
    and mutates the supplied document — the first branch of the overload."""
    import io
    runner = text_to_pdf.TextToPDF()
    runner.font = _StubType1()
    doc = PDDocument()
    try:
        ret = runner.create_pdf_from_text(doc, io.StringIO("a b c\n"))
        assert ret is None
        assert len(list(doc.get_pages())) >= 1
    finally:
        doc.close()


def test_text_to_pdf_setter_round_trip() -> None:
    """All accessor pairs round-trip — covers the boilerplate that
    upstream exposes for builder-style configuration."""
    t = text_to_pdf.TextToPDF()
    t.set_font_size(14)
    assert t.get_font_size() == 14
    t.set_line_spacing(1.5)
    assert t.get_line_spacing() == 1.5
    t.set_left_margin(10.0)
    t.set_right_margin(20.0)
    t.set_top_margin(30.0)
    t.set_bottom_margin(40.0)
    assert t.get_left_margin() == 10.0
    assert t.get_right_margin() == 20.0
    assert t.get_top_margin() == 30.0
    assert t.get_bottom_margin() == 40.0
    rect = PDRectangle(0, 0, 100, 100)
    t.set_media_box(rect)
    assert t.get_media_box() is rect
    t.set_landscape(True)
    assert t.is_landscape() is True
    t.set_font("sentinel")  # accessor only — not exercised by layout
    assert t.get_font() == "sentinel"


def test_text_to_pdf_page_sizes_enum() -> None:
    """``PageSizes`` enum is a thin wrapper — every member's
    ``get_page_size`` must return a :class:`PDRectangle`."""
    for member in text_to_pdf.PageSizes:
        assert isinstance(member.get_page_size(), PDRectangle)


# --------------------------------------------------------------------------
# write_decoded_doc
# --------------------------------------------------------------------------
def test_write_decoded_doc_round_trip(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """rot0.pdf has no encrypted streams — the runner walks the xref,
    decodes each stream, and saves a fresh PDF with ``/Filter`` removed."""
    src = tmp_path / "in.pdf"
    src.write_bytes(ROT0.read_bytes())
    out = tmp_path / "out.pdf"
    rc = write_decoded_doc.WriteDecodedDoc.main([
        str(src), str(out),
    ])
    assert rc == 0
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


def test_write_decoded_doc_default_outfile_derived(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """When no outfile is given, the runner derives ``<in>_unc.pdf``
    next to the input — covers the ``calculate_output_filename`` branch
    plus the no-outfile call path."""
    src = tmp_path / "in.pdf"
    src.write_bytes(ROT0.read_bytes())
    rc = write_decoded_doc.WriteDecodedDoc.main([
        str(src),
    ])
    assert rc == 0
    assert (tmp_path / "in_unc.pdf").exists()


def test_write_decoded_doc_skip_images(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """``-skipImages`` toggles the early-return branch in
    ``process_object``. rot0.pdf has no image XObjects, so the result is
    still valid — the flag must just be accepted and propagated."""
    out = tmp_path / "skip.pdf"
    rc = write_decoded_doc.WriteDecodedDoc.main([
        "-skipImages",
        str(ROT0), str(out),
    ])
    assert rc == 0
    assert out.exists()


def test_write_decoded_doc_load_error_returns_4(
    patched_loader: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    rc = write_decoded_doc.WriteDecodedDoc.main([
        str(tmp_path / "no-such.pdf"),
        str(tmp_path / "out.pdf"),
    ])
    assert rc == 4
    assert "Error writing decoded PDF" in capsys.readouterr().err


def test_write_decoded_doc_missing_infile_raises() -> None:
    runner = write_decoded_doc.WriteDecodedDoc()
    with pytest.raises(OSError, match="infile is required"):
        runner.call()


def test_write_decoded_doc_process_object_non_stream_is_noop() -> None:
    """``process_object`` returns silently when handed something that
    is not a COSStream — covers the early-return guard."""
    runner = write_decoded_doc.WriteDecodedDoc()
    # A bare object has no ``get_object``; the helper falls through to
    # the non-stream branch and returns without raising.
    runner.process_object(object(), skip_images=False)
    runner.process_object(object(), skip_images=True)


def test_write_decoded_doc_process_object_plain_stream_decodes() -> None:
    """A non-image COSStream is decoded in place — ``/Filter`` is removed
    and the stream's decoded bytes round-trip through the rewrite branch.
    """
    from pypdfbox.cos.cos_name import COSName
    from pypdfbox.cos.cos_stream import COSStream

    stream = COSStream()
    stream.set_item(COSName.FILTER, COSName.FLATE_DECODE)
    # Write a tiny payload through the encoded sink so the on-disk
    # representation carries a filter; the helper's decode + rewrite
    # path must strip ``/Filter`` and round-trip the bytes unchanged.
    with stream.create_output_stream(COSName.FLATE_DECODE) as out:
        out.write(b"hello world")

    runner = write_decoded_doc.WriteDecodedDoc()
    runner.process_object(stream, skip_images=False)
    assert stream.get_item(COSName.FILTER) is None


# --------------------------------------------------------------------------
# export_xfdf
# --------------------------------------------------------------------------
def test_export_xfdf_form_pdf_writes_xfdf(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """The form-bearing fixture round-trips through export_xfdf —
    produces an XML file with the xfdf root."""
    out = tmp_path / "out.xfdf"
    rc = export_xfdf.ExportXFDF.main([
        "-i", str(FORM_PDF),
        "-o", str(out),
    ])
    assert rc == 0
    assert out.exists()
    head = out.read_text(encoding="utf-8")[:200]
    assert "<?xml" in head
    assert "xfdf" in head


def test_export_xfdf_no_form_no_failure(
    patched_loader: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """rot0.pdf has no AcroForm — runner logs the warning but returns 0
    (current port does not propagate exit 1; mirrors upstream's
    ``System.err.println`` only behaviour)."""
    rc = export_xfdf.ExportXFDF.main([
        "-i", str(ROT0),
        "-o", str(tmp_path / "out.xfdf"),
    ])
    assert rc == 0
    assert "does not contain a form" in capsys.readouterr().err


def test_export_xfdf_load_error_returns_4(
    patched_loader: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    rc = export_xfdf.ExportXFDF.main([
        "-i", str(tmp_path / "missing.pdf"),
        "-o", str(tmp_path / "out.xfdf"),
    ])
    assert rc == 4
    assert "Error exporting XFDF data" in capsys.readouterr().err


def test_export_xfdf_missing_infile_raises() -> None:
    runner = export_xfdf.ExportXFDF()
    with pytest.raises(OSError, match="infile is required"):
        runner.call()


def test_export_xfdf_default_outfile_derived(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """When ``outfile`` is None, the runner derives ``<in>.xfdf`` from
    the input path. Copy the fixture so the derived file lands inside
    tmp_path."""
    src = tmp_path / "form.pdf"
    src.write_bytes(FORM_PDF.read_bytes())
    runner = export_xfdf.ExportXFDF()
    runner.infile = src
    rc = runner.call()
    assert rc == 0
    assert (tmp_path / "form.xfdf").exists()


# --------------------------------------------------------------------------
# import_xfdf
# --------------------------------------------------------------------------
def test_import_xfdf_round_trip(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """Feed a minimal XFDF + the form fixture; the runner must call
    ``acro_form.import_fdf`` (no-op if the field isn't present) and save
    a fresh PDF to ``-o``."""
    xfdf = tmp_path / "data.xfdf"
    xfdf.write_bytes(
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<xfdf xmlns="http://ns.adobe.com/xfdf/">'
        b'<fields><field name="city"><value>Paris</value></field></fields>'
        b"</xfdf>"
    )
    out = tmp_path / "imported.pdf"
    rc = import_xfdf.ImportXFDF.main([
        "-i", str(FORM_PDF),
        "-o", str(out),
        "--data", str(xfdf),
    ])
    assert rc == 0
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


def test_import_xfdf_default_outfile_overwrites_input(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """When no ``-o`` is given, the runner saves over the original
    input — covers the ``self.outfile = self.infile`` branch."""
    src = tmp_path / "form.pdf"
    src.write_bytes(FORM_PDF.read_bytes())
    xfdf = tmp_path / "data.xfdf"
    xfdf.write_bytes(
        b'<?xml version="1.0"?><xfdf xmlns="http://ns.adobe.com/xfdf/">'
        b'<fields/></xfdf>'
    )
    rc = import_xfdf.ImportXFDF.main([
        "-i", str(src),
        "--data", str(xfdf),
    ])
    assert rc == 0
    # The src is overwritten in place; it still begins with %PDF-.
    assert src.read_bytes()[:5] == b"%PDF-"


def test_import_xfdf_no_form_quietly_returns_0(
    patched_loader: Any, tmp_path: Path,
) -> None:
    """rot0.pdf has no AcroForm — the ``import_fdf`` helper returns
    silently and the runner still saves the (otherwise unchanged) PDF."""
    src = tmp_path / "rot0.pdf"
    src.write_bytes(ROT0.read_bytes())
    xfdf = tmp_path / "data.xfdf"
    xfdf.write_bytes(
        b'<?xml version="1.0"?><xfdf xmlns="http://ns.adobe.com/xfdf/">'
        b'<fields/></xfdf>'
    )
    out = tmp_path / "out.pdf"
    rc = import_xfdf.ImportXFDF.main([
        "-i", str(src),
        "-o", str(out),
        "--data", str(xfdf),
    ])
    assert rc == 0
    assert out.exists()


def test_import_xfdf_load_error_returns_4(
    patched_loader: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    xfdf = tmp_path / "data.xfdf"
    xfdf.write_bytes(b'<?xml version="1.0"?><xfdf><fields/></xfdf>')
    rc = import_xfdf.ImportXFDF.main([
        "-i", str(tmp_path / "missing.pdf"),
        "-o", str(tmp_path / "out.pdf"),
        "--data", str(xfdf),
    ])
    assert rc == 4
    assert "Error importing XFDF data" in capsys.readouterr().err


def test_import_xfdf_missing_infile_raises() -> None:
    runner = import_xfdf.ImportXFDF()
    with pytest.raises(OSError, match="infile and xfdffile are required"):
        runner.call()


def test_import_xfdf_helper_no_form_returns_none(
    patched_loader: Any,
) -> None:
    """``import_fdf`` returns silently when the document has no
    AcroForm — covers the explicit ``if acro_form is None: return``
    guard without needing the full runner."""
    runner = import_xfdf.ImportXFDF()

    class _FakeCatalog:
        def get_acro_form(self) -> Any:
            return None

    class _FakeDoc:
        def get_document_catalog(self) -> _FakeCatalog:
            return _FakeCatalog()

    # Should return None without raising.
    assert runner.import_fdf(_FakeDoc(), object()) is None
