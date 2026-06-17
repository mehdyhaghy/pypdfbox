"""Live PDFBox differential parity for ``/Prev`` chain resolution across
MULTIPLE stacked incremental updates, each a CLASSIC ``xref...trailer``.

PDF 32000-1 §7.5.6 — every incremental update appends a fresh body + a new
xref section whose ``/Prev`` points at the previous section's offset. The
parser walks the chain newest→oldest; for any object number the entry from
the MOST RECENT section that mentions it wins (later sections shadow earlier
ones). An object marked free (``f``) in a later section is GONE even though
an earlier section defined it (``n``).

This builds a 3-revision PDF in ``tmp_path``:

* **rev1** — classic ``xref...trailer``: catalog (1), pages (2), page (3),
  contents (4), font (5), marker (6, ``/Tag (rev1) /Value 100``).
* **rev2** — incremental append: redefines object 6
  (``/Tag (rev2-redef) /Value 200``) and adds a new marker (7,
  ``/Tag (rev2-added) /Value 300``). Its trailer ``/Prev`` → rev1.
* **rev3** — incremental append: redefines object 7
  (``/Tag (rev3-redef) /Value 400``) and FREES object 6 (xref ``f`` entry,
  generation bumped). Its trailer ``/Prev`` → rev2.

Resolved expectations both engines must agree on:
  * object 7 carries rev3's value 400 / tag ``rev3-redef`` — NOT rev2's 300.
  * object 6 is freed in rev3 → not resolvable.

Probe :class:`PrevChainProbe` (``oracle/probes/PrevChainProbe.java``) emits
``pages`` / ``root`` / ``object_count`` plus per-object ``resolved_<n>`` /
``type_<n>`` / ``tag_<n>`` / ``value_<n>``. pypdfbox must produce the same
facts.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_string import COSString
from pypdfbox.loader import Loader
from pypdfbox.pdmodel import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_TAG = COSName.get_pdf_name("Tag")
_VALUE = COSName.get_pdf_name("Value")


# ---------------------------------------------------------------- fixture build


def _build_prev_chain_pdf() -> bytes:
    """Build a 3-revision incremental PDF chained via classic-xref ``/Prev``.

    rev2 redefines object 6 and adds 7; rev3 redefines 7 and frees 6.
    """
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    # ----- rev1 body (objects 1..6) ----------------------------------------
    rev1: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: (
            b"<< /Length 44 >>\nstream\n"
            b"BT /F1 12 Tf 50 700 Td (Rev1 only text) Tj ET"
            b"\nendstream"
        ),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        6: b"<< /Type /Marker /Tag (rev1) /Value 100 >>",
    }
    off1: dict[int, int] = {}
    for n in sorted(rev1):
        off1[n] = len(out)
        out += b"%d 0 obj\n" % n + rev1[n] + b"\nendobj\n"

    # ----- rev1 classic xref + trailer + startxref + %%EOF ------------------
    xref1_off = len(out)
    out += b"xref\n0 7\n"
    out += b"0000000000 65535 f \n"
    for n in range(1, 7):
        out += b"%010d 00000 n \n" % off1[n]
    out += b"trailer\n<< /Size 7 /Root 1 0 R >>\n"
    out += b"startxref\n%d\n%%%%EOF\n" % xref1_off

    # ----- rev2 body: redefine object 6, add object 7 ----------------------
    rev2: dict[int, bytes] = {
        6: b"<< /Type /Marker /Tag (rev2-redef) /Value 200 >>",
        7: b"<< /Type /Marker /Tag (rev2-added) /Value 300 >>",
    }
    off2: dict[int, int] = {}
    for n in sorted(rev2):
        off2[n] = len(out)
        out += b"%d 0 obj\n" % n + rev2[n] + b"\nendobj\n"

    # rev2 classic xref: two single-object subsections (6 and 7), /Prev -> rev1
    xref2_off = len(out)
    out += b"xref\n"
    out += b"6 1\n%010d 00000 n \n" % off2[6]
    out += b"7 1\n%010d 00000 n \n" % off2[7]
    out += b"trailer\n<< /Size 8 /Root 1 0 R /Prev %d >>\n" % xref1_off
    out += b"startxref\n%d\n%%%%EOF\n" % xref2_off

    # ----- rev3 body: redefine object 7 ------------------------------------
    off7_rev3 = len(out)
    out += b"7 0 obj\n<< /Type /Marker /Tag (rev3-redef) /Value 400 >>\nendobj\n"

    # rev3 classic xref: free object 6 (same generation 0), redefine 7,
    # /Prev -> rev2.
    xref3_off = len(out)
    out += b"xref\n"
    # Object 6 freed at gen 0: 'f' entry, next-free=0. PDFBox NEVER inserts
    # a free record into its byte-offset map, so this does not erase the
    # in-use entry rev2 established for (6,0) — obj 6 still resolves to
    # rev2's value. pypdfbox must agree.
    out += b"6 1\n0000000000 00000 f \n"
    out += b"7 1\n%010d 00000 n \n" % off7_rev3
    out += b"trailer\n<< /Size 8 /Root 1 0 R /Prev %d >>\n" % xref2_off
    out += b"startxref\n%d\n%%%%EOF\n" % xref3_off

    return bytes(out)


# ---------------------------------------------------------------- helpers


def _parse_facts(raw: str) -> dict[str, str]:
    """Parse PrevChainProbe's ``key=value`` stdout into a dict."""
    fields: dict[str, str] = {}
    for line in raw.split("\n"):
        key, sep, value = line.partition("=")
        if sep:
            fields[key] = value
    return fields


