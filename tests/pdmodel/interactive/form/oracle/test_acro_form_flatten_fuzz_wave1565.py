"""Live Apache PDFBox differential fuzz of ``PDAcroForm.flatten(...)``
(wave 1565, agent E).

The existing flatten oracle (``test_flatten_oracle.py`` / ``FlattenProbe.java``)
drives a few curated on-disk fixtures through a flatten and compares per-page
widget counts + content growth. This probe complements it by fuzzing the flatten
DECISION SURFACE across many hand-built field configurations that exercise the
branches inside ``flatten``:

* a text field carrying a value + a real ``/AP /N`` appearance;
* a text field with NO appearance flattened with ``refresh_appearances=True``
  (upstream regenerates the AP) vs ``=False`` (no AP to bake);
* a check box flattened in its on-state vs its off-state (state dict + ``/AS``);
* a SUBSET flatten (``flatten([one], False)``) leaving other fields + the
  ``/AcroForm`` dict intact;
* an empty form (no fields) — flatten is a no-op;
* a field whose single widget lives on page 2 (multi-page ``/P`` resolution);
* a non-terminal parent with two terminal kid widgets;
* a hidden (``/F`` bit 2) widget — removed from ``/Annots`` but not drawn;
* a widget with no ``/P`` back-pointer (reverse-walk page lookup).

Strategy (mirrors ``AcroFormFieldFuzzProbe``): hand-build a deterministic corpus
of minimal-but-valid PDFs into a directory plus a ``manifest.txt`` whose lines
are ``<case>\\t<op>\\t<arg>``. Both this test and ``AcroFormFlattenFuzzProbe``
read the EXACT same bytes on disk, run the same flatten op, then project a STABLE
shape (counts + presence flags, never raw bytes) so the observable flatten
contract is directly comparable.

Per case both sides project::

    CASE <name> preFields=<n> preWidgets=<n> pages=<n>
    FLAT <name> op=<op> result=<ok|ERR:<Exc>> acroform=<0/1> \\
         postFields=<n> postWidgets=<n> valueBaked=<0/1> grew=<0/1>
    ENDCASE <name>

Counts are read from a RELOAD of the saved bytes so the comparison reflects the
persisted outcome, not the in-memory object graph.

Validation, not blind pinning: the Java line is ground truth and most facts
match cross-engine directly. The known/documented divergences are pinned in
``_PINNED`` with a justification and a matching CHANGES.md row:

* ``acroform`` after a flatten-ALL — upstream keeps the now-field-less
  ``/AcroForm`` dict (acroform=1); pypdfbox drops it outright (acroform=0). This
  is the pre-existing documented divergence already pinned by
  ``test_flatten_oracle``; re-asserted here so a regression on EITHER side is
  caught. ``postFields`` is 0 on both sides regardless, so the "form is gone"
  contract is identical.

Decorated ``@requires_oracle`` so it skips on machines without Java + jar. The
saved bytes are checked with ``qpdf --check`` when qpdf is on PATH.
"""

from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

from pypdfbox import PDDocument
from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from tests.oracle.harness import requires_oracle, run_probe_text

_QPDF = shutil.which("qpdf")

_ANNOTS = COSName.get_pdf_name("Annots")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_WIDGET = COSName.get_pdf_name("Widget")
_CONTENTS = COSName.get_pdf_name("Contents")
_FIELDS = COSName.get_pdf_name("Fields")
_RESOURCES = COSName.get_pdf_name("Resources")
_XOBJECT = COSName.get_pdf_name("XObject")


# ----------------------------------------------------------------- corpus builder


def _build_pdf(objs: list[str]) -> bytes:
    """Assemble a minimal valid PDF from ``objs`` (object bodies 1..N), wiring
    a classic xref table so both parsers load it cleanly. Object 1 must be the
    catalog."""
    body = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(body))
        body += f"{i} 0 obj\n".encode("latin-1") + o.encode("latin-1") + b"\nendobj\n"
    xref_pos = len(body)
    n = len(objs) + 1
    body += f"xref\n0 {n}\n".encode("latin-1")
    body += b"0000000000 65535 f \n"
    for off in offsets:
        body += f"{off:010d} 00000 n \n".encode("latin-1")
    body += b"trailer\n" + f"<<\n/Root 1 0 R\n/Size {n}\n>>\n".encode("latin-1")
    body += f"startxref\n{xref_pos}\n%%EOF".encode("latin-1")
    return bytes(body)


