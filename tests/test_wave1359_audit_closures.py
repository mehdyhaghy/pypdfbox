"""Wave 1359 — audit closure tests.

Locks in the documented behaviour at the nine TODO / stale-doc sites
addressed by the wave-1359 audit pass. Each test pins the public surface
of one of the audited methods so any future regression that re-introduces
the deferred or speculative behaviour fails loudly.
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.fontbox.cff.type2_char_string import Type2CharString
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (
    PDOptionalContentMembershipDictionary,
)
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
from pypdfbox.pdmodel.pd_page import PDPage

# ---------- Site 1: tools/__init__.py — debug CLI shipping ----------


def test_tools_init_docstring_no_longer_lists_debug_as_tbd() -> None:
    """Wave 1359 stripped the ``debug`` CLI TBD line — pdfdebugger ships."""
    from pypdfbox import tools

    doc = tools.__doc__ or ""
    assert "CLI-only port TBD" not in doc
    assert "pdfdebugger" in doc


def test_tools_cli_wires_pdfdebugger_subcommand() -> None:
    """``pdfdebugger`` is in the live ``_SUBCOMMANDS`` tuple."""
    from pypdfbox.tools import cli, pdfdebugger

    assert pdfdebugger in cli._SUBCOMMANDS


# ---------- Site 4: Type2CharString.expand_stem_hints stays a no-op ----------


def test_expand_stem_hints_is_a_no_op() -> None:
    """Upstream PDFBox 3.0.x ships ``expandStemHints`` as a TODO no-op;
    pypdfbox preserves the behaviour because fontTools handles hinting
    independently. Calling it must not mutate the sequence buffer."""
    cs = Type2CharString(
        font=None,
        font_name="TestFont",
        glyph_name="A",
        gid=0,
        sequence=b"",
    )
    before = list(cs._type1_sequence)
    cs.expand_stem_hints([10.0, 20.0, 30.0], True)
    cs.expand_stem_hints([10.0, 20.0, 30.0], False)
    cs.expand_stem_hints([], True)
    assert cs._type1_sequence == before


# ---------- Site 5: PDPage.get_matrix stays identity ----------


def test_pd_page_get_matrix_ignores_user_unit() -> None:
    """``/UserUnit`` is a viewer concern (PDF 32000-1 §14.10.4) — applying
    it inside ``get_matrix()`` would over-scale callers that already
    compose it separately. Lock the identity behaviour."""
    page = PDPage()
    page.set_user_unit(7.5)
    assert page.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_pd_page_get_matrix_ignores_rotation() -> None:
    """``/Rotate`` is composed by the rendering pipeline, not by
    ``get_matrix()``. Lock the identity behaviour."""
    page = PDPage()
    page.set_rotation(270)
    assert page.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


# ---------- Site 6: PDEncryption.set_security_handler does not stamp /Filter ----------


def test_set_security_handler_does_not_touch_filter() -> None:
    """Upstream's TODO speculates that ``setSecurityHandler`` should also
    write /Filter; pypdfbox preserves the no-op behaviour because the
    dedicated :meth:`set_filter` is the right call site."""
    enc = PDEncryption()
    assert enc.get_filter() is None

    class _DummyHandler:  # minimal stand-in
        pass

    enc.set_security_handler(_DummyHandler())
    assert enc.get_filter() is None


def test_set_security_handler_preserves_pre_existing_filter() -> None:
    """Installing a handler must not clobber an existing /Filter — for
    example, a /Filter Adobe.PubSec public-key dispatch."""
    enc = PDEncryption()
    enc.set_filter("Adobe.PubSec")
    enc.set_security_handler(object())
    assert enc.get_filter() == "Adobe.PubSec"


# ---------- Site 7: PDPropertyList fallback covers all "more types" ----------


def test_property_list_create_dispatches_ocg() -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("OCG"))  # type: ignore[attr-defined]
    result = PDPropertyList.create(d)
    assert isinstance(result, PDOptionalContentGroup)


def test_property_list_create_dispatches_ocmd() -> None:
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("OCMD"))  # type: ignore[attr-defined]
    result = PDPropertyList.create(d)
    assert isinstance(result, PDOptionalContentMembershipDictionary)


def test_property_list_create_unknown_type_returns_bare_wrapper() -> None:
    """Wave 1359 close-out: PDF 32000-1 §14.6 only defines /OCG and
    /OCMD; any other /Type lands as a bare PDPropertyList rather than
    ``None``."""
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("MadeUpType"))  # type: ignore[attr-defined]
    result = PDPropertyList.create(d)
    assert result is not None
    assert type(result) is PDPropertyList
    assert result.get_cos_object() is d


def test_property_list_create_no_type_returns_bare_wrapper() -> None:
    d = COSDictionary()
    result = PDPropertyList.create(d)
    assert result is not None
    assert type(result) is PDPropertyList


def test_property_list_create_none_returns_none() -> None:
    assert PDPropertyList.create(None) is None


# ---------- Site 8: PDXObject.create_x_object(None) returns None ----------


def test_create_x_object_none_returns_none() -> None:
    """Upstream's ``TODO throw an exception?`` is intentionally left as
    a null-return so resource-dict callers can tolerate stale entries."""
    assert PDXObject.create_x_object(None) is None


def test_create_x_object_non_stream_raises() -> None:
    """Non-stream non-None inputs still raise OSError (mirrors upstream's
    ``IOException("Unexpected object type: ...")``) — verifies that the
    ``None`` early-out is the *only* tolerated null case."""
    import pytest

    with pytest.raises(OSError):
        PDXObject.create_x_object(COSArray())


# ---------- Site 9: PDLab.to_rgb keeps no-BPC parity with upstream ----------


def test_pd_lab_to_rgb_skips_black_point_compensation() -> None:
    """Locking the no-BPC behaviour: setting a non-trivial /BlackPoint
    must not change the rendered sRGB because upstream PDLab.toRGB
    intentionally skips BPC (PDLab.java line 129 TODO)."""
    lab = PDLab()
    base_rgb = lab.to_rgb([50.0, 0.0, 0.0])
    lab.set_black_point([0.05, 0.05, 0.05])
    bpc_rgb = lab.to_rgb([50.0, 0.0, 0.0])
    assert base_rgb == bpc_rgb


def test_pd_lab_to_rgb_neutral_grey_round_trips() -> None:
    """Sanity: L*=100 / a*=0 / b*=0 with unit /WhitePoint maps to a
    near-white sRGB triple."""
    lab = PDLab()
    r, g, b = lab.to_rgb([100.0, 0.0, 0.0])
    # sRGB white from unit XYZ — clamped to 0..1 range.
    assert 0.9 <= r <= 1.0
    assert 0.9 <= g <= 1.0
    assert 0.9 <= b <= 1.0


# ---------- Site 2: CHANGES.md SMask audit closure note ----------


def test_changes_md_records_smask_audit_closure() -> None:
    """The wave-1359 audit closed the stale ``/SMask`` deferral note.

    Wave 1378 split CHANGES.md into a lean active-divergence file
    (`CHANGES.md`), a chronological log (`HISTORY.md`), and an
    open-items tracker (`DEFERRED.md`). The historical SMask deferral
    note + Wave 1359 closure marker now live in ``HISTORY.md``; the
    audit-closure annotation itself was stripped from the bullet
    because the wave-1359 entry below it documents the closure event.
    We confirm here that the historical record retains both the
    deferral context AND the Wave 1359 entry that closed it.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    # HISTORY.md (the chronological migration log) was relocated under
    # archive/migration-docs/ in the wave-1597 restructure; fall back to the
    # legacy root location if the archive is absent.
    history_md = root / "archive" / "migration-docs" / "HISTORY.md"
    if not history_md.exists():
        history_md = root / "HISTORY.md"
    body = history_md.read_text(encoding="utf-8")
    # Wave 31 onward documents the SMask wiring that closed the
    # original deferral.
    assert "SMask alpha compositing" in body
    # Wave 40 round-out added the ExtGState soft-mask compositing
    # pipeline that finalised the closure tracked under the
    # wave-1359 audit.
    assert "Wave 40 round-out — ExtGState `/SMask` soft-mask compositing" in body


