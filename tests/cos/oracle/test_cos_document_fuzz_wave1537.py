"""Live PDFBox differential parity for the document-level COS container —
``org.apache.pdfbox.cos.COSDocument`` — on a FRESH / EMPTY document and around
the lifecycle (close / re-close / use-after-close). Wave 1537, agent B.

Drives the ``CosDocumentFuzzProbe`` Java oracle (which builds ``COSDocument``
instances directly — no bytes parsed) and reproduces the identical surface in
pypdfbox. Most projections are asserted byte-identical; the five upstream
``NullPointerException``-on-null-trailer corners are PINNED BOTH SIDES because
pypdfbox is deliberately hardened there (returns ``None`` / auto-creates a
trailer instead of crashing) — see ``CHANGES.md`` wave 1537.

Real bugs this wave aligned to upstream (the probe proved the divergence):
* ``set_version`` / ``set_start_xref`` / ``set_highest_xref_object_number`` are
  now bare assignments with no validation — upstream stores zero / negative /
  downgrade values verbatim;
* ``get_object_from_pool(None)`` returns ``None`` rather than raising —
  upstream's ``computeIfAbsent(null, …)`` yields ``null``.
"""

from __future__ import annotations

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_document import COSDocument
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from tests.oracle.harness import requires_oracle, run_probe_text

# Keys where upstream throws an NPE (null trailer) but pypdfbox is intentionally
# hardened. The Java side is pinned to ``ERR:NullPointerException``; the Python
# side is asserted to the documented hardened value below.
_HARDENED_DIVERGENCES = {
    "docIdNoTrailer": ("ERR:NullPointerException", "null"),
    "encDictNoTrailer": ("ERR:NullPointerException", "null"),
    # pypdfbox auto-creates a trailer instead of NPE.
    "setDocIdNoTrailer": ("ERR:NullPointerException", "nonnull"),
    "setEncNoTrailer": ("ERR:NullPointerException", "nonnull"),
    # pypdfbox accepts ``set_trailer(None)`` — trailer ends up null.
    "setTrailerNull": ("ERR:NullPointerException", "null"),
}


def _parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        key, _, value = raw.partition("=")
        out[key] = value
    return out


def _nn(obj: object) -> str:
    return "null" if obj is None else "nonnull"


def _float(value: float) -> str:
    # Match Java's Float.toString for the values this probe emits (1.4, 1.3,
    # 1.2, 0.0, -1.0, 1.4-after-close). All have exact short decimal reprs.
    return f"{value:.1f}"


def _py_projection() -> dict[str, str]:
    out: dict[str, str] = {}

    out["version"] = _float(COSDocument().get_version())
    out["trailer"] = _nn(COSDocument().get_trailer())
    out["isEncrypted"] = str(COSDocument().is_encrypted()).lower()
    out["isDecrypted"] = str(COSDocument().is_decrypted()).lower()
    out["isClosed"] = str(COSDocument().is_closed()).lower()
    out["isXRefStream"] = str(COSDocument().is_xref_stream()).lower()
    out["hasHybridXRef"] = str(COSDocument().has_hybrid_xref()).lower()
    out["highestXRef"] = str(COSDocument().get_highest_xref_object_number())
    out["startXref"] = str(COSDocument().get_start_xref())
    out["linearized"] = _nn(COSDocument().get_linearized_dictionary())

    # null-trailer accessors — pypdfbox hardened values.
    out["docIdNoTrailer"] = _nn(COSDocument().get_document_id())
    out["encDictNoTrailer"] = _nn(COSDocument().get_encryption_dictionary())
    d = COSDocument()
    d.set_document_id(COSArray())
    out["setDocIdNoTrailer"] = _nn(d.get_trailer())
    d = COSDocument()
    d.set_encryption_dictionary(COSDictionary())
    out["setEncNoTrailer"] = _nn(d.get_trailer())
    d = COSDocument()
    d.set_trailer(COSDictionary())
    d.set_trailer(None)
    out["setTrailerNull"] = _nn(d.get_trailer())

    out["byTypeAbsentSize"] = str(
        len(COSDocument().get_objects_by_type(COSName.get_pdf_name("Nope")))
    )

    o = COSDocument().get_object_from_pool(COSObjectKey(5, 0))
    out["poolFresh"] = (
        "null"
        if o is None
        else f"n={o.get_object_number()},g={o.get_generation_number()}"
    )
    d = COSDocument()
    a = d.get_object_from_pool(COSObjectKey(5, 0))
    b = d.get_object_from_pool(COSObjectKey(5, 0))
    out["poolSame"] = str(a is b).lower()
    out["poolNull"] = _nn(COSDocument().get_object_from_pool(None))

    d = COSDocument()
    d.set_version(1.7)
    d.set_version(1.3)
    out["downgrade"] = _float(d.get_version())
    d = COSDocument()
    d.set_version(1.2)
    out["downgradeFromDefault"] = _float(d.get_version())
    d = COSDocument()
    d.set_version(0.0)
    out["setVerZero"] = _float(d.get_version())
    d = COSDocument()
    d.set_version(-1.0)
    out["setVerNeg"] = _float(d.get_version())
    d = COSDocument()
    d.set_highest_xref_object_number(-5)
    out["highestNeg"] = str(d.get_highest_xref_object_number())
    d = COSDocument()
    d.set_start_xref(-3)
    out["startNeg"] = str(d.get_start_xref())

    d = COSDocument()
    d.close()
    c1 = d.is_closed()
    d.close()
    c2 = d.is_closed()
    out["doubleClose"] = f"{str(c1).lower()},{str(c2).lower()}"
    d = COSDocument()
    d.close()
    out["poolAfterClose"] = _nn(d.get_object_from_pool(COSObjectKey(1, 0)))
    d = COSDocument()
    d.close()
    out["byTypeAfterClose"] = str(
        len(d.get_objects_by_type(COSName.get_pdf_name("Page")))
    )
    d = COSDocument()
    d.close()
    out["versionAfterClose"] = _float(d.get_version())

    d = COSDocument()
    d.set_decrypted()
    out["afterSetDecrypted"] = str(d.is_decrypted()).lower()

    return out


@requires_oracle
def test_cos_document_fuzz_matches_pdfbox() -> None:
    java = _parse(run_probe_text("CosDocumentFuzzProbe"))
    py = _py_projection()

    # Same set of keys on both sides.
    assert set(py) == set(java)

    for key in java:
        if key in _HARDENED_DIVERGENCES:
            java_pin, py_pin = _HARDENED_DIVERGENCES[key]
            assert java[key] == java_pin, f"{key}: upstream changed: {java[key]!r}"
            assert py[key] == py_pin, f"{key}: pypdfbox changed: {py[key]!r}"
        else:
            assert py[key] == java[key], f"{key}: {py[key]!r} != {java[key]!r}"