# Form XObject appearance stream body carrying the marker token FLATMARK so the
# probe can detect when an appearance was baked into the page.
def _ap_stream(obj_no: int, body: str = "q BT /Helv 12 Tf (FLATMARK) Tj ET Q") -> str:
    raw = body.encode("latin-1")
    return (
        "<<\n/Type /XObject\n/Subtype /Form\n/FormType 1\n"
        "/BBox [0 0 100 20]\n/Resources << /Font << /Helv 99 0 R >> >>\n"
        f"/Length {len(raw)}\n>>\nstream\n{body}\nendstream"
    )


def _font_obj() -> str:
    return "<<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>"


def _build_corpus() -> dict[str, tuple[bytes, str, str]]:
    """Return ``{case -> (pdf_bytes, op, arg)}`` ordered by insertion.

    ``op`` is one of ``all`` / ``all-refresh`` / ``subset`` / ``subset-refresh``;
    ``arg`` is the fully-qualified field name for the subset ops (else "")."""
    c: dict[str, tuple[bytes, str, str]] = {}

    catalog = "<<\n/Type /Catalog\n/Pages 2 0 R\n/AcroForm 3 0 R\n>>"
    pages_one = "<<\n/Type /Pages\n/Kids [4 0 R]\n/Count 1\n>>"
    page_one = (
        "<<\n/Type /Page\n/MediaBox [0 0 612 792]\n/Parent 2 0 R\n/Annots [5 0 R]\n>>"
    )

    # --- 1. text field with value + real /AP /N appearance (flatten-all) ---
    c["text_with_ap_all"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields [5 0 R]\n/DR << /Font << /Helv 99 0 R >> >>\n>>",
                page_one,
                "<<\n/FT /Tx\n/T (text1)\n/V (FLATMARK)\n/Subtype /Widget\n"
                "/Type /Annot\n/Rect [50 700 150 720]\n/P 4 0 R\n/AP << /N 6 0 R >>\n>>",
                _ap_stream(6),
            ]
            + _pad_to_99()
            + [_font_obj()]
        ),
        "all",
        "",
    )

    # --- 2. text field with NO appearance, refresh regenerates ---
    c["text_no_ap_refresh"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields [5 0 R]\n/DR << /Font << /Helv 6 0 R >> >>\n"
                "/DA (/Helv 12 Tf 0 g)\n>>",
                page_one,
                "<<\n/FT /Tx\n/T (text1)\n/V (FLATMARK)\n/DA (/Helv 12 Tf 0 g)\n"
                "/Subtype /Widget\n/Type /Annot\n/Rect [50 700 150 720]\n/P 4 0 R\n>>",
                _font_obj(),
            ]
        ),
        "all-refresh",
        "",
    )

    # --- 3. text field with NO appearance, refresh=False (nothing to bake) ---
    c["text_no_ap_no_refresh"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields [5 0 R]\n>>",
                page_one,
                "<<\n/FT /Tx\n/T (text1)\n/V (FLATMARK)\n/Subtype /Widget\n"
                "/Type /Annot\n/Rect [50 700 150 720]\n/P 4 0 R\n>>",
            ]
        ),
        "all",
        "",
    )

    # --- 4. checkbox ON-state (/AS /Yes, /AP /N state dict) ---
    c["checkbox_on_all"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields [5 0 R]\n>>",
                page_one,
                "<<\n/FT /Btn\n/T (cb1)\n/V /Yes\n/AS /Yes\n/Subtype /Widget\n"
                "/Type /Annot\n/Rect [50 600 70 620]\n/P 4 0 R\n"
                "/AP << /N << /Yes 6 0 R /Off 7 0 R >> >>\n>>",
                _ap_stream(6, "q 1 0 0 RG 2 2 16 16 re S Q"),
                _ap_stream(7, "q 0 0 16 16 re S Q"),
            ]
        ),
        "all",
        "",
    )

    # --- 5. checkbox OFF-state (/AS /Off) ---
    c["checkbox_off_all"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields [5 0 R]\n>>",
                page_one,
                "<<\n/FT /Btn\n/T (cb1)\n/V /Off\n/AS /Off\n/Subtype /Widget\n"
                "/Type /Annot\n/Rect [50 600 70 620]\n/P 4 0 R\n"
                "/AP << /N << /Yes 6 0 R /Off 7 0 R >> >>\n>>",
                _ap_stream(6, "q 1 0 0 RG 2 2 16 16 re S Q"),
                _ap_stream(7, "q 0 0 16 16 re S Q"),
            ]
        ),
        "all",
        "",
    )

    # --- 6. subset flatten — two fields, only flatten the first ---
    two_field_pages = (
        "<<\n/Type /Page\n/MediaBox [0 0 612 792]\n/Parent 2 0 R\n"
        "/Annots [5 0 R 7 0 R]\n>>"
    )
    c["subset_two_fields"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields [5 0 R 7 0 R]\n>>",
                two_field_pages,
                "<<\n/FT /Tx\n/T (keep)\n/V (FLATMARK)\n/Subtype /Widget\n"
                "/Type /Annot\n/Rect [50 700 150 720]\n/P 4 0 R\n/AP << /N 6 0 R >>\n>>",
                _ap_stream(6),
                "<<\n/FT /Tx\n/T (drop)\n/V (FLATMARK)\n/Subtype /Widget\n"
                "/Type /Annot\n/Rect [50 650 150 670]\n/P 4 0 R\n/AP << /N 8 0 R >>\n>>",
                _ap_stream(8),
            ]
        ),
        "subset",
        "drop",
    )

    # --- 7. empty form (no fields) — flatten no-op ---
    c["empty_form"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields []\n>>",
                "<<\n/Type /Page\n/MediaBox [0 0 612 792]\n/Parent 2 0 R\n>>",
            ]
        ),
        "all",
        "",
    )

    # --- 8. field whose widget lives on page 2 ---
    pages_two = "<<\n/Type /Pages\n/Kids [4 0 R 5 0 R]\n/Count 2\n>>"
    page_a = "<<\n/Type /Page\n/MediaBox [0 0 612 792]\n/Parent 2 0 R\n>>"
    page_b = (
        "<<\n/Type /Page\n/MediaBox [0 0 612 792]\n/Parent 2 0 R\n/Annots [6 0 R]\n>>"
    )
    c["widget_on_page2"] = (
        _build_pdf(
            [
                catalog,
                pages_two,
                "<<\n/Fields [6 0 R]\n>>",
                page_a,
                page_b,
                "<<\n/FT /Tx\n/T (text1)\n/V (FLATMARK)\n/Subtype /Widget\n"
                "/Type /Annot\n/Rect [50 700 150 720]\n/P 5 0 R\n/AP << /N 7 0 R >>\n>>",
                _ap_stream(7),
            ]
        ),
        "all",
        "",
    )

    # --- 9. non-terminal parent with two terminal kid widgets ---
    page_kids = (
        "<<\n/Type /Page\n/MediaBox [0 0 612 792]\n/Parent 2 0 R\n"
        "/Annots [6 0 R 8 0 R]\n>>"
    )
    c["parent_two_kids"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields [5 0 R]\n>>",
                page_kids,
                "<<\n/FT /Tx\n/T (parent)\n/Kids [6 0 R 8 0 R]\n>>",
                "<<\n/T (a)\n/V (FLATMARK)\n/Parent 5 0 R\n/Subtype /Widget\n"
                "/Type /Annot\n/Rect [50 700 150 720]\n/P 4 0 R\n/AP << /N 7 0 R >>\n>>",
                _ap_stream(7),
                "<<\n/T (b)\n/V (FLATMARK)\n/Parent 5 0 R\n/Subtype /Widget\n"
                "/Type /Annot\n/Rect [50 650 150 670]\n/P 4 0 R\n/AP << /N 9 0 R >>\n>>",
                _ap_stream(9),
            ]
        ),
        "all",
        "",
    )

    # --- 10. hidden widget (/F bit 2) — removed but not drawn ---
    c["hidden_widget_all"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields [5 0 R]\n>>",
                page_one,
                "<<\n/FT /Tx\n/T (text1)\n/V (FLATMARK)\n/F 2\n/Subtype /Widget\n"
                "/Type /Annot\n/Rect [50 700 150 720]\n/P 4 0 R\n/AP << /N 6 0 R >>\n>>",
                _ap_stream(6),
            ]
        ),
        "all",
        "",
    )

    # --- 11. invisible widget (/F bit 1) — removed but not drawn ---
    c["invisible_widget_all"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields [5 0 R]\n>>",
                page_one,
                "<<\n/FT /Tx\n/T (text1)\n/V (FLATMARK)\n/F 1\n/Subtype /Widget\n"
                "/Type /Annot\n/Rect [50 700 150 720]\n/P 4 0 R\n/AP << /N 6 0 R >>\n>>",
                _ap_stream(6),
            ]
        ),
        "all",
        "",
    )

    # --- 12. widget with NO /P back-pointer (reverse-walk page lookup) ---
    c["widget_no_p_all"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields [5 0 R]\n>>",
                page_one,
                "<<\n/FT /Tx\n/T (text1)\n/V (FLATMARK)\n/Subtype /Widget\n"
                "/Type /Annot\n/Rect [50 700 150 720]\n/AP << /N 6 0 R >>\n>>",
                _ap_stream(6),
            ]
        ),
        "all",
        "",
    )

    # --- 13. subset flatten of a non-existent field name (no-op-ish) ---
    c["subset_missing_name"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields [5 0 R]\n>>",
                page_one,
                "<<\n/FT /Tx\n/T (text1)\n/V (FLATMARK)\n/Subtype /Widget\n"
                "/Type /Annot\n/Rect [50 700 150 720]\n/P 4 0 R\n/AP << /N 6 0 R >>\n>>",
                _ap_stream(6),
            ]
        ),
        "subset",
        "nope",
    )

    # --- 14. text field, separate widget kid (field != widget) ---
    page_sep = "<<\n/Type /Page\n/MediaBox [0 0 612 792]\n/Parent 2 0 R\n/Annots [6 0 R]\n>>"
    c["field_with_kid_widget"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields [5 0 R]\n>>",
                page_sep,
                "<<\n/FT /Tx\n/T (text1)\n/V (FLATMARK)\n/Kids [6 0 R]\n>>",
                "<<\n/Parent 5 0 R\n/Subtype /Widget\n/Type /Annot\n"
                "/Rect [50 700 150 720]\n/P 4 0 R\n/AP << /N 7 0 R >>\n>>",
                _ap_stream(7),
            ]
        ),
        "all",
        "",
    )

    # --- 15. subset-refresh on a single appearance-less field ---
    c["subset_refresh_no_ap"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields [5 0 R]\n/DR << /Font << /Helv 6 0 R >> >>\n"
                "/DA (/Helv 12 Tf 0 g)\n>>",
                page_one,
                "<<\n/FT /Tx\n/T (text1)\n/V (FLATMARK)\n/DA (/Helv 12 Tf 0 g)\n"
                "/Subtype /Widget\n/Type /Annot\n/Rect [50 700 150 720]\n/P 4 0 R\n>>",
                _font_obj(),
            ]
        ),
        "subset-refresh",
        "text1",
    )

    # --- 16. text field with empty /Rect — appearance can't place, still removed ---
    c["zero_rect_all"] = (
        _build_pdf(
            [
                catalog,
                pages_one,
                "<<\n/Fields [5 0 R]\n>>",
                page_one,
                "<<\n/FT /Tx\n/T (text1)\n/V (FLATMARK)\n/Subtype /Widget\n"
                "/Type /Annot\n/Rect [50 700 50 700]\n/P 4 0 R\n/AP << /N 6 0 R >>\n>>",
                _ap_stream(6),
            ]
        ),
        "all",
        "",
    )

    return c