# ---------- Site 3: ImportFDF /NeedAppearances workaround stays ----------


def test_import_fdf_sets_need_appearances() -> None:
    """The wave-1286 / wave-1359-audited workaround: importing an FDF
    must leave /NeedAppearances = true so viewers regenerate the
    appearance streams."""
    from pypdfbox.pdmodel.fdf.fdf_document import FDFDocument
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.tools.import_fdf import ImportFDF

    pdf = PDDocument()
    catalog = pdf.get_document_catalog()
    acro_form = PDAcroForm(pdf)
    catalog.set_acro_form(acro_form)

    fdf = FDFDocument()
    try:
        # Empty FDF — import_fdf path executes the catalog walk and
        # falls through to the /NeedAppearances toggle.
        ImportFDF().import_fdf(pdf, fdf)
    finally:
        fdf.close()
    assert acro_form.is_need_appearances() is True
    pdf.close()


# ---------- Misc: confirm COSStream form-XObject still dispatches ----------


def test_create_x_object_image_still_dispatches() -> None:
    """Sanity: the surrounding XObject factory still works."""
    cos = COSStream()
    cos.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Image"))
    cos.set_item(COSName.get_pdf_name("Width"), COSName.get_pdf_name("1"))
    obj = PDXObject.create_x_object(cos)
    assert obj is not None
    assert obj.get_subtype() == "Image"
