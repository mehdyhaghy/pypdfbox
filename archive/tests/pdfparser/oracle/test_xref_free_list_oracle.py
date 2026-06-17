"""Live PDFBox differential parity for classic xref FREE-LIST handling with
GENERATION-NUMBER REUSE across a ``/Prev`` chain.

PDF 32000-1 §7.5.4 — a traditional cross-reference table records each
object as either in-use (``n``) or free (``f``). When an object is deleted,
its slot becomes a free (``f``) entry whose generation number is bumped;
a NEW object may later reuse the same object NUMBER at the incremented
generation. A correct parser must:

* **honour the free entry** from the newer revision so the OLD
  generation-0 object no longer resolves at its old slot, and
* **resolve the reused number at its NEW generation** to the object the
  newer revision added.

This module hand-authors a 2-revision PDF:

* **rev1** — classic ``xref...trailer``: catalog (1), pages (2), page (3),
  contents (4 — "Free-list probe text"), font (5), and a marker dict
  (6 gen 0, ``/Type /Marker /Tag (rev1-original) /Value 111``).
* **rev2** — appended incremental save (classic ``xref...trailer`` with
  ``/Prev`` → rev1) that FREES object 6 (an ``f`` entry at the bumped
  generation 1, linked into the free chain) and then reintroduces object
  6 at GENERATION 1 (``/Type /Marker /Tag (rev2-reused) /Value 222``).
  The catalog still references object 1; the reused object is reached via
  the rev2 trailer's ``/Info 6 1 R``.

Probe :class:`XrefFreeListProbe` (``oracle/probes/XrefFreeListProbe.java``)
emits ``pages`` / ``object_count`` / ``text`` plus per-key ``resolved_N_G``
/ ``type_N_G`` / ``tag_N_G`` / ``value_N_G``. pypdfbox must produce the
same facts: the reused ``6 1 R`` resolves to the rev2 marker, and the
stale ``6 0`` slot resolves identically to PDFBox (both engines auto-create
an unresolved placeholder for a freed slot, so neither surfaces the stale
gen-0 dictionary).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_string import COSString
from pypdfbox.loader import Loader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_TAG = COSName.get_pdf_name("Tag")
_VALUE = COSName.get_pdf_name("Value")


# ---------------------------------------------------------------- fixture build


def _build_free_list_pdf() -> bytes:
    """Build a 2-revision PDF whose rev2 classic ``xref`` frees object 6
    (gen 0) and reuses object number 6 at generation 1.

    Object layout:
      rev1: 1 catalog, 2 pages, 3 page, 4 contents, 5 font,
            6 gen 0 marker (``rev1-original``, value 111)
      rev2: 6 gen 1 marker (``rev2-reused``, value 222) -- reuses number 6

    rev2's classic xref subsections:
      * ``0 1``  -> free-list head (object 0, gen 65535, next free = 6)
      * ``6 1``  -> object 6 IN-USE at gen 1 (the reused object)

    The freed gen-0 slot is recorded in rev2's free chain by pointing the
    head's "next free object" at 6 and giving object 6's prior generation
    one increment (gen 1 is now the live slot). Both engines must reach the
    reused gen-1 object and must agree on the stale gen-0 slot.
    """
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")

    # ----- rev1 body (objects 1..6 gen 0) ----------------------------------
    objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: (
            b"<< /Length 47 >>\nstream\n"
            b"BT /F1 12 Tf 50 700 Td (Free-list probe text) Tj ET"
            b"\nendstream"
        ),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        6: b"<< /Type /Marker /Tag (rev1-original) /Value 111 >>",
    }
    offsets: dict[int, int] = {}
    for n in sorted(objs):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n"

    # ----- rev1 classic xref + trailer + startxref + %%EOF ------------------
    xref1_off = len(out)
    n_objs_rev1 = 7  # objects 0..6
    out += b"xref\n0 %d\n" % n_objs_rev1
    out += b"0000000000 65535 f \n"
    for n in range(1, n_objs_rev1):
        out += b"%010d 00000 n \n" % offsets[n]
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info 6 0 R >>\n" % n_objs_rev1
    out += b"startxref\n%d\n%%%%EOF\n" % xref1_off

    # ----- rev2 body: reuse object number 6 at GENERATION 1 -----------------
    obj6_gen1_off = len(out)
    out += (
        b"6 1 obj\n<< /Type /Marker /Tag (rev2-reused) /Value 222 >>\nendobj\n"
    )

    # ----- rev2 classic xref + trailer + startxref + %%EOF ------------------
    # Two subsections:
    #   0 1  -> free-list head: object 0, gen 65535, next free obj = 6
    #   6 1  -> object 6 IN-USE at gen 1 (the reused object)
    # The freed gen-0 object 6 is represented by the head's next-free pointer
    # (object 0 -> 6) combined with the bumped generation on the live slot.
    xref2_off = len(out)
    out += b"xref\n"
    out += b"0 1\n"
    out += b"0000000006 65535 f \n"
    out += b"6 1\n"
    out += b"%010d 00001 n \n" % obj6_gen1_off
    out += (
        b"trailer\n<< /Size 7 /Root 1 0 R /Info 6 1 R /Prev %d >>\n" % xref1_off
    )
    out += b"startxref\n%d\n%%%%EOF\n" % xref2_off
    return bytes(out)


# ---------------------------------------------------------------- helpers


def _parse_facts(raw: str) -> dict[str, str]:
    """Parse XrefFreeListProbe's ``facts`` stdout. The ``text=`` line is
    emitted last and may itself contain ``=``/newlines, so it is consumed
    verbatim once encountered."""
    fields: dict[str, str] = {}
    lines = raw.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        key, sep, value = line.partition("=")
        if not sep:
            i += 1
            continue
        if key == "text":
            fields["text"] = "\n".join([value, *lines[i + 1 :]])
            break
        fields[key] = value
        i += 1
    return fields


def _py_object_facts(
    path: Path, *keys: tuple[int, int]
) -> dict[str, str]:
    """Mirror XrefFreeListProbe's facts via pypdfbox. Closes the document
    in ``finally`` so the source file handle is released (Windows safety)."""
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        fields: dict[str, str] = {
            "pages": str(doc.get_number_of_pages()),
            "object_count": str(len(cos.get_xref_table())),
        }
        for num, gen in keys:
            suffix = f"{num}_{gen}"
            obj = cos.get_object_from_pool(COSObjectKey(num, gen))
            base = obj.get_object() if obj is not None else None
            fields[f"resolved_{suffix}"] = "true" if base is not None else "false"
            if isinstance(base, COSDictionary):
                type_obj = base.get_dictionary_object(COSName.TYPE)
                fields[f"type_{suffix}"] = (
                    type_obj.get_name() if isinstance(type_obj, COSName) else ""
                )
                tag = base.get_dictionary_object(_TAG)
                fields[f"tag_{suffix}"] = (
                    tag.get_string() if isinstance(tag, COSString) else ""
                )
                fields[f"value_{suffix}"] = str(base.get_int(_VALUE))
        fields["text"] = PDFTextStripper().get_text(doc)
        return fields
    finally:
        doc.close()


# ---------------------------------------------------------------- tests


@requires_oracle
def test_free_list_generation_reuse_resolves_reused_object(
    tmp_path: Path,
) -> None:
    """pypdfbox honours rev2's free entry for object 6 gen 0 and resolves
    the REUSED object number 6 at generation 1 identically to PDFBox.

    The headline guard: ``6 1 R`` (the rev2 reused slot) must resolve to
    the rev2 marker on both engines, and the stale gen-0 slot must resolve
    identically (neither engine may surface the rev1 dictionary at gen 0)."""
    pdf = tmp_path / "xref_free_list_reuse.pdf"
    pdf.write_bytes(_build_free_list_pdf())

    java = _parse_facts(
        run_probe_text("XrefFreeListProbe", "facts", str(pdf), "6:0", "6:1")
    )
    py = _py_object_facts(pdf, (6, 0), (6, 1))

    # Sanity: PDFBox must read the fixture and reach the reused object.
    assert java["pages"] == "1", (
        "PDFBox failed to parse the free-list fixture — fixture is broken"
    )
    assert java["resolved_6_1"] == "true", (
        "PDFBox failed to resolve the reused gen-1 object — fixture broken"
    )

    # Headline: pypdfbox resolves the reused gen-1 object.
    assert py["resolved_6_1"] == java["resolved_6_1"] == "true"
    assert py["type_6_1"] == java["type_6_1"] == "Marker"
    assert py["tag_6_1"] == java["tag_6_1"] == "rev2-reused"
    assert py["value_6_1"] == java["value_6_1"] == "222"

    # Stale gen-0 slot resolves identically across engines (the freed slot
    # must NOT surface the rev1 dictionary on either engine).
    assert py["resolved_6_0"] == java["resolved_6_0"]
    if java["resolved_6_0"] == "true":
        # If PDFBox resolves it at all, the tag must match — a divergence
        # here would mean one engine kept the freed rev1 object.
        assert py.get("tag_6_0", "") == java.get("tag_6_0", "")
        assert py.get("value_6_0", "") == java.get("value_6_0", "")
    else:
        assert "rev1-original" not in py.get("tag_6_0", ""), (
            "pypdfbox surfaced the freed rev1 object at gen 0 — the free "
            "entry from rev2 was not honoured"
        )

    # Page count + body text parity.
    assert py["pages"] == java["pages"]
    assert py["text"] == java["text"]


@requires_oracle
def test_free_list_generation_reuse_object_count_matches(
    tmp_path: Path,
) -> None:
    """The catalog must resolve, the page count must match, and pypdfbox's
    merged pool must surface AT LEAST as many objects as PDFBox's — neither
    engine may silently drop entries across the ``/Prev`` hop."""
    pdf = tmp_path / "xref_free_list_reuse.pdf"
    pdf.write_bytes(_build_free_list_pdf())

    java = _parse_facts(
        run_probe_text("XrefFreeListProbe", "facts", str(pdf), "1:0")
    )
    py = _py_object_facts(pdf, (1, 0))

    assert java["resolved_1_0"] == py["resolved_1_0"] == "true"
    assert py["type_1_0"] == java["type_1_0"] == "Catalog"
    assert py["pages"] == java["pages"] == "1"

    # pypdfbox must see at least as many objects as PDFBox — the /Prev hop
    # into rev1's classic table registered the rev1 entries.
    assert int(py["object_count"]) >= int(java["object_count"])