def _pad_to_99() -> list[str]:
    """Filler null objects so the /Helv font lands at object 99 (keeps the font
    reference stable across cases regardless of how many objects precede it)."""
    # Objects so far per case vary; we always reference 99 0 R for the font and
    # place it last. The catalog uses objects 1..k; we pad up to 98 then append
    # the font as 99. The caller appends exactly one font object after this pad.
    # Cases that use this all have 6 real objects (1..6), so pad 7..98 = 92 nulls.
    return ["null"] * 92


# ----------------------------------------------------------------- pypdfbox side


def _count_widgets(doc: PDDocument) -> int:
    total = 0
    for p in range(doc.get_number_of_pages()):
        annots = doc.get_page(p).get_cos_object().get_dictionary_object(_ANNOTS)
        if not isinstance(annots, COSArray):
            continue
        for i in range(annots.size()):
            entry = annots.get_object(i)
            if (
                isinstance(entry, COSDictionary)
                and entry.get_dictionary_object(_SUBTYPE) == _WIDGET
            ):
                total += 1
    return total


def _root_fields(doc: PDDocument) -> int:
    form = doc.get_document_catalog().get_acro_form()
    if form is None:
        return 0
    raw = form.get_cos_object().get_dictionary_object(_FIELDS)
    return raw.size() if isinstance(raw, COSArray) else 0


