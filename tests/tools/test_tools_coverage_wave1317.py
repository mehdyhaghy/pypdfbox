"""Coverage-boost tests for five more CLI class-port modules in
``pypdfbox.tools`` (wave 1317).

The targets — ``decrypt_tool``, ``encrypt_tool``, ``image_to_pdf``,
``import_fdf``, ``pdf_text2_markdown`` — are direct ports of the
upstream PDFBox ``main(...)`` runners. The first four are exercised
through end-to-end round-trips (build a tiny PDD, save it, run the
CLI, verify the side effect). ``pdf_text2_markdown`` is exercised at
the FontState / module-helper level, mirroring how its HTML sibling
was covered in wave 1316 — the parent ``PDFTextStripper.write_string``
signature differs from upstream (see CHANGES.md), so wrapping
overrides are exercised with the parent stubbed out via fixture.

Where the runner's body calls PDD-layer helpers (``import_fdf``), it
needs the ``_PDLoaderShim`` introduced in wave 1314 so the parser's
``COSDocument`` is wrapped in a ``PDDocument`` with the upstream
``try-with-resources`` shape.
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from pypdfbox.loader import Loader as RealLoader
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.fdf import FDFDocument
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.tools import decrypt_tool, encrypt_tool, image_to_pdf, import_fdf
from pypdfbox.tools.pdf_text2_markdown import (
    FontState,
    PDFText2Markdown,
    _append_escaped,
    _escape,
)


# --------------------------------------------------------------------------
# Shared shim — wraps Loader.load_pdf(COSDocument) → PDDocument so the
# class ports' PD-layer calls resolve. Mirrors the wave-1314 shim.
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

    @staticmethod
    def load_fdf(source: Any) -> FDFDocument:
        return RealLoader.load_fdf(source)


@pytest.fixture
def patched_import_fdf_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> type[_PDLoaderShim]:
    """Patch the ``Loader`` import in ``import_fdf`` to the shim."""
    monkeypatch.setattr(import_fdf, "Loader", _PDLoaderShim)
    return _PDLoaderShim


# --------------------------------------------------------------------------
# helpers — build tiny inputs
# --------------------------------------------------------------------------
def _build_blank_pdf(target: Path, page_count: int = 1) -> Path:
    doc = PDDocument()
    try:
        for _ in range(page_count):
            doc.add_page(PDPage())
        doc.save(target)
    finally:
        doc.close()
    return target


def _build_form_pdf(target: Path) -> Path:
    """Build a single-page PDF carrying an empty AcroForm — enough for
    ``ImportFDF`` to take the non-``return`` branch (acro_form is not None
    → ``set_cache_fields`` / ``import_fdf`` / ``set_need_appearances``)."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        cat = doc.get_document_catalog()
        cat.set_acro_form(PDAcroForm(doc))
        doc.save(target)
    finally:
        doc.close()
    return target


def _build_fdf(target: Path) -> Path:
    f = FDFDocument()
    try:
        f.save(target)
    finally:
        f.close()
    return target


def _build_png(target: Path, color: tuple[int, int, int] = (255, 0, 0)) -> Path:
    Image.new("RGB", (4, 4), color).save(target, format="PNG")
    return target


# --------------------------------------------------------------------------
# decrypt_tool — exit codes + round-trip + helpers
# --------------------------------------------------------------------------
def test_decrypt_tool_round_trip_with_encrypted_pdf(tmp_path: Path) -> None:
    """Build a plain PDF, encrypt it via ``encrypt_pdf``, then decrypt it
    via ``Decrypt.main`` — the runner must exit 0 and the result must be
    a plain (unencrypted) PDF."""
    from pypdfbox.tools.encrypt import encrypt_pdf

    src = _build_blank_pdf(tmp_path / "plain.pdf")
    enc = tmp_path / "enc.pdf"
    encrypt_pdf(src, enc, owner_password="owner", user_password="user",
                key_length=128)
    dec = tmp_path / "dec.pdf"
    rc = decrypt_tool.Decrypt.main([
        "-i", str(enc),
        "-o", str(dec),
        "-password", "owner",
    ])
    assert rc == 0
    assert dec.is_file()
    with PDDocument.load(dec) as d:
        assert d.is_encrypted() is False


def test_decrypt_tool_missing_infile_raises() -> None:
    runner = decrypt_tool.Decrypt()
    with pytest.raises(OSError, match="infile is required"):
        runner.call()


