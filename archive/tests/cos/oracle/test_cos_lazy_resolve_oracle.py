"""Live PDFBox differential parity for COSObject lazy indirect resolution.

A PDF's body is a graph of indirect objects linked by ``N G R`` references. The
``COSObject`` class is the lazy holder for one such reference: it carries the
``(objectNumber, generationNumber)`` key into the document's xref and a loader
that parses the referenced body on first ``getObject()``. Two behaviours of this
surface are load-bearing for graph fidelity and have to match Apache PDFBox
3.0.7 exactly:

  * **Object-pool dedup identity.** When the same object is referenced from two
    places (``/SharedA 10 0 R`` and ``/SharedB 10 0 R``), the parser routes both
    through ``COSDocument.getObjectFromPool(key)``, so both raw entries are the
    *same* ``COSObject`` instance, and dereferencing either yields the *same*
    underlying ``COSBase`` — the body is parsed once and shared. An indirect
    reference appearing twice inside an array dedups to that same instance too.
  * **Null-on-missing.** A reference to an object with no xref entry (a dangling
    ``99 0 R``) dereferences to null: ``getObject()`` is ``None``,
    ``isObjectNull()`` is ``True``, and ``getDictionaryObject`` collapses it to
    ``None``.

Plus the recursion-safety guarantees: a self reference (object 20 carrying
``/Me 20 0 R``) and a two-object cycle (30 ⇄ 31) both resolve without infinite
recursion, with the cycle closing on the *same* shared base/COSObject instance.

The ``CosLazyResolveProbe`` Java probe loads the same bytes via
``Loader.loadPDF`` and emits a canonical JSON summary (identity comparisons as
booleans, types as coarse tags); pypdfbox parses the same bytes and emits the
same summary with identical rules. The two must match character for character.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_parser import PDFParser
from tests.oracle.harness import requires_oracle, run_probe_text

_HEADER = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"


def _obj(num: int, body: str) -> bytes:
    return f"{num} 0 obj\n{body}\nendobj\n".encode("latin-1")


def _build_pdf() -> bytes:
    """Build a single-section PDF whose catalog exercises the COSObject
    reference surface:

      * object 10 — a plain dict referenced from /SharedA, /SharedB, and twice
        inside /Arr (pool-dedup identity target);
      * object 99 — referenced from /Dangling but NEVER defined and absent from
        the xref (dangling reference → null);
      * object 20 — a dict carrying /Me 20 0 R (self reference);
      * objects 30 and 31 — each carrying /Next pointing at the other
        (two-object cycle).
    """
    buf = bytearray(_HEADER)
    offsets: dict[int, int] = {}

    def add(num: int, body: str) -> None:
        offsets[num] = len(buf)
        buf.extend(_obj(num, body))

    add(
        1,
        "<< /Type /Catalog /Pages 2 0 R "
        "/SharedA 10 0 R /SharedB 10 0 R "
        "/Dangling 99 0 R /SelfRef 20 0 R /CycleHead 30 0 R "
        "/Arr [10 0 R 10 0 R] >>",
    )
    add(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    add(3, "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>")
    add(10, "<< /Type /SharedThing /Value 42 >>")
    add(20, "<< /Type /Selfie /Me 20 0 R >>")
    add(30, "<< /Type /Node /Name (head) /Next 31 0 R >>")
    add(31, "<< /Type /Node /Name (tail) /Next 30 0 R >>")

    # Single xref table. Object 99 is deliberately omitted (dangling ref).
    # Subsection 0..3 (catalog graph), then 10, 20, 30, 31 as singletons.
    xref_off = len(buf)
    nums = [0, 1, 2, 3, 10, 20, 30, 31]
    # Group consecutive numbers into xref subsections.
    subsections: list[list[int]] = []
    run: list[int] = []
    for n in nums:
        if run and n == run[-1] + 1:
            run.append(n)
        else:
            if run:
                subsections.append(run)
            run = [n]
    if run:
        subsections.append(run)

    buf.extend(b"xref\n")
    for sub in subsections:
        buf.extend(f"{sub[0]} {len(sub)}\n".encode("latin-1"))
        for n in sub:
            if n == 0:
                buf.extend(b"0000000000 65535 f \n")
            else:
                buf.extend(f"{offsets[n]:010d} 00000 n \n".encode("latin-1"))

    buf.extend(b"trailer\n")
    # /Size is the highest object number + 1.
    buf.extend(b"<< /Size 32 /Root 1 0 R >>\n")
    buf.extend(b"startxref\n")
    buf.extend(f"{xref_off}\n".encode("latin-1"))
    buf.extend(b"%%EOF\n")
    return bytes(buf)


def _type_tag(base: COSBase | None) -> str:
    """Coarse type tag mirroring ``CosLazyResolveProbe.typeTag``."""
    if base is None:
        return "null"
    if isinstance(base, COSObject):
        return "object"
    if isinstance(base, COSArray):
        return "array"
    if isinstance(base, COSDictionary):
        return "dict"
    return f"other:{type(base).__name__}"


def _pypdfbox_resolve(data: bytes) -> dict[str, object]:
    """Parse ``data`` with pypdfbox and emit the same summary the Java
    ``CosLazyResolveProbe`` produces."""
    parser = PDFParser(RandomAccessReadBuffer(data))
    doc = parser.parse()
    try:
        parser.initial_parse()
        cos_doc = doc
        catalog = cos_doc.get_catalog()
        assert catalog is not None

        out: dict[str, object] = {}

        # --- dedup identity: /SharedA and /SharedB both -> object 10.
        raw_a = catalog.get_item("SharedA")
        raw_b = catalog.get_item("SharedB")
        out["sharedA_is_object"] = isinstance(raw_a, COSObject)
        out["sharedB_is_object"] = isinstance(raw_b, COSObject)
        out["shared_raw_same_ref"] = raw_a is raw_b
        assert isinstance(raw_a, COSObject)
        assert isinstance(raw_b, COSObject)
        from pypdfbox.cos.cos_object_key import COSObjectKey

        pooled = cos_doc.get_object_from_pool(
            COSObjectKey(raw_a.get_object_number(), raw_a.get_generation_number())
        )
        out["shared_pool_same_ref"] = pooled is raw_a
        base_a = raw_a.get_object()
        base_b = raw_b.get_object()
        out["shared_base_same"] = base_a is base_b
        out["shared_type"] = _type_tag(base_a)
        out["sharedA_object_null"] = raw_a.is_object_null()

        # --- dangling reference: /Dangling -> object 99 (no xref entry).
        raw_d = catalog.get_item("Dangling")
        out["dangling_is_object"] = isinstance(raw_d, COSObject)
        assert isinstance(raw_d, COSObject)
        base_d = raw_d.get_object()
        out["dangling_base_null"] = base_d is None
        out["dangling_object_null"] = raw_d.is_object_null()
        out["dangling_dictobj_null"] = (
            catalog.get_dictionary_object("Dangling") is None
        )

        # --- self reference: object 20 carries /Me 20 0 R.
        raw_self = catalog.get_item("SelfRef")
        assert isinstance(raw_self, COSObject)
        base_self = raw_self.get_object()
        out["self_type"] = _type_tag(base_self)
        assert isinstance(base_self, COSDictionary)
        raw_me = base_self.get_item("Me")
        out["self_me_is_object"] = isinstance(raw_me, COSObject)
        assert isinstance(raw_me, COSObject)
        out["self_cycle_same_base"] = raw_me.get_object() is base_self
        out["self_cycle_same_ref"] = raw_me is raw_self

        # --- two-object cycle: 30 <-> 31.
        obj30 = catalog.get_item("CycleHead")
        assert isinstance(obj30, COSObject)
        d30 = obj30.get_object()
        assert isinstance(d30, COSDictionary)
        obj31 = d30.get_item("Next")
        assert isinstance(obj31, COSObject)
        d31 = obj31.get_object()
        assert isinstance(d31, COSDictionary)
        back = d31.get_item("Next")
        assert isinstance(back, COSObject)
        out["cycle_closes_same_base"] = back.get_object() is d30
        out["cycle_back_same_ref"] = back is obj30

        # --- indirect ref inside an array dedups too.
        arr = catalog.get_dictionary_object("Arr")
        assert isinstance(arr, COSArray)
        arr0 = arr.get(0)
        arr1 = arr.get(1)
        out["arr_elems_same_ref"] = arr0 is arr1
        out["arr_elem_same_as_shared"] = arr0 is raw_a

        return out
    finally:
        doc.close()


@requires_oracle
def test_lazy_resolve_matches_pdfbox() -> None:
    data = _build_pdf()
    # The Java probe takes a file path; write the in-memory fixture to a temp
    # file. Close the handle before the probe reads it and unlink afterwards so
    # the path is never held open on Windows (WinError 32).
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        java_json = run_probe_text("CosLazyResolveProbe", str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)

    java = json.loads(java_json)
    py = _pypdfbox_resolve(data)
    assert py == java


def test_dedup_identity_regression() -> None:
    """Regression pin (no oracle needed): two references to the same object
    number resolve to the SAME COSObject instance and the SAME base, and a
    reference appearing twice in an array dedups to that instance too."""
    data = _build_pdf()
    py = _pypdfbox_resolve(data)
    assert py["shared_raw_same_ref"] is True
    assert py["shared_pool_same_ref"] is True
    assert py["shared_base_same"] is True
    assert py["arr_elems_same_ref"] is True
    assert py["arr_elem_same_as_shared"] is True


def test_dangling_reference_resolves_to_null_regression() -> None:
    """Regression pin: a reference to an object with no xref entry
    dereferences to null and reports ``is_object_null()`` True, and
    ``get_dictionary_object`` collapses it to ``None``."""
    data = _build_pdf()
    py = _pypdfbox_resolve(data)
    assert py["dangling_is_object"] is True
    assert py["dangling_base_null"] is True
    assert py["dangling_object_null"] is True
    assert py["dangling_dictobj_null"] is True


def test_cyclic_reference_terminates_regression() -> None:
    """Regression pin: a self reference and a two-object cycle both resolve
    without infinite recursion and close on the same shared instance."""
    data = _build_pdf()
    py = _pypdfbox_resolve(data)
    assert py["self_cycle_same_base"] is True
    assert py["self_cycle_same_ref"] is True
    assert py["cycle_closes_same_base"] is True
    assert py["cycle_back_same_ref"] is True