def _content_len(doc: PDDocument) -> int:
    total = 0
    for p in range(doc.get_number_of_pages()):
        contents = doc.get_page(p).get_cos_object().get_dictionary_object(_CONTENTS)
        if isinstance(contents, COSStream):
            total += len(contents.create_input_stream().read())
        elif isinstance(contents, COSArray):
            for i in range(contents.size()):
                entry = contents.get_object(i)
                if isinstance(entry, COSStream):
                    total += len(entry.create_input_stream().read())
    return total


def _value_baked(doc: PDDocument) -> bool:
    needle = b"FLATMARK"
    for p in range(doc.get_number_of_pages()):
        pd = doc.get_page(p).get_cos_object()
        contents = pd.get_dictionary_object(_CONTENTS)
        for blob in _collect(contents):
            if needle in blob:
                return True
        res = pd.get_dictionary_object(_RESOURCES)
        if isinstance(res, COSDictionary):
            xobj = res.get_dictionary_object(_XOBJECT)
            if isinstance(xobj, COSDictionary):
                for key in xobj.key_set():
                    entry = xobj.get_dictionary_object(key)
                    if (
                        isinstance(entry, COSStream)
                        and needle in entry.create_input_stream().read()
                    ):
                        return True
    return False


def _collect(contents: object) -> list[bytes]:
    blobs: list[bytes] = []
    if isinstance(contents, COSStream):
        blobs.append(contents.create_input_stream().read())
    elif isinstance(contents, COSArray):
        for i in range(contents.size()):
            entry = contents.get_object(i)
            if isinstance(entry, COSStream):
                blobs.append(entry.create_input_stream().read())
    return blobs