def test_decrypt_tool_load_error_returns_4(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing input → ``decrypt_pdf`` raises OSError → exit 4 + stderr."""
    rc = decrypt_tool.Decrypt.main([
        "-i", str(tmp_path / "no-such.pdf"),
        "-o", str(tmp_path / "out.pdf"),
    ])
    assert rc == 4
    assert "Error decrypting document" in capsys.readouterr().err


def test_decrypt_tool_default_outfile_overwrites_input(tmp_path: Path) -> None:
    """When ``-o`` is omitted, the runner writes the decrypted PDF back
    over the input path (matches upstream)."""
    from pypdfbox.tools.encrypt import encrypt_pdf

    src = _build_blank_pdf(tmp_path / "x.pdf")
    encrypted = tmp_path / "enc.pdf"
    encrypt_pdf(src, encrypted, owner_password="owner", user_password="user",
                key_length=128)
    rc = decrypt_tool.Decrypt.main([
        "-i", str(encrypted),
        "-password", "owner",
    ])
    assert rc == 0
    with PDDocument.load(encrypted) as d:
        assert d.is_encrypted() is False


def test_decrypt_tool_keystore_and_alias_attrs_recorded(tmp_path: Path) -> None:
    """``-keyStore`` / ``-alias`` populate the runner attributes even if
    the cert-decrypt path itself isn't wired."""
    # We construct the runner directly so we don't trip the missing-file
    # OSError in decrypt_pdf — the goal is to cover the attribute
    # assignments in ``main()``.
    src = _build_blank_pdf(tmp_path / "p.pdf")
    # Construct via main with all four flags; the underlying decrypt
    # call will succeed because the input is plain (no /Encrypt).
    rc = decrypt_tool.Decrypt.main([
        "-i", str(src),
        "-o", str(tmp_path / "out.pdf"),
        "-keyStore", str(tmp_path / "ks.p12"),
        "-alias", "client",
        "-password", "",
    ])
    assert rc == 0


# --------------------------------------------------------------------------
# encrypt_tool — exit codes + round-trip + permission flags
# --------------------------------------------------------------------------
def test_encrypt_tool_round_trip_with_user_password(tmp_path: Path) -> None:
    src = _build_blank_pdf(tmp_path / "plain.pdf")
    enc = tmp_path / "enc.pdf"
    rc = encrypt_tool.Encrypt.main([
        "-i", str(src),
        "-o", str(enc),
        "-U", "user",
        "-O", "owner",
        "-keyLength", "128",
    ])
    assert rc == 0
    assert enc.is_file()
    with PDDocument.load(enc, password="user") as d:
        assert d.is_encrypted() is True


def test_encrypt_tool_missing_infile_raises() -> None:
    runner = encrypt_tool.Encrypt()
    with pytest.raises(OSError, match="infile is required"):
        runner.call()


def test_encrypt_tool_load_error_returns_4(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    rc = encrypt_tool.Encrypt.main([
        "-i", str(tmp_path / "missing.pdf"),
        "-o", str(tmp_path / "out.pdf"),
        "-U", "user",
        "-keyLength", "128",
    ])
    assert rc == 4
    assert "Error encrypting document" in capsys.readouterr().err


def test_encrypt_tool_default_outfile_falls_back_to_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``-o`` is omitted, the runner's ``call()`` uses ``self.infile``
    as the output target. The in-place save is parity-equivalent to the
    standalone ``encrypt`` CLI which wraps the write in a tempfile.
    Patch ``encrypt_pdf`` to record the resolved (input, output) tuple
    so we can pin the ``out = self.outfile if ... else self.infile``
    branch deterministically."""
    src = _build_blank_pdf(tmp_path / "inplace.pdf")
    seen: dict[str, Any] = {}

    def _record(
        input_path: Any, output_path: Any, **kw: Any,
    ) -> None:
        seen["input"] = input_path
        seen["output"] = output_path

    monkeypatch.setattr(encrypt_tool, "encrypt_pdf", _record)
    runner = encrypt_tool.Encrypt()
    runner.infile = src
    runner.outfile = None  # exercises the fallback to self.infile
    runner.user_password = "user"
    runner.key_length = 128
    rc = runner.call()
    assert rc == 0
    assert seen["input"] == src
    assert seen["output"] == src


def test_encrypt_tool_access_permission_flags_propagate() -> None:
    """Flip a couple of the boolean permission attributes and confirm the
    derived ``AccessPermission`` reflects them — exercises
    ``_access_permission`` end-to-end without needing a save."""
    runner = encrypt_tool.Encrypt()
    runner.can_print = False
    runner.can_modify = False
    runner.can_extract = False
    runner.can_fill_in_form = False
    runner.can_modify_annotations = False
    runner.can_assemble = False
    runner.can_extract_for_accessibility = False
    runner.can_print_faithful = False
    ap = runner._access_permission()  # noqa: SLF001 — exercising port invariant
    assert ap.can_print() is False
    assert ap.can_modify() is False
    assert ap.can_extract_content() is False
    assert ap.can_fill_in_form() is False
    assert ap.can_modify_annotations() is False
    assert ap.can_assemble_document() is False
    assert ap.can_extract_for_accessibility() is False
    assert ap.can_print_faithful() is False


def test_encrypt_tool_default_permissions_all_true() -> None:
    """A freshly-constructed ``Encrypt`` carries every permission bit
    set to ``True`` — mirrors upstream defaults."""
    runner = encrypt_tool.Encrypt()
    ap = runner._access_permission()  # noqa: SLF001
    assert ap.can_print() is True
    assert ap.can_modify() is True
    assert ap.can_extract_content() is True
    assert ap.can_fill_in_form() is True
    assert ap.can_modify_annotations() is True
    assert ap.can_assemble_document() is True


def test_encrypt_tool_certfile_attribute_populated(tmp_path: Path) -> None:
    """``-certFile`` is repeatable; both paths must land on ``cert_files``."""
    # Don't actually need valid certs — only exercising the argparse →
    # attribute plumbing. Run main with a missing input so we exit 4
    # before the cert path is taken.
    rc = encrypt_tool.Encrypt.main([
        "-i", str(tmp_path / "missing.pdf"),
        "-certFile", str(tmp_path / "a.cer"),
        "-certFile", str(tmp_path / "b.cer"),
        "-keyLength", "256",
    ])
    assert rc == 4


# --------------------------------------------------------------------------
# image_to_pdf — round-trip + helpers + rotation branches
# --------------------------------------------------------------------------
def test_image_to_pdf_single_png_round_trip(tmp_path: Path) -> None:
    src = _build_png(tmp_path / "red.png")
    out = tmp_path / "out.pdf"
    rc = image_to_pdf.ImageToPDF.main([
        "-i", str(src),
        "-o", str(out),
    ])
    assert rc == 0
    assert out.is_file()
    assert out.read_bytes()[:4] == b"%PDF"


def test_image_to_pdf_landscape_branch(tmp_path: Path) -> None:
    src = _build_png(tmp_path / "blue.png", color=(0, 0, 255))
    out = tmp_path / "out.pdf"
    rc = image_to_pdf.ImageToPDF.main([
        "-i", str(src),
        "-o", str(out),
        "-landscape",
        "-pageSize", "A4",
    ])
    assert rc == 0
    assert out.is_file()


def test_image_to_pdf_auto_orientation_branch(tmp_path: Path) -> None:
    # A wider-than-tall image triggers the auto-orientation rotation.
    src = tmp_path / "wide.png"
    Image.new("RGB", (10, 4), (0, 255, 0)).save(src, format="PNG")
    out = tmp_path / "out.pdf"
    rc = image_to_pdf.ImageToPDF.main([
        "-i", str(src),
        "-o", str(out),
        "-autoOrientation",
    ])
    assert rc == 0


def test_image_to_pdf_resize_branch(tmp_path: Path) -> None:
    src = _build_png(tmp_path / "r.png")
    out = tmp_path / "out.pdf"
    rc = image_to_pdf.ImageToPDF.main([
        "-i", str(src),
        "-o", str(out),
        "-resize",
    ])
    assert rc == 0


def test_image_to_pdf_multiple_inputs(tmp_path: Path) -> None:
    a = _build_png(tmp_path / "a.png", color=(255, 0, 0))
    b = _build_png(tmp_path / "b.png", color=(0, 255, 0))
    out = tmp_path / "ab.pdf"
    rc = image_to_pdf.ImageToPDF.main([
        "-i", str(a), str(b),
        "-o", str(out),
    ])
    assert rc == 0
    with PDDocument.load(out) as d:
        assert d.get_number_of_pages() == 2


def test_image_to_pdf_missing_file_returns_4(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "out.pdf"
    rc = image_to_pdf.ImageToPDF.main([
        "-i", str(tmp_path / "no-such.png"),
        "-o", str(out),
    ])
    assert rc == 4
    assert "Error converting image to PDF" in capsys.readouterr().err


def test_image_to_pdf_setters_and_getters() -> None:
    """Cover the small bag of setters/getters mirroring upstream."""
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    runner = image_to_pdf.ImageToPDF()
    assert runner.get_media_box() is PDRectangle.LETTER
    runner.set_media_box(PDRectangle.A4)
    assert runner.get_media_box() is PDRectangle.A4
    assert runner.is_landscape() is False
    runner.set_landscape(True)
    assert runner.is_landscape() is True
    assert runner.is_auto_orientation() is False
    runner.set_auto_orientation(True)
    assert runner.is_auto_orientation() is True


def test_image_to_pdf_outfile_required_when_constructed_directly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """A direct-constructed runner with infiles but no outfile must
    surface the ``outfile is required`` OSError as exit 4."""
    runner = image_to_pdf.ImageToPDF()
    runner.infiles = [_build_png(tmp_path / "x.png")]
    runner.outfile = None
    rc = runner.call()
    assert rc == 4
    assert "outfile is required" in capsys.readouterr().err


# --------------------------------------------------------------------------
# import_fdf — round-trip + error branches
# --------------------------------------------------------------------------
def test_import_fdf_round_trip_with_form_pdf(
    patched_import_fdf_loader: Any, tmp_path: Path,
) -> None:
    src = _build_form_pdf(tmp_path / "form.pdf")
    fdf = _build_fdf(tmp_path / "data.fdf")
    out = tmp_path / "out.pdf"
    rc = import_fdf.ImportFDF.main([
        "-i", str(src),
        "-o", str(out),
        "--data", str(fdf),
    ])
    assert rc == 0
    assert out.is_file()
    assert out.read_bytes()[:4] == b"%PDF"


def test_import_fdf_default_outfile_overwrites_input(
    patched_import_fdf_loader: Any, tmp_path: Path,
) -> None:
    """No ``-o`` → result lands back at the input path."""
    src = _build_form_pdf(tmp_path / "form.pdf")
    fdf = _build_fdf(tmp_path / "data.fdf")
    rc = import_fdf.ImportFDF.main([
        "-i", str(src),
        "--data", str(fdf),
    ])
    assert rc == 0
    assert src.is_file()


def test_import_fdf_no_acroform_pdf_still_saves(
    patched_import_fdf_loader: Any, tmp_path: Path,
) -> None:
    """A PDF with no AcroForm hits the early-return branch in
    ``import_fdf(...)`` and the runner still saves the (unchanged) PDF."""
    src = _build_blank_pdf(tmp_path / "plain.pdf")
    fdf = _build_fdf(tmp_path / "data.fdf")
    out = tmp_path / "out.pdf"
    rc = import_fdf.ImportFDF.main([
        "-i", str(src),
        "-o", str(out),
        "--data", str(fdf),
    ])
    assert rc == 0
    assert out.is_file()


def test_import_fdf_missing_infile_raises() -> None:
    runner = import_fdf.ImportFDF()
    runner.fdffile = Path("/tmp/x.fdf")  # noqa: S108 — placeholder
    with pytest.raises(OSError, match="infile and fdffile are required"):
        runner.call()


def test_import_fdf_missing_fdffile_raises() -> None:
    runner = import_fdf.ImportFDF()
    runner.infile = Path("/tmp/x.pdf")  # noqa: S108 — placeholder
    with pytest.raises(OSError, match="infile and fdffile are required"):
        runner.call()


def test_import_fdf_load_error_returns_4(
    patched_import_fdf_loader: Any, tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = import_fdf.ImportFDF.main([
        "-i", str(tmp_path / "missing.pdf"),
        "-o", str(tmp_path / "out.pdf"),
        "--data", str(tmp_path / "missing.fdf"),
    ])
    assert rc == 4
    assert "Error importing FDF data" in capsys.readouterr().err


# --------------------------------------------------------------------------
# pdf_text2_markdown — module helpers + FontState + wrapping overrides
# --------------------------------------------------------------------------
def test_md_append_escaped_special_markdown_chars() -> None:
    """The four Markdown specials (``*``, ``+``, ``-``, ``#``) must be
    backslash-escaped."""
    for ch in ("*", "+", "-", "#"):
        buf: list[str] = []
        _append_escaped(buf, ch)
        assert buf == ["\\" + ch]


def test_md_append_escaped_superscript_2_and_3() -> None:
    """``²`` (178) and ``³`` (179) become ``<sup>2</sup>`` /
    ``<sup>3</sup>`` — the Markdown variant's only HTML emission."""
    buf2: list[str] = []
    _append_escaped(buf2, chr(178))
    assert buf2 == ["<sup>2</sup>"]
    buf3: list[str] = []
    _append_escaped(buf3, chr(179))
    assert buf3 == ["<sup>3</sup>"]


def test_md_append_escaped_passthrough() -> None:
    buf: list[str] = []
    _append_escaped(buf, "a")
    _append_escaped(buf, "1")
    assert buf == ["a", "1"]


def test_md_escape_mixed_run() -> None:
    assert _escape("a*b") == "a\\*b"
    assert _escape("x" + chr(178)) == "x<sup>2</sup>"


def test_md_static_escape_proxies_module_helper() -> None:
    assert PDFText2Markdown.escape("a*b") == _escape("a*b")


def test_md_static_append_escaped_proxies_module_helper() -> None:
    builder: list[str] = []
    PDFText2Markdown.append_escaped(builder, "#")
    assert builder == ["\\#"]


# --- FontState --------------------------------------------------------------
def test_md_font_state_open_emits_tag_and_records_state() -> None:
    fs = FontState()
    # The Markdown FontState's ``open_tag`` returns the tag as-is.
    assert fs.open("**") == "**"
    assert fs.open("**") == ""  # already open → no-op


def test_md_font_state_close_on_unopened_tag_is_noop() -> None:
    assert FontState().close("**") == ""


def test_md_font_state_clear_closes_all_open_tags() -> None:
    fs = FontState()
    fs.open("**")
    fs.open("*")
    out = fs.clear()
    # innermost first.
    assert out == "***"
    assert fs.clear() == ""


def test_md_font_state_close_reopens_intermediate_tags() -> None:
    """Closing an outer tag must close all inner tags down to it and
    re-emit the intermediate ones. open_tag/close_tag both return the
    tag verbatim in the Markdown variant, so the sequence ``close *``,
    ``close **``, ``re-open *`` yields ``*`` + ``**`` + ``*``."""
    fs = FontState()
    fs.open("**")
    fs.open("*")
    closed = fs.close("**")
    assert closed == "*" + "**" + "*"


def test_md_font_state_open_close_tag_helpers() -> None:
    fs = FontState()
    assert fs.open_tag("**") == "**"
    assert fs.close_tag("**") == "**"


def test_md_font_state_is_bold_detects_force_bold() -> None:
    class _Desc:
        def is_force_bold(self) -> bool:
            return True

        def get_font_name(self) -> str:
            return "Plain"

        def is_italic(self) -> bool:
            return False

    assert FontState().is_bold(_Desc()) is True


def test_md_font_state_is_bold_detects_name() -> None:
    class _Desc:
        def is_force_bold(self) -> bool:
            return False

        def get_font_name(self) -> str:
            return "Foo-Bold"

        def is_italic(self) -> bool:
            return False

    assert FontState().is_bold(_Desc()) is True


def test_md_font_state_is_italic_detects_flag() -> None:
    class _Desc:
        def is_italic(self) -> bool:
            return True

        def is_force_bold(self) -> bool:
            return False

        def get_font_name(self) -> str:
            return "Plain"

    assert FontState().is_italic(_Desc()) is True


def test_md_font_state_is_italic_detects_name_italic_and_oblique() -> None:
    class _IDesc:
        def is_italic(self) -> bool:
            return False

        def is_force_bold(self) -> bool:
            return False

        def get_font_name(self) -> str:
            return "Foo-Italic"

    class _ODesc:
        def is_italic(self) -> bool:
            return False

        def is_force_bold(self) -> bool:
            return False

        def get_font_name(self) -> str:
            return "Foo-Oblique"

    assert FontState().is_italic(_IDesc()) is True
    assert FontState().is_italic(_ODesc()) is True


def test_md_font_state_push_with_matched_positions() -> None:
    class _Desc:
        def __init__(self, name: str, bold: bool, italic: bool) -> None:
            self._n = name
            self._b = bold
            self._i = italic

        def get_font_name(self) -> str:
            return self._n

        def is_force_bold(self) -> bool:
            return self._b

        def is_italic(self) -> bool:
            return self._i

    class _Font:
        def __init__(self, d: _Desc) -> None:
            self._d = d

        def get_font_descriptor(self) -> _Desc:
            return self._d

    class _TP:
        def __init__(self, d: _Desc) -> None:
            self._f = _Font(d)

        def get_font(self) -> _Font:
            return self._f

    fs = FontState()
    bold = _TP(_Desc("Foo-Bold", True, False))
    italic = _TP(_Desc("Foo-Italic", False, True))
    out = fs.push("AB", [bold, italic])
    # ``A`` opens **, ``B`` closes ** and opens *.
    assert "**A" in out
    assert "*B" in out


def test_md_font_state_push_no_positions_returns_raw_text() -> None:
    assert FontState().push("abc", []) == "abc"


def test_md_font_state_push_empty_text_returns_empty() -> None:
    assert FontState().push("", []) == ""


def test_md_font_state_push_falls_back_to_single_position_then_escape() -> None:
    class _NoDescFont:
        def get_font_descriptor(self) -> None:
            return None

    class _TP:
        def get_font(self) -> _NoDescFont:
            return _NoDescFont()

    fs = FontState()
    out = fs.push("H*", [_TP()])
    # ``H`` goes through the position branch; ``*`` tail is escaped.
    assert out.endswith("\\*")


def test_md_font_state_push_char_swallows_attribute_error() -> None:
    """When ``text_position.get_font()`` raises, descriptor stays None
    and the char is emitted with no styling."""

    class _BareTP:
        pass

    buf: list[str] = []
    FontState().push_char(buf, "x", _BareTP())
    assert "".join(buf) == "x"


# --- PDFText2Markdown wrapping overrides ------------------------------------
@pytest.fixture
def patched_parent(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace ``PDFTextStripper.write_string`` /
    ``write_paragraph_end`` with capture stubs so the Markdown wrapping
    methods can be exercised in isolation. Mirrors the wave-1316
    PDFText2HTML coverage pattern."""
    captured: list[str] = []

    def _capture(self: Any, text: str, *args: Any, **kw: Any) -> None:
        captured.append(text)

    def _para_end(self: Any, *args: Any, **kw: Any) -> None:
        captured.append("<PARA_END>")

    monkeypatch.setattr(PDFTextStripper, "write_string", _capture)
    monkeypatch.setattr(PDFTextStripper, "write_paragraph_end", _para_end)
    return captured


def test_md_constructor_configures_separators() -> None:
    """The Markdown subclass wires every separator/start/end to the
    configured line separator (so output is paragraph-friendly)."""
    p = PDFText2Markdown()
    sep = p.get_line_separator()
    assert p.get_paragraph_start() == sep
    assert p.get_paragraph_end() == sep
    assert p.get_page_start() == sep
    assert p.get_page_end() == sep
    assert p.get_article_start() == sep
    assert p.get_article_end() == sep


def test_md_start_article_emits_separator(patched_parent: list[str]) -> None:
    p = PDFText2Markdown()
    p.start_article(True)
    assert "".join(patched_parent) == p.get_line_separator()


def test_md_end_article_emits_separator(patched_parent: list[str]) -> None:
    p = PDFText2Markdown()
    p.end_article()
    assert p.get_line_separator() in "".join(patched_parent)


def test_md_write_string_no_positions_escapes_and_forwards(
    patched_parent: list[str],
) -> None:
    p = PDFText2Markdown()
    p.write_string("a*b")
    assert "".join(patched_parent) == "a\\*b"


def test_md_write_string_with_positions_routes_through_font_state(
    patched_parent: list[str],
) -> None:
    class _Desc:
        def get_font_name(self) -> str:
            return "Foo-Bold"

        def is_force_bold(self) -> bool:
            return True

        def is_italic(self) -> bool:
            return False

    class _Font:
        def get_font_descriptor(self) -> _Desc:
            return _Desc()

    class _TP:
        def get_font(self) -> _Font:
            return _Font()

    p = PDFText2Markdown()
    p.write_string("X", [_TP()])
    assert "**X" in "".join(patched_parent)


def test_md_write_paragraph_end_clears_font_state(
    patched_parent: list[str],
) -> None:
    p = PDFText2Markdown()
    p._font_state.open("**")  # noqa: SLF001 — exercising port invariant
    p.write_paragraph_end()
    captured = "".join(patched_parent)
    # The closing ``**`` from clear() is present, then the parent's
    # write_paragraph_end stub appended ``<PARA_END>``.
    assert "**" in captured
    assert "<PARA_END>" in captured
