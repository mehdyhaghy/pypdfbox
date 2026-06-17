"""Live PDFBox differential parity for the COS object graph.

Compares the canonical COS-graph fingerprint pypdfbox parses a PDF into against
the one Apache PDFBox 3.0.7 produces from the same file (via the
``CosDumpProbe`` Java probe). This is a *parsing-fidelity* check: it asserts the
two parsers register the same indirect objects, with the same type structure,
the same dictionary keys, the same cross-references, and the same scalar values
(integers, names, IEEE-754 float32 bits, string byte-lengths, stream raw
lengths).

Canonical format (one LF-terminated line per indirect object, sorted by
``(objNum, genNum)``)::

    <objNum> <genNum>: <typetag>

Type-tag grammar (identical on both sides — see ``CosDumpProbe.java``)::

    null          -> null
    boolean       -> bool(true) / bool(false)
    integer       -> int(<decimal>)
    float         -> real(<float32-bits-hex>)   # repr-independent; see below
    name          -> name(/Foo)
    string        -> str(len=<byte-count>)       # raw bytes too brittle to dump
    array         -> array[<elt>,<elt>,...]
    dictionary    -> dict{/A->t,/B->t,...}       # keys sorted, /Length omitted
                                                 #   for streams (reported as rawlen)
    stream        -> stream{...}(rawlen=<n>)     # raw (encoded) body byte length
    reference     -> ref(N G)                    # NOT followed; target gets its
                                                 #   own top-level line

Why float32 bits instead of a decimal string: Java's ``Float.toString`` and
Python's float formatting disagree on shortest-round-trip decimal reprs, but the
underlying IEEE-754 single-precision bit pattern is identical (pypdfbox's
``COSFloat`` coerces every value through float32, matching Java's ``float``).
Comparing bits is therefore repr-independent yet still flags any value that
parsed to a *different* float32 (a real fidelity bug).

Normalizations applied (BENIGN, not fidelity workarounds):

  - ``/Length`` is omitted from stream dicts (reported separately as
    ``rawlen``) so a direct-value /Length and an indirect-reference /Length
    compare equal.
  - The pypdfbox side calls ``initial_parse()`` after ``parse()`` so it
    reaches the same lifecycle state Java's ``Loader.loadPDF`` does. Java's
    ``PDFParser.parse()`` calls ``initialParse()`` (lenient ``/Type /Catalog``
    repair on a /Root dict that omits it); pypdfbox deliberately defers that
    out of ``parse()``. The COS graph parses identically either way — only
    *when* the repair runs differs (exercised by ``MissingCatalog.pdf``).
"""

from __future__ import annotations

import struct
from contextlib import suppress
from pathlib import Path

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.cos.cos_boolean import COSBoolean
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.cos.cos_string import COSString
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdfparser.parse_error import PDFParseError
from pypdfbox.pdfparser.pdf_parser import PDFParser
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

# A spread of parser code paths:
#   - traditional cross-reference table (rot*.pdf, hand-built simple PDFs)
#   - cross-reference stream + object streams (objstm) — PDF 1.5+
#   - linearized files (/Linearized first object) with xref streams
#   - incremental updates / multiple xref sections (PDFBOX-* corpus files)
#   - a file with a deliberately missing catalog (recovery path)
_FIXTURES_UNDER_TEST: list[str] = [
    # traditional xref, tiny hand-built graphs
    "multipdf/rot0.pdf",
    "multipdf/rot90.pdf",
    "multipdf/PDFBoxLegacyMerge-SameMerged.pdf",
    # object streams / xref streams
    "pdmodel/interactive/form/AcroFormsBasicFields.pdf",
    "pdmodel/interactive/form/AlignmentTests.pdf",
    "multipdf/PDFBOX-6049-Source.pdf",
    "multipdf/PDFBOX-4417-001031.pdf",
    # linearized + xref stream
    "multipdf/PDFBOX-5762-722238.pdf",
    "pdmodel/interactive/form/AcroFormsRotation.pdf",
    "pdmodel/interactive/annotation/AnnotationTypes.pdf",
    # PDF/A, more complex graph
    "multipdf/PDFA3A.pdf",
    # missing catalog — recovery / brute-force-ish path
    "pdfparser/MissingCatalog.pdf",
]


def _float32_bits_hex(value: float) -> str:
    """Bare lowercase hex of the IEEE-754 float32 bit pattern, no ``0x``,
    no leading zeros — matching Java ``Integer.toHexString(
    Float.floatToIntBits(f))``."""
    bits = struct.unpack(">I", struct.pack(">f", value))[0]
    return f"{bits:x}"