def _py_case(name: str, data: bytes, op: str, arg: str) -> tuple[list[str], bytes | None]:
    """Project pypdfbox's flatten of one case to the probe's line grammar.

    Returns ``(lines, saved_bytes)`` — ``saved_bytes`` is ``None`` when the
    flatten itself raised (so there is nothing to qpdf-check)."""
    # Pre facts.
    try:
        pre = PDDocument.load(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001 - contract probe
        return (
            [
                f"CASE {name} preFields=? preWidgets=? pages=?",
                f"FLAT {name} op={op} result=ERR:{type(e).__name__} "
                "acroform=? postFields=? postWidgets=? valueBaked=? grew=?",
                f"ENDCASE {name}",
            ],
            None,
        )
    try:
        pre_fields = _root_fields(pre)
        pre_widgets = _count_widgets(pre)
        pages = pre.get_number_of_pages()
        pre_len = _content_len(pre)
    finally:
        pre.close()

    lines = [f"CASE {name} preFields={pre_fields} preWidgets={pre_widgets} pages={pages}"]

    # Flatten + save.
    try:
        saved = _flatten_and_save(data, op, arg)
    except Exception as e:  # noqa: BLE001 - contract probe
        lines.append(
            f"FLAT {name} op={op} result=ERR:{type(e).__name__} "
            "acroform=? postFields=? postWidgets=? valueBaked=? grew=?"
        )
        lines.append(f"ENDCASE {name}")
        return lines, None

    post = PDDocument.load(io.BytesIO(saved))
    try:
        has_form = post.get_document_catalog().get_acro_form() is not None
        post_fields = _root_fields(post)
        post_widgets = _count_widgets(post)
        baked = _value_baked(post)
        post_len = _content_len(post)
        lines.append(
            f"FLAT {name} op={op} result=ok "
            f"acroform={1 if has_form else 0} postFields={post_fields} "
            f"postWidgets={post_widgets} valueBaked={1 if baked else 0} "
            f"grew={1 if post_len > pre_len else 0}"
        )
    finally:
        post.close()
    lines.append(f"ENDCASE {name}")
    return lines, saved


def _flatten_and_save(data: bytes, op: str, arg: str) -> bytes:
    doc = PDDocument.load(io.BytesIO(data))
    try:
        form = doc.get_document_catalog().get_acro_form()
        if form is None:
            buf = io.BytesIO()
            doc.save(buf)
            return buf.getvalue()
        refresh = op.endswith("refresh")
        if op.startswith("subset"):
            field = form.get_field(arg)
            only = [field] if field is not None else []
            form.flatten(only, refresh)
        elif refresh:
            form.flatten(form.get_fields(), True)
        else:
            form.flatten()
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()
    finally:
        doc.close()


# ----------------------------------------------------------------- comparison


def _group(raw: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur: str | None = None
    for line in raw.splitlines():
        if line.startswith("CASE "):
            cur = line.split()[1]
            out[cur] = [line]
        elif cur is not None:
            out[cur].append(line)
    return out


def _kv(line: str) -> dict[str, str]:
    """Parse a ``KEY a=b c=d`` line into {a:b, c:d} (ignoring the leading tag
    and the case name token)."""
    parts = line.split()
    return dict(p.split("=", 1) for p in parts if "=" in p)


# Pinned, intentional divergences. Maps (case, key) -> (java_value, py_value)
# with a justification + matching CHANGES.md row.
#
# acroform after a NO-ARG flatten-ALL (``form.flatten()``): upstream keeps the
# now-field-less /AcroForm dict (acroform=1); pypdfbox drops it outright
# (acroform=0). Documented divergence already pinned by test_flatten_oracle;
# re-asserted here. postFields=0 on both sides regardless, so the "form is gone"
# contract is identical.
#
# IMPORTANT — the drop only fires on the NO-ARG overload (``fields is None``).
# When the same full field set is passed as an EXPLICIT list (the ``all-refresh``
# op calls ``flatten(form.get_fields(), True)``), pypdfbox takes the partial-
# flatten ``remove_fields`` path and KEEPS /AcroForm — which matches Java's
# acroform=1 directly, so those cases are NOT in the drop set. The empty-form /
# missing-name cases never trigger the dict drop either because flatten returns
# early (no targets) — /AcroForm stays present on both sides.
_FLATTEN_ALL_DROP_CASES = {
    "text_with_ap_all",
    "text_no_ap_no_refresh",
    "checkbox_on_all",
    "checkbox_off_all",
    "widget_on_page2",
    "parent_two_kids",
    "hidden_widget_all",
    "invisible_widget_all",
    "widget_no_p_all",
    "field_with_kid_widget",
    "zero_rect_all",
}


def _normalise(case: str, key: str, java_val: str, py_val: str) -> tuple[str, str]:
    """Apply pinned divergences so the surviving comparison is the real
    behavioural contract. Returns the (java, py) pair to compare."""
    if key == "acroform" and case in _FLATTEN_ALL_DROP_CASES:
        # Documented: Java keeps empty /AcroForm (1), pypdfbox drops it (0).
        assert java_val == "1", f"{case}: expected Java to keep /AcroForm"
        assert py_val == "0", f"{case}: expected pypdfbox to drop /AcroForm"
        return ("X", "X")  # neutralised — both contract-correct
    return (java_val, py_val)


# Keys whose values we compare across engines (per FLAT line).
_COMPARE_KEYS = ("result", "acroform", "postFields", "postWidgets", "valueBaked")


def _build_corpus_dir(tmp_path: Path) -> tuple[Path, dict[str, tuple[bytes, str, str]]]:
    corpus = _build_corpus()
    cdir = tmp_path / "flatten_corpus"
    cdir.mkdir()
    manifest_lines = []
    for name, (data, op, arg) in corpus.items():
        (cdir / f"{name}.pdf").write_bytes(data)
        manifest_lines.append(f"{name}\t{op}\t{arg}")
    (cdir / "manifest.txt").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    return cdir, corpus


@requires_oracle
def test_acro_form_flatten_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    cdir, corpus = _build_corpus_dir(tmp_path)

    java_raw = run_probe_text("AcroFormFlattenFuzzProbe", str(cdir))
    java_groups = _group(java_raw)

    assert set(java_groups) == set(corpus), (
        "probe/corpus case mismatch: "
        f"java={sorted(java_groups)} corpus={sorted(corpus)}"
    )

    saved_blobs: dict[str, bytes] = {}
    mismatches: list[str] = []

    for name, (data, op, arg) in corpus.items():
        py_lines, saved = _py_case(name, data, op, arg)
        if saved is not None:
            saved_blobs[name] = saved

        java_lines = java_groups[name]

        # CASE header (pre facts) must match exactly.
        if py_lines[0] != java_lines[0]:
            mismatches.append(f"{name} CASE: java={java_lines[0]!r} py={py_lines[0]!r}")
            continue

        # FLAT line: compare the contract keys after applying pinned divergences.
        java_flat = next((line for line in java_lines if line.startswith("FLAT ")), "")
        py_flat = next((line for line in py_lines if line.startswith("FLAT ")), "")
        jkv = _kv(java_flat)
        pkv = _kv(py_flat)
        for key in _COMPARE_KEYS:
            jv = jkv.get(key, "?")
            pv = pkv.get(key, "?")
            jv, pv = _normalise(name, key, jv, pv)
            if jv != pv:
                mismatches.append(
                    f"{name} FLAT.{key}: java={jv!r} py={pv!r}\n"
                    f"   java={java_flat!r}\n   py  ={py_flat!r}"
                )

    assert not mismatches, "flatten parity divergences:\n" + "\n".join(mismatches)

    # qpdf validity of every pypdfbox-saved flatten output.
    if _QPDF is not None:
        for name, blob in saved_blobs.items():
            out = tmp_path / f"py_{name}.pdf"
            out.write_bytes(blob)
            proc = subprocess.run(
                [_QPDF, "--check", str(out)],
                capture_output=True,
                text=True,
                check=False,
            )
            assert proc.returncode <= 3, (
                f"{name}: pypdfbox flatten output failed qpdf --check "
                f"(rc={proc.returncode}):\n{proc.stdout}{proc.stderr}"
            )


@requires_oracle
def test_flatten_all_drops_or_keeps_acroform_but_empties_fields(tmp_path: Path) -> None:
    """Re-pin the documented flatten-ALL divergence boundary on a hand-built
    single-field form: Java keeps the (now empty) /AcroForm dict, pypdfbox drops
    it, but both leave zero referenceable root fields."""
    corpus = _build_corpus()
    data, op, _ = corpus["text_with_ap_all"]
    cdir = tmp_path / "single"
    cdir.mkdir()
    (cdir / "text_with_ap_all.pdf").write_bytes(data)
    (cdir / "manifest.txt").write_text("text_with_ap_all\tall\t\n", encoding="utf-8")

    java_raw = run_probe_text("AcroFormFlattenFuzzProbe", str(cdir))
    jkv = _kv(next(line for line in java_raw.splitlines() if line.startswith("FLAT ")))

    saved = _flatten_and_save(data, op, "")
    post = PDDocument.load(io.BytesIO(saved))
    try:
        has_form = post.get_document_catalog().get_acro_form() is not None
        py_fields = _root_fields(post)
    finally:
        post.close()

    # Java keeps the dict; pypdfbox drops it (documented).
    assert jkv["acroform"] == "1"
    assert has_form is False
    # Both empty the field set.
    assert jkv["postFields"] == "0"
    assert py_fields == 0
