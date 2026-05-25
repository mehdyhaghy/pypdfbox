"""Wave 1399 — close residual partial branches on ``PDAcroForm``.

Targets the 7 partial arrows surviving after wave 1396:

* 531->526 — ``get_calc_order`` with a /CO entry that
  :class:`PDFieldFactory` cannot build (returns ``None``) skips the
  append and continues the loop.
* 609->608 — ``refresh_appearances`` skips a non-:class:`PDTerminalField`
  entry in the input list (loop ``continue``-equivalent).
* 640->635 — ``import_fdf`` whose FDF carries a field name absent from
  the form falls through to the next field.
* 698->700 — ``export_fdf`` against a document object whose
  ``get_document`` attribute is not callable.
* 702->705 — ``export_fdf`` when the COSDocument's ``get_document_id``
  returns ``None``.
* 854->865 — ``flatten(fields=...)`` when /Fields is not a COSArray.
* 951->958 — ``_select_appearance_stream`` when /AP/N is neither
  COSStream nor COSDictionary.
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDNonTerminalField


def _num_array(*values: float) -> COSArray:
    return COSArray([COSFloat(v) for v in values])


# ---------- 531->526 — get_calc_order skips an unbuildable /CO entry --------


def test_get_calc_order_skips_entries_pdfieldfactory_cannot_build() -> None:
    """``PDFieldFactory.create_field`` returns ``None`` for a dictionary
    with no recognisable /FT. The for-loop must skip that None and
    continue scanning the rest of the /CO array. Closes False arm at
    line 531."""
    form = PDAcroForm()

    # Two entries: one valid text-field dict, one bare dict with no /FT.
    bogus = COSDictionary()  # no /FT → factory returns None
    valid = COSDictionary()
    valid.set_item(COSName.get_pdf_name("FT"), COSName.get_pdf_name("Tx"))
    valid.set_item(COSName.get_pdf_name("T"), COSName.get_pdf_name("good"))

    co = COSArray()
    co.add(bogus)
    co.add(valid)
    form.get_cos_object().set_item(COSName.get_pdf_name("CO"), co)

    # Walk completes without raising; the valid entry surfaces, the bogus
    # one is silently dropped.
    out = form.get_calc_order()
    assert len(out) == 1


# ---------- 609->608 — refresh_appearances skips non-terminal field ---------


def test_refresh_appearances_with_non_terminal_field_in_list_skips_it() -> None:
    """Passing a non-:class:`PDTerminalField` in the ``fields=`` argument
    must not raise — the isinstance guard at L609 short-circuits. Closes
    the False arm of that guard."""
    form = PDAcroForm()
    non_term = PDNonTerminalField(form)
    non_term.set_partial_name("group")

    # Must not raise — the guard at L609 is False for the non-terminal.
    form.refresh_appearances(fields=[non_term])


# ---------- 640->635 — import_fdf skips fields absent from the form ---------


def test_import_fdf_skips_field_names_absent_from_form() -> None:
    """An FDF field whose partial name doesn't resolve in the form is
    silently skipped (closes False arm of the
    ``doc_field is not None`` guard at L640)."""
    from pypdfbox.pdmodel.fdf.fdf_dictionary import FDFDictionary
    from pypdfbox.pdmodel.fdf.fdf_document import FDFDocument
    from pypdfbox.pdmodel.fdf.fdf_field import FDFField

    form = PDAcroForm()  # empty form — no fields at all
    fdf = FDFDocument()
    fdf_dict = FDFDictionary()
    fdf.get_catalog().set_fdf(fdf_dict)

    stray = FDFField()
    stray.set_partial_field_name("ghost")
    fdf_dict.set_fields([stray])

    # Must not raise — empty form has no "ghost" field.
    form.import_fdf(fdf)


# ---------- 698->700 — export_fdf with document lacking callable get_document


def test_export_fdf_document_get_document_not_callable_skips_id_copy() -> None:
    """A document whose ``get_document`` attribute is *not* callable
    skips the cos_doc lookup. Closes False arm at L698."""

    class _DocNonCallableGetter:
        # Non-callable attribute named get_document.
        get_document: int = 0  # type: ignore[assignment]

    form = PDAcroForm(document=_DocNonCallableGetter())  # type: ignore[arg-type]
    fdf = form.export_fdf()
    # Sanity: export still produced an FDF document.
    assert fdf is not None


# ---------- 702->705 — export_fdf cos_doc.get_document_id returns None ------


def test_export_fdf_cos_doc_returns_none_doc_id_skips_set_id() -> None:
    """When the COSDocument's ``get_document_id`` returns ``None``,
    the FDF dict's /ID is not set. Closes False arm at L702."""

    class _CosDocNoneId:
        def get_document_id(self) -> bytes | None:
            return None

    class _DocReturnsCosWithNoneId:
        def get_document(self) -> _CosDocNoneId:
            return _CosDocNoneId()

    form = PDAcroForm(document=_DocReturnsCosWithNoneId())  # type: ignore[arg-type]
    fdf = form.export_fdf()
    # Sanity: export completed (no exception) — and /ID is absent on FDF.
    fdf_dict = fdf.get_catalog().get_fdf()
    assert fdf_dict.get_id() is None