def _py_object_facts(path: Path, *obj_nums: int) -> dict[str, str]:
    """Mirror PrevChainProbe's facts via pypdfbox. Closes the document in
    ``finally`` so the source file handle is released (Windows safety)."""
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        fields: dict[str, str] = {
            "pages": str(doc.get_number_of_pages()),
            "object_count": str(len(cos.get_xref_table())),
        }
        trailer = cos.get_trailer()
        root_ref = trailer.get_item(COSName.ROOT) if trailer is not None else None
        # COSObject reference exposes its object/generation numbers.
        obj_num = getattr(root_ref, "object_number", None)
        gen_num = getattr(root_ref, "generation_number", None)
        fields["root"] = (
            f"{obj_num} {gen_num}" if obj_num is not None else ""
        )
        for num in obj_nums:
            obj = cos.get_object(COSObjectKey(num, 0))
            base = obj.get_object() if obj is not None else None
            fields[f"resolved_{num}"] = "true" if base is not None else "false"
            if isinstance(base, COSDictionary):
                type_obj = base.get_dictionary_object(COSName.TYPE)
                fields[f"type_{num}"] = (
                    type_obj.get_name() if isinstance(type_obj, COSName) else ""
                )
                tag = base.get_dictionary_object(_TAG)
                fields[f"tag_{num}"] = (
                    tag.get_string() if isinstance(tag, COSString) else ""
                )
                fields[f"value_{num}"] = str(base.get_int(_VALUE))
        return fields
    finally:
        doc.close()


# ---------------------------------------------------------------- tests


@requires_oracle
def test_prev_chain_latest_revision_value_wins(tmp_path: Path) -> None:
    """Object 7, redefined in rev3, must resolve to rev3's value (400),
    NOT rev2's (300) — newer ``/Prev`` sections shadow older ones, and
    pypdfbox must walk the chain identically to PDFBox."""
    pdf = tmp_path / "prev_chain.pdf"
    pdf.write_bytes(_build_prev_chain_pdf())

    java = _parse_facts(run_probe_text("PrevChainProbe", "facts", str(pdf), "7"))
    py = _py_object_facts(pdf, 7)

    # Fixture sanity: PDFBox must see rev3's value, proving the chain is real.
    assert java["resolved_7"] == "true"
    assert java["value_7"] == "400", (
        f"fixture broken — PDFBox resolved obj7 to {java['value_7']}, expected 400"
    )

    assert py["pages"] == java["pages"] == "1"
    assert py["root"] == java["root"]
    assert py["resolved_7"] == java["resolved_7"] == "true"
    assert py["type_7"] == java["type_7"] == "Marker"
    assert py["tag_7"] == java["tag_7"] == "rev3-redef"
    assert py["value_7"] == java["value_7"] == "400"


@requires_oracle
def test_prev_chain_free_entry_does_not_shadow_older_in_use_entry(
    tmp_path: Path,
) -> None:
    """Object 6: defined in rev1 (100), redefined in rev2 (200), then a
    free (``f``) entry for the SAME generation appears in rev3.

    PDFBox 3.0.7 NEVER inserts a free record into its byte-offset map
    (``COSParser.parseXrefTable`` only registers in-use ``n`` entries), so
    the rev3 free entry does NOT erase the in-use entry rev2 established
    for ``(6,0)`` — object 6 still resolves to rev2's value 200. pypdfbox
    must agree: a newer-revision free entry may not shadow an older
    in-use definition for the same key.

    This is the regression guard for the bug fixed in this wave: pypdfbox
    previously let the rev3 free entry overwrite rev2's in-use entry in the
    consolidated xref merge, dropping object 6 from the pool entirely
    (``resolved_6 == false``) while PDFBox kept it reachable at 200."""
    pdf = tmp_path / "prev_chain.pdf"
    pdf.write_bytes(_build_prev_chain_pdf())

    java = _parse_facts(run_probe_text("PrevChainProbe", "facts", str(pdf), "6"))
    py = _py_object_facts(pdf, 6)

    # Sanity: PDFBox keeps object 6 reachable at rev2's value despite rev3's
    # free entry.
    assert java["resolved_6"] == "true", (
        "PDFBox dropped obj6 — fixture or PDFBox behaviour changed"
    )
    assert java["value_6"] == "200"

    # Headline guard: pypdfbox must NOT let the newer free entry shadow the
    # older in-use entry.
    assert py["resolved_6"] == java["resolved_6"] == "true", (
        "pypdfbox dropped a freed-over-in-use object — a later /Prev "
        "section's free entry wrongly shadowed the earlier 'n' definition"
    )
    assert py["type_6"] == java["type_6"] == "Marker"
    assert py["tag_6"] == java["tag_6"] == "rev2-redef"
    assert py["value_6"] == java["value_6"] == "200"
    # Both engines count the same number of objects in the merged pool.
    assert py["object_count"] == java["object_count"]
