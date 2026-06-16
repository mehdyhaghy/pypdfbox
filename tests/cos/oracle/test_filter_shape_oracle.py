"""Live PDFBox differential parity for ``/Filter`` SHAPE leniency.

ISO 32000-1 §7.4.2 allows the ``/Filter`` entry on a stream dictionary to
appear in either of two shapes:

* A single ``COSName`` — ``/Filter /FlateDecode``
* A ``COSArray`` of ``COSName`` — ``/Filter [/FlateDecode]`` or
  ``[/ASCII85Decode /FlateDecode]``

PDFBox normalises both shapes transparently at decode time: a bare-name
``/Filter`` is treated identically to a one-element array, and the chain is
walked left-to-right regardless of how the producer wrote the entry. The
spec puts no semantic difference between the two shapes — a one-element
array MUST decode identically to a bare name on the same body.

This oracle exercises that leniency end-to-end. For each test case we:

1. Build a PDF with pypdfbox whose page content stream is FlateDecode-
   encoded (writer emits the COMPACT single-name form, the same shape
   PDFBox's writer uses).
2. Byte-patch the in-memory PDF to wrap the same name in a one-element
   array (``/Filter /FlateDecode`` → ``/Filter [/FlateDecode]``). The
   stream body is untouched — exactly the producer-shape divergence the
   spec calls out.
3. Drive ``FilterShapeProbe`` against each variant: PDFBox 3.0.7 must
   land on the same ``(pages, content_decoded_len, text)`` tuple for
   bare-name and one-element-array, with ``first_filter_shape`` reflecting
   the producer's choice.
4. Drive pypdfbox over the same files and assert byte-equal parity to the
   probe output — same decoded body length, same extracted text, same
   normalised filter list across both shapes.

The third case (``/Filter [/ASCII85Decode /FlateDecode]``) pins the
multi-element chain end-to-end so the array-handling path doesn't quietly
regress to single-element-only.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.cos.cos_array import COSArray
from pypdfbox.pdmodel import PDDocument, PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_CONTENT_PLAIN = (
    b"BT /F1 12 Tf 100 700 Td (Hello PDF Filter Test) Tj ET\n"
    # padding so deflate output is non-trivial and bytes don't collide
    # with the dictionary header on a hand-patched fixture.
    + b"% padding " + (b"P" * 64) + b"\n"
)


def _build_flate_pdf(tmp_path: Path) -> Path:
    """Build a PDF with a single FlateDecode-encoded content stream.

    pypdfbox's writer emits the compact single-name ``/Filter /FlateDecode``
    shape — exactly what PDFBox writes. This is the bare-name fixture.
    """
    out = tmp_path / "bare_filter.pdf"
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        stream = COSStream()
        with stream.create_output_stream(filters=COSName.FLATE_DECODE) as sink:
            sink.write(_CONTENT_PLAIN)
        page.set_contents(stream)
        doc.save(out)
    finally:
        doc.close()
    return out


def _patch_bare_to_array(src: Path, dst: Path) -> Path:
    """Patch ``/Filter /FlateDecode`` → ``/Filter [/FlateDecode]`` in place.

    PDFBox tolerates a stream-dict whose serialised length differs from the
    declared ``/Length`` value by a couple of bytes (the parser still reads
    body bytes up to ``endstream``), so the two-character expansion the
    array brackets introduce does not invalidate the file. This is the
    deliberate producer divergence the test exercises.
    """
    data = src.read_bytes()
    patched, n = re.subn(
        rb"/Filter /FlateDecode", b"/Filter [/FlateDecode]", data, count=1
    )
    assert n == 1, "fixture must contain exactly one bare /Filter entry"
    dst.write_bytes(patched)
    return dst


def _build_multi_filter_pdf(tmp_path: Path) -> Path:
    """Build a PDF whose content stream uses a 2-filter chain.

    ``/Filter [/ASCII85Decode /FlateDecode]`` — both filters are applied in
    encode-reverse order (FlateDecode first, then ASCII85), so the on-disk
    body is ASCII85-armoured Flate output. The decode path must run
    left-to-right: undo ASCII85, then undo Flate, recovering ``_CONTENT_PLAIN``.
    """
    out = tmp_path / "multi_filter.pdf"
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        stream = COSStream()
        with stream.create_output_stream(
            filters=[
                COSName.get_pdf_name("ASCII85Decode"),
                COSName.FLATE_DECODE,
            ],
        ) as sink:
            sink.write(_CONTENT_PLAIN)
        page.set_contents(stream)
        doc.save(out)
    finally:
        doc.close()
    return out


# ----- pypdfbox-side reproduction of the same facts the probe emits ----------


def _pypdfbox_facts(path: Path) -> dict[str, str]:
    """Reproduce the four ``key=value`` lines ``FilterShapeProbe`` emits.

    Counts decoded bytes over every UNTYPED ``COSStream`` (content streams
    don't carry a /Type — typed streams like catalog / pages / font
    descriptors / /ObjStm / /XRef are excluded so the metric tracks page
    content). Reports the first counted stream's /Filter shape +
    normalised chain names + extracted text.
    """
    pages: int
    total_decoded_len = 0
    first_shape = "none"
    first_list = ""
    first_seen = False

    from pypdfbox.text.pdf_text_stripper import PDFTextStripper

    with PDDocument.load(path) as doc:
        pages = doc.get_number_of_pages()
        cos_doc = doc.get_document()
        for cos_obj in cos_doc.get_objects():
            base = cos_obj.get_object()
            if not isinstance(base, COSStream):
                continue
            type_entry = base.get_dictionary_object(COSName.TYPE)
            if type_entry is not None:
                continue
            with base.create_input_stream() as src:
                total_decoded_len += len(src.read())
            if not first_seen:
                first_seen = True
                raw_filters = base.get_filters()
                if raw_filters is None:
                    first_shape = "none"
                elif isinstance(raw_filters, COSName):
                    first_shape = "name"
                elif isinstance(raw_filters, COSArray):
                    first_shape = "array"
                first_list = ",".join(
                    name.name for name in base.get_filter_list()
                )

        text = PDFTextStripper().get_text(doc)

    one_line = re.sub(r"\s+", " ", text).strip()

    return {
        "pages": str(pages),
        "content_decoded_len": str(total_decoded_len),
        "first_filter_shape": first_shape,
        "first_filter_list": first_list,
        "text": one_line,
    }


def _parse_probe_output(text: str) -> dict[str, str]:
    facts: dict[str, str] = {}
    for raw in text.splitlines():
        if not raw:
            continue
        key, _, value = raw.partition("=")
        facts[key] = value
    return facts


# ============================================================================
# Differential tests
# ============================================================================


@requires_oracle
def test_bare_filter_name_pypdfbox_matches_pdfbox(tmp_path: Path) -> None:
    """``/Filter /FlateDecode`` (single name) — pypdfbox decodes identically
    to PDFBox: same pages, same decoded length, same filter shape, same
    text."""
    fixture = _build_flate_pdf(tmp_path)
    java = _parse_probe_output(run_probe_text("FilterShapeProbe", str(fixture)))
    py = _pypdfbox_facts(fixture)

    assert py == java
    assert py["first_filter_shape"] == "name"
    assert py["first_filter_list"] == "FlateDecode"
    assert py["pages"] == "1"
    assert py["content_decoded_len"] == str(len(_CONTENT_PLAIN))
    assert "Hello PDF Filter Test" in py["text"]


@requires_oracle
def test_single_element_filter_array_pypdfbox_matches_pdfbox(
    tmp_path: Path,
) -> None:
    """``/Filter [/FlateDecode]`` (one-element array) — same body, same
    decoded result; only the producer shape differs. Both PDFBox and
    pypdfbox MUST report ``first_filter_shape=array`` while landing on the
    identical decoded length + extracted text as the bare-name case."""
    bare = _build_flate_pdf(tmp_path)
    patched = _patch_bare_to_array(bare, tmp_path / "array_filter.pdf")
    java = _parse_probe_output(run_probe_text("FilterShapeProbe", str(patched)))
    py = _pypdfbox_facts(patched)

    assert py == java
    assert py["first_filter_shape"] == "array"
    assert py["first_filter_list"] == "FlateDecode"
    assert py["pages"] == "1"
    assert py["content_decoded_len"] == str(len(_CONTENT_PLAIN))
    assert "Hello PDF Filter Test" in py["text"]


@requires_oracle
def test_bare_and_one_element_array_decode_identically(tmp_path: Path) -> None:
    """The whole point of the leniency: a one-element array decodes to
    the SAME bytes as the bare-name form on the same body. Asserts the
    invariant directly across pypdfbox + PDFBox."""
    bare = _build_flate_pdf(tmp_path)
    patched = _patch_bare_to_array(bare, tmp_path / "array_filter.pdf")

    java_bare = _parse_probe_output(run_probe_text("FilterShapeProbe", str(bare)))
    java_arr = _parse_probe_output(
        run_probe_text("FilterShapeProbe", str(patched))
    )
    py_bare = _pypdfbox_facts(bare)
    py_arr = _pypdfbox_facts(patched)

    # Decoded length + text are shape-independent on both sides.
    assert java_bare["content_decoded_len"] == java_arr["content_decoded_len"]
    assert java_bare["text"] == java_arr["text"]
    assert py_bare["content_decoded_len"] == py_arr["content_decoded_len"]
    assert py_bare["text"] == py_arr["text"]
    # And pypdfbox lands on PDFBox's numbers shape-by-shape.
    assert py_bare["content_decoded_len"] == java_bare["content_decoded_len"]
    assert py_arr["content_decoded_len"] == java_arr["content_decoded_len"]
    assert py_bare["text"] == java_bare["text"]
    assert py_arr["text"] == java_arr["text"]


@requires_oracle
def test_multi_filter_chain_pypdfbox_matches_pdfbox(tmp_path: Path) -> None:
    """``/Filter [/ASCII85Decode /FlateDecode]`` — a real two-filter chain.

    Pins that the array-handling path keeps left-to-right decode order:
    ASCII85 undoes the armour, FlateDecode undoes the compression, and
    the recovered body equals ``_CONTENT_PLAIN`` on both sides."""
    fixture = _build_multi_filter_pdf(tmp_path)
    java = _parse_probe_output(run_probe_text("FilterShapeProbe", str(fixture)))
    py = _pypdfbox_facts(fixture)

    assert py == java
    assert py["first_filter_shape"] == "array"
    assert py["first_filter_list"] == "ASCII85Decode,FlateDecode"
    assert py["content_decoded_len"] == str(len(_CONTENT_PLAIN))


# ============================================================================
# pypdfbox-side invariants (no oracle, fast)
# ============================================================================


def test_set_filters_single_name_stores_bare_name() -> None:
    """``set_filters([name])`` stores the COMPACT single-name shape so the
    writer emits ``/Filter /FlateDecode`` (not the one-element array)."""
    s = COSStream()
    s.set_filters([COSName.FLATE_DECODE])
    assert isinstance(s.get_filters(), COSName)
    assert s.get_filter_list() == [COSName.FLATE_DECODE]


def test_set_filters_two_names_stores_array() -> None:
    """``set_filters([n1, n2])`` stores a ``COSArray`` so the writer emits
    the array shape ``/Filter [/n1 /n2]``."""
    s = COSStream()
    s.set_filters(
        [COSName.get_pdf_name("ASCII85Decode"), COSName.FLATE_DECODE]
    )
    assert isinstance(s.get_filters(), COSArray)
    assert [n.name for n in s.get_filter_list()] == [
        "ASCII85Decode",
        "FlateDecode",
    ]


def test_get_filter_list_normalises_bare_name_and_one_element_array(
    tmp_path: Path,
) -> None:
    """The dispatch invariant: a stream whose ``/Filter`` dictionary entry
    is a bare ``COSName`` and one whose entry is a single-element
    ``COSArray`` must surface the IDENTICAL ``get_filter_list()`` /
    decoded body."""
    bare = _build_flate_pdf(tmp_path)
    patched = _patch_bare_to_array(bare, tmp_path / "array_filter.pdf")

    bare_chain: list[str]
    bare_decoded: bytes
    bare_raw: bytes
    arr_chain: list[str]
    arr_decoded: bytes
    arr_raw: bytes

    with PDDocument.load(bare) as doc:
        for cos_obj in doc.get_document().get_objects():
            base = cos_obj.get_object()
            if isinstance(base, COSStream) and base.get_dictionary_object(
                COSName.TYPE
            ) is None:
                bare_chain = [n.name for n in base.get_filter_list()]
                with base.create_input_stream() as src:
                    bare_decoded = src.read()
                bare_raw = base.get_raw_data()
                break

    with PDDocument.load(patched) as doc:
        for cos_obj in doc.get_document().get_objects():
            base = cos_obj.get_object()
            if isinstance(base, COSStream) and base.get_dictionary_object(
                COSName.TYPE
            ) is None:
                arr_chain = [n.name for n in base.get_filter_list()]
                with base.create_input_stream() as src:
                    arr_decoded = src.read()
                arr_raw = base.get_raw_data()
                break

    assert bare_chain == arr_chain == ["FlateDecode"]
    # Same on-disk raw body (the patch only rewraps /Filter).
    assert bare_raw == arr_raw
    # Same decoded body.
    assert bare_decoded == arr_decoded == _CONTENT_PLAIN


# Pin the in-memory equivalent so a future refactor of ``get_filter_list``
# that drops the COSArray branch fails the suite without needing the oracle.
def test_get_filter_list_handles_in_memory_array_form() -> None:
    s = COSStream()
    # Bypass set_filters' compact-single-name normalisation and store the
    # exact array shape the spec allows producers to write.
    s.set_item(COSName.FILTER, COSArray([COSName.FLATE_DECODE]))
    assert isinstance(s.get_filters(), COSArray)
    assert s.get_filter_list() == [COSName.FLATE_DECODE]
    assert s.has_filters() is True
    assert s.has_filter(COSName.FLATE_DECODE) is True
    assert s.get_first_filter() == COSName.FLATE_DECODE


def test_get_filter_list_handles_in_memory_bare_name() -> None:
    s = COSStream()
    s.set_item(COSName.FILTER, COSName.FLATE_DECODE)
    assert isinstance(s.get_filters(), COSName)
    assert s.get_filter_list() == [COSName.FLATE_DECODE]
    assert s.has_filters() is True
    assert s.has_filter(COSName.FLATE_DECODE) is True
    assert s.get_first_filter() == COSName.FLATE_DECODE


def test_get_filter_list_rejects_non_name_array_entry() -> None:
    """A malformed ``/Filter`` array carrying a non-name entry raises
    ``OSError`` — upstream ``getFilterList`` throws ``IOException``
    ("Forbidden type in filter array: ...") for a non-name array element
    (wave 1564)."""
    from pypdfbox.cos.cos_integer import COSInteger

    s = COSStream()
    s.set_item(COSName.FILTER, COSArray([COSInteger.get(0)]))
    with pytest.raises(OSError, match="Forbidden type in filter array"):
        s.get_filter_list()