def _type_tag(base: COSBase | None) -> str:
    """Canonical type-tag for a COS value. Mirrors ``CosDumpProbe.typeTag``
    exactly. Indirect references are rendered as ``ref(N G)`` and NOT
    dereferenced (the referenced object appears on its own top-level line)."""
    if base is None:
        return "null"
    if isinstance(base, COSObject):
        return f"ref({base.get_object_number()} {base.get_generation_number()})"
    if isinstance(base, COSNull):
        return "null"
    if isinstance(base, COSBoolean):
        return f"bool({'true' if base.get_value() else 'false'})"
    if isinstance(base, COSInteger):
        return f"int({base.long_value()})"
    if isinstance(base, COSFloat):
        return f"real({_float32_bits_hex(base.float_value())})"
    if isinstance(base, COSName):
        return f"name(/{base.get_name()})"
    if isinstance(base, COSString):
        return f"str(len={len(base.get_bytes())})"
    # COSStream is a subclass of COSDictionary — test it first.
    if isinstance(base, COSStream):
        return f"stream{_dict_body(base)}(rawlen={_raw_len(base)})"
    if isinstance(base, COSArray):
        parts = [_type_tag(base.get(i)) for i in range(base.size())]
        return "array[" + ",".join(parts) + "]"
    if isinstance(base, COSDictionary):
        return "dict" + _dict_body(base)
    return f"unknown({type(base).__name__})"


def _dict_body(d: COSDictionary) -> str:
    """``{/Key->typetag,...}`` with keys sorted by name. The stream-only
    ``/Length`` entry is skipped (its info is reported as ``rawlen``) so a
    direct-value /Length and an indirect-reference /Length compare equal."""
    is_stream = isinstance(d, COSStream)
    keys = sorted(d.key_set(), key=lambda n: n.get_name())
    parts: list[str] = []
    for k in keys:
        if is_stream and k == COSName.LENGTH:
            continue
        # get_item returns the RAW entry (a COSObject ref stays a ref).
        parts.append(f"/{k.get_name()}->{_type_tag(d.get_item(k))}")
    return "{" + ",".join(parts) + "}"


def _raw_len(stream: COSStream) -> int:
    """Raw (encoded) body byte length — matches the Java probe reading
    ``createRawInputStream`` to EOF."""
    try:
        return len(stream.get_raw_data())
    except Exception:
        return -1


def _pypdfbox_dump(path: Path) -> str:
    """Produce the canonical COS-graph fingerprint pypdfbox parses ``path``
    into — same format the Java ``CosDumpProbe`` emits.

    Parses via :class:`PDFParser` directly (rather than ``PDDocument.load``)
    and then calls ``initial_parse()``. This reaches the same document
    lifecycle state Java's ``Loader.loadPDF`` reaches: upstream's
    ``PDFParser.parse()`` invokes ``initialParse()`` (which performs the
    lenient ``/Type /Catalog`` repair when the trailer's /Root dictionary
    omits it). pypdfbox deliberately defers ``initial_parse()`` out of
    ``parse()`` (documented lazy-error contract in pdf_parser.py), so to
    compare apples-to-apples we invoke it here. The underlying COS object
    graph parses identically either way — only the catalog-type repair
    differs, and only by *when* it runs. This is a benign lifecycle
    normalization, not a fidelity workaround (see module docstring)."""
    data = path.read_bytes()
    parser = PDFParser(RandomAccessReadBuffer(data))
    doc = parser.parse()
    try:
        with suppress(PDFParseError):
            parser.initial_parse()
        lines: list[str] = []
        # The xref table is the authoritative set of indirect objects (same
        # source the Java probe walks). Sort by (objNum, genNum).
        keys = sorted(
            doc.get_xref_table().keys(),
            key=lambda k: (k.get_number(), k.get_generation()),
        )
        for key in keys:
            obj = doc.get_object_from_pool(key)
            try:
                resolved = obj.get_object()
            except Exception:
                resolved = None
            lines.append(
                f"{key.get_number()} {key.get_generation()}: {_type_tag(resolved)}"
            )
        return "".join(line + "\n" for line in lines)
    finally:
        doc.close()


@requires_oracle
@pytest.mark.parametrize("rel", _FIXTURES_UNDER_TEST)
def test_cos_graph_matches_pdfbox(rel: str) -> None:
    fixture = _FIXTURES / rel
    assert fixture.is_file(), f"missing fixture: {fixture}"
    java = run_probe_text("CosDumpProbe", str(fixture))
    py = _pypdfbox_dump(fixture)
    assert py == java
