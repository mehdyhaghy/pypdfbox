from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser

# ---------- helpers ----------


def _build_linearized_pdf(
    *,
    linearized_value: bytes = b"1",
    file_length: int = 0,
    hint_offset: int = 0,
    hint_length: int = 0,
    first_page_obj: int = 4,
    end_of_first_page: int = 0,
    n_pages: int = 1,
    main_xref_offset: int = 0,
    hint_body: bytes = b"HINTBYTES",
) -> bytes:
    """Assemble a tiny linearized-shaped PDF.

    The structure mirrors PDF 32000-1 Annex F:

      %PDF-1.7
      1 0 obj  << /Linearized 1 /L ... /H [hint_off hint_len]
                  /O ... /E ... /N ... /T ... >>
      endobj
      2 0 obj  << /Length N >> stream HINTBYTES endstream endobj
      3 0 obj  << /Type /Catalog /Pages 4 0 R >> endobj
      4 0 obj  << /Type /Pages /Kids [5 0 R] /Count 1 >> endobj
      5 0 obj  << /Type /Page /Parent 4 0 R ... >> endobj
      xref
      trailer << /Size 6 /Root 3 0 R >>
      startxref ...
      %%EOF

    Most numeric fields in the linearization dict are set with
    placeholder values *after* the byte layout is computed (we patch
    them in once we know real offsets) — except for fields that the
    test explicitly sets, which the caller can override via kwargs.
    """
    out = bytearray()
    out += b"%PDF-1.7\n"
    # Reserve a slot for the linearization dict's text so we can patch
    # it in after we know the hint stream offset.
    lin_obj_placeholder_start = len(out)
    # Render the linearization dict with the caller-supplied values
    # first; we'll re-render it once /H offset/length are known when
    # the caller passes hint_offset=0 / hint_length=0 (the default —
    # let the helper auto-compute).
    auto_hint = hint_offset == 0 and hint_length == 0
    # First pass: emit a stub linearization dict so we know where the
    # hint stream body lands. We'll rewrite it once.
    stub_dict = (
        b"1 0 obj\n"
        b"<< /Linearized " + linearized_value + b" "
        b"/L " + str(file_length).encode("ascii") + b" "
        b"/H [0000000000 0000000000] "
        b"/O " + str(first_page_obj).encode("ascii") + b" "
        b"/E " + str(end_of_first_page).encode("ascii") + b" "
        b"/N " + str(n_pages).encode("ascii") + b" "
        b"/T " + str(main_xref_offset).encode("ascii") + b" "
        b">>\nendobj\n"
    )
    out += stub_dict
    # Hint stream object 2 — emit with raw hint_body.
    hint_stream_dict = (
        b"2 0 obj\n<< /Length " + str(len(hint_body)).encode("ascii") + b" >>\nstream\n"
    )
    hint_body_offset = len(out) + len(hint_stream_dict)
    out += hint_stream_dict
    out += hint_body + b"\nendstream\nendobj\n"
    # Catalog + page tree.
    obj3_offset = len(out)
    out += b"3 0 obj\n<< /Type /Catalog /Pages 4 0 R >>\nendobj\n"
    obj4_offset = len(out)
    out += b"4 0 obj\n<< /Type /Pages /Kids [5 0 R] /Count 1 >>\nendobj\n"
    obj5_offset = len(out)
    out += b"5 0 obj\n<< /Type /Page /Parent 4 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    # If the caller didn't pass explicit hint_offset/length, patch the
    # linearization dict with the actual values now.
    if auto_hint:
        real_off = hint_body_offset
        real_len = len(hint_body)
        patched = (
            b"1 0 obj\n"
            b"<< /Linearized " + linearized_value + b" "
            b"/L " + str(file_length).encode("ascii") + b" "
            b"/H [" + f"{real_off:010d}".encode("ascii") + b" "
            + f"{real_len:010d}".encode("ascii") + b"] "
            b"/O " + str(first_page_obj).encode("ascii") + b" "
            b"/E " + str(end_of_first_page).encode("ascii") + b" "
            b"/N " + str(n_pages).encode("ascii") + b" "
            b"/T " + str(main_xref_offset).encode("ascii") + b" "
            b">>\nendobj\n"
        )
        # The patched dict has the same length as the stub by
        # construction — both use 10-digit zero-padded ints.
        assert len(patched) == len(stub_dict), (len(patched), len(stub_dict))
        out[lin_obj_placeholder_start : lin_obj_placeholder_start + len(stub_dict)] = patched
    # Now emit xref + trailer + startxref.
    xref_offset = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n"
    for off in (lin_obj_placeholder_start, hint_body_offset - len(hint_stream_dict),
                obj3_offset, obj4_offset, obj5_offset):
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 6 /Root 3 0 R >>\n"
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def _parse(pdf_bytes: bytes) -> PDFParser:
    parser = PDFParser(RandomAccessReadBuffer(pdf_bytes))
    parser.parse()
    return parser