# ---------- 854->865 — flatten(fields=...) when /Fields is not a COSArray ---


def test_flatten_fields_when_fields_entry_is_not_array_completes_without_raising() -> None:
    """When the AcroForm's /Fields entry is not a COSArray (e.g. removed
    or replaced with a dictionary), ``flatten(fields=...)`` still runs
    to completion — the L854 isinstance guard is False so the cleanup
    loop is skipped. Closes that False arm."""
    from pypdfbox.pdmodel.interactive.form.pd_field_factory import PDFieldFactory

    form = PDAcroForm()
    # Build a real terminal text field, add it to the form so flatten
    # has something to walk.
    field_dict = COSDictionary()
    field_dict.set_item(COSName.get_pdf_name("FT"), COSName.get_pdf_name("Tx"))
    field_dict.set_item(COSName.get_pdf_name("T"), COSName.get_pdf_name("t1"))
    field = PDFieldFactory.create_field(form, field_dict, None)
    assert field is not None
    fields_arr = COSArray()
    fields_arr.add(field_dict)
    form.get_cos_object().set_item(COSName.get_pdf_name("Fields"), fields_arr)

    # Sabotage /Fields — replace the COSArray with a COSDictionary so
    # the isinstance(arr, COSArray) at L854 is False.
    form.get_cos_object().set_item(
        COSName.get_pdf_name("Fields"), COSDictionary()
    )

    # flatten(fields=[field]) is the "not flatten_all" path that reaches
    # the L853-863 branch — must not raise even though /Fields is a dict.
    form.flatten(fields=[field], refresh_appearances=False)


# ---------- 951->958 — _select_appearance_stream when /AP/N is bogus --------


def test_select_appearance_stream_returns_none_when_ap_n_is_array() -> None:
    """When /AP/N is neither COSStream nor COSDictionary (e.g. a stray
    COSArray written by a broken producer), the helper returns None.
    Closes False arm of the COSDictionary isinstance check at L951."""
    form = PDAcroForm()
    widget = COSDictionary()
    widget.set_item(COSName.get_pdf_name("Rect"), _num_array(0.0, 0.0, 10.0, 10.0))
    ap = COSDictionary()
    # /AP/N is an ARRAY — neither stream nor dict.
    ap.set_item(COSName.get_pdf_name("N"), _num_array(1.0, 2.0))
    widget.set_item(COSName.get_pdf_name("AP"), ap)

    result = form._select_appearance_stream(widget)  # noqa: SLF001
    assert result is None


def test_select_appearance_stream_returns_stream_for_simple_normal_state() -> None:
    """Sanity check that the L949 True arm still works after the L951
    False-arm coverage is added."""
    form = PDAcroForm()
    widget = COSDictionary()
    stream = COSStream()
    stream.set_item("BBox", _num_array(0.0, 0.0, 10.0, 10.0))
    ap = COSDictionary()
    ap.set_item(COSName.get_pdf_name("N"), stream)
    widget.set_item(COSName.get_pdf_name("AP"), ap)

    assert form._select_appearance_stream(widget) is stream  # noqa: SLF001