def _close(parser: PDFParser) -> None:
    """Close the parser's document — keeps the scratch-file warning
    suppressed across tests. Idempotent."""
    doc = parser.get_document()
    if doc is not None:
        doc.close()


# ---------- positive cases ----------


def test_is_linearized_true_for_linearized_pdf() -> None:
    pdf = _build_linearized_pdf()
    p = _parse(pdf)
    assert p.is_linearized() is True
    assert p.linearization_dict is not None
    assert isinstance(p.linearization_dict, COSDictionary)
    _close(p)


def test_linearization_dict_round_trips_known_keys() -> None:
    pdf = _build_linearized_pdf(
        first_page_obj=4,
        end_of_first_page=1234,
        n_pages=7,
        main_xref_offset=5678,
    )
    p = _parse(pdf)
    d = p.get_linearization_dictionary()
    assert d is not None
    # The /Linearized number must round-trip as 1.
    lin = d.get_int("Linearized")
    assert lin == 1
    assert d.get_int("O") == 4
    assert d.get_int("E") == 1234
    assert d.get_int("N") == 7
    assert d.get_int("T") == 5678
    _close(p)


def test_hint_table_bytes_are_extracted() -> None:
    body = b"HINTPAYLOAD-XYZ-12345"
    pdf = _build_linearized_pdf(hint_body=body)
    p = _parse(pdf)
    assert p.hint_table_bytes == body
    assert p.get_hint_table_bytes() == body
    _close(p)


def test_linearized_value_as_float_is_recognised() -> None:
    """Per spec ``/Linearized`` is a number — accept ``1.0`` too."""
    pdf = _build_linearized_pdf(linearized_value=b"1.0")
    p = _parse(pdf)
    assert p.is_linearized() is True
    _close(p)


# ---------- negative cases ----------


def test_non_linearized_pdf_reports_false() -> None:
    """A regular PDF whose first object is a /Catalog (not a /Linearized
    dict) must surface as not-linearized."""
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Count 0 >>\nendobj\n"
    )
    # Append xref + trailer.
    obj1_off = pdf.find(b"1 0 obj")
    obj2_off = pdf.find(b"2 0 obj")
    xref_off = len(pdf)
    pdf += b"xref\n0 3\n0000000000 65535 f \n"
    pdf += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    pdf += f"{obj2_off:010d} 00000 n \n".encode("ascii")
    pdf += b"trailer\n<< /Size 3 /Root 1 0 R >>\n"
    pdf += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    p = _parse(pdf)
    assert p.is_linearized() is False
    assert p.linearization_dict is None
    assert p.hint_table_bytes is None
    _close(p)


def test_linearized_zero_value_is_not_linearized() -> None:
    """``/Linearized 0`` (extremely unusual but spec-permits any number)
    must not flip the flag — only truthy numbers do."""
    pdf = _build_linearized_pdf(linearized_value=b"0")
    p = _parse(pdf)
    assert p.is_linearized() is False
    assert p.hint_table_bytes is None
    _close(p)


def test_linearization_state_is_advisory_only() -> None:
    """Linearized parses must not skip / shortcut the regular xref walk
    — the document pool must still contain the catalog object."""
    pdf = _build_linearized_pdf()
    p = _parse(pdf)
    doc = p.get_document()
    assert doc is not None
    catalog = doc.get_catalog()
    assert catalog is not None
    assert catalog.get_name("Type") == "Catalog"
    _close(p)


# ---------- defensive parsing ----------


def test_first_object_not_a_dict_does_not_raise() -> None:
    """If the first object is something exotic (an integer, say), the
    detector must silently leave the parser in the not-linearized
    state — no exception."""
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n42\nendobj\n"
        b"2 0 obj\n<< /Type /Catalog >>\nendobj\n"
    )
    obj1_off = pdf.find(b"1 0 obj")
    obj2_off = pdf.find(b"2 0 obj")
    xref_off = len(pdf)
    pdf += b"xref\n0 3\n0000000000 65535 f \n"
    pdf += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    pdf += f"{obj2_off:010d} 00000 n \n".encode("ascii")
    pdf += b"trailer\n<< /Size 3 /Root 2 0 R >>\n"
    pdf += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    p = _parse(pdf)
    assert p.is_linearized() is False
    _close(p)
