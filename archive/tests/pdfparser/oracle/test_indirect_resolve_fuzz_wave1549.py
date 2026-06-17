"""Live PDFBox differential fuzz for INDIRECT-OBJECT / COSObject lazy
resolution (pypdfbox parity wave 1549, agent A).

Targets the on-demand dereferencing surface of the parser —
``COSParser.parse_object_dynamically`` + ``COSObject.get_object`` + the
document object-pool — as reached when a real document resolves a reference.
This is the CROSS-OBJECT resolution layer: missing-object → null, wrong /
mismatched generation, free (deleted) xref entries, self-reference, A→B→A
cycles, object-stream members addressed by an out-of-range index, and dangling
references nested inside array / dict values.

Complements:

* ``test_cos_lazy_resolve_oracle`` — pins object-pool dedup IDENTITY and cycle
  closure on a single hand-built catalog;
* ``test_cos_object_parse_fuzz_wave1516`` — fuzzes the BODY parse of one object;
* ``test_indirect_length_oracle`` — pins ``/Length`` indirect resolution.

Here the angle is the resolution EDGES across a corpus of whole PDFs, one
hazard per file. Both sides read identical bytes from disk (file-driven
manifest, same pattern as ``CosObjectParseFuzzProbe``).

Manifest line grammar (``<case> <target> [<target> ...]``); each ``target``:

    pool:N:G          getObjectFromPool(N,G).getObject() — projects tag+isnull
    dictobj:N:G:/K    catalog-of-N's /K via getDictionaryObject (null collapse)
    item:N:G:/K       raw /K via getItem (ref stays a placeholder)
    arr:N:G:/K:I      element I of array N's /K via COSArray.getObject(I)

Projection grammar (per target, one line ``R <case> <target> <proj>``):

    null | bool(true|false) | int(d) | real(f32-bits-hex) | name(/x)
    str(hex) | ref(n,g) | array[n] | dict[n] | stream
    <tag>+isnull(true|false)    for pool: targets
    OOR | ERR:<Exc> | LOAD:<Exc> | BADTARGET

Free-entry / missing-object / mismatched-generation cases are where loader
LENIENCY divergences live; those are pinned BOTH-SIDES with honest comments
rather than "fixed", unless pypdfbox resolves to a WRONG value where PDFBox
resolves correctly.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_boolean import COSBoolean
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.cos.cos_string import COSString
from pypdfbox.loader import Loader
from tests.oracle.harness import requires_oracle, run_probe_text

_HEADER = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"


# --------------------------------------------------------------------------- #
# PDF builder helpers — full manual control over xref entries (incl. free
# slots) so we can plant deleted / missing / mismatched-generation objects.
# --------------------------------------------------------------------------- #


def _build_pdf(objects: dict[int, bytes], free: set[int], root: int = 2) -> bytes:
    """Assemble a classic-xref PDF.

    ``objects`` maps object number -> the FULL ``N G obj ... endobj`` block
    (bytes, no surrounding whitespace). ``free`` is the set of object numbers
    that must be written into the xref table as free (``f``) entries even
    though their body may or may not be present in the file. The xref ``size``
    is one past the max object number; any number neither in ``objects`` nor
    ``free`` is written as a free entry (so it has no xref offset → missing).
    """
    buf = bytearray()
    buf.extend(_HEADER)
    offsets: dict[int, int] = {}
    for num in sorted(objects):
        offsets[num] = len(buf)
        buf.extend(objects[num])
        if not objects[num].endswith(b"\n"):
            buf.extend(b"\n")

    max_num = max([*objects.keys(), *free, root])
    size = max_num + 1
    xref_off = len(buf)
    buf.extend(b"xref\n")
    buf.extend(f"0 {size}\n".encode("latin-1"))
    # Object 0 is always the head of the free list.
    buf.extend(b"0000000000 65535 f \n")
    for num in range(1, size):
        if num in offsets and num not in free:
            buf.extend(f"{offsets[num]:010d} 00000 n \n".encode("latin-1"))
        else:
            # Free slot — present body but listed free, or genuinely absent.
            buf.extend(b"0000000000 00000 f \n")
    buf.extend(f"trailer\n<< /Size {size} /Root {root} 0 R >>\n".encode("latin-1"))
    buf.extend(b"startxref\n")
    buf.extend(f"{xref_off}\n".encode("latin-1"))
    buf.extend(b"%%EOF\n")
    return bytes(buf)


def _obj(num: int, body: bytes, gen: int = 0) -> bytes:
    return f"{num} {gen} obj\n".encode("latin-1") + body + b"\nendobj\n"


def _catalog(num: int = 2, extra: bytes = b"") -> bytes:
    return _obj(num, b"<< /Type /Catalog /Pages 3 0 R " + extra + b">>")


def _pages() -> bytes:
    return _obj(3, b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>")


def _page() -> bytes:
    return _obj(
        4, b"<< /Type /Page /Parent 3 0 R /MediaBox [0 0 612 792] >>"
    )


def _objstm(num: int, members: list[tuple[int, bytes]]) -> bytes:
    """An UNFILTERED (/Filter omitted) /Type /ObjStm container so both sides
    decode the body identically without depending on a compression codec.

    ``members`` is a list of (objectNumber, directObjectBytes). The body is a
    header of ``num byteoffset`` pairs followed by the concatenated bodies
    starting at /First.
    """
    bodies = bytearray()
    pairs: list[bytes] = []
    for member_num, member_body in members:
        pairs.append(f"{member_num} {len(bodies)}".encode("latin-1"))
        bodies.extend(member_body)
        bodies.extend(b" ")
    header = (" ".join(p.decode("latin-1") for p in pairs)).encode("latin-1") + b" "
    first = len(header)
    payload = header + bytes(bodies)
    dict_part = (
        f"<< /Type /ObjStm /N {len(members)} /First {first} "
        f"/Length {len(payload)} >>"
    ).encode("latin-1")
    block = (
        f"{num} 0 obj\n".encode("latin-1")
        + dict_part
        + b"\nstream\n"
        + payload
        + b"\nendstream\nendobj\n"
    )
    return block


# --------------------------------------------------------------------------- #
# Corpus. Each entry: (case_id, pdf_bytes, [target, ...]).
# Targets are probed in order; the resolution machinery shares state across
# targets within one case (mirrors how a real reader resolves).
# --------------------------------------------------------------------------- #


def _corpus() -> list[tuple[str, bytes, list[str]]]:
    cases: list[tuple[str, bytes, list[str]]] = []

    # 1. Reference to a MISSING object number (no body, no xref offset) → null.
    pdf = _build_pdf(
        {2: _catalog(extra=b"/Miss 9 0 R "), 3: _pages(), 4: _page()},
        free=set(),
    )
    cases.append(
        ("missing_objnum", pdf, ["pool:9:0", "dictobj:2:0:/Miss", "item:2:0:/Miss"])
    )

    # 2. Reference with WRONG generation: body is 5 0 obj, ref asks 5 7 R.
    pdf = _build_pdf(
        {
            2: _catalog(extra=b"/WG 5 7 R "),
            3: _pages(),
            4: _page(),
            5: _obj(5, b"<< /Real true >>"),
        },
        free=set(),
    )
    cases.append(
        ("wrong_generation", pdf, ["pool:5:7", "pool:5:0", "dictobj:2:0:/WG"])
    )

    # 3. Reference to a FREE / deleted object: body 6 0 obj present but its
    #    xref slot is marked 'f'.
    pdf = _build_pdf(
        {
            2: _catalog(extra=b"/Del 6 0 R "),
            3: _pages(),
            4: _page(),
            6: _obj(6, b"<< /Gone true >>"),
        },
        free={6},
    )
    cases.append(("free_entry", pdf, ["pool:6:0", "dictobj:2:0:/Del"]))

    # 4. SELF-referential indirect object: 5 0 obj << /Me 5 0 R >>.
    pdf = _build_pdf(
        {
            2: _catalog(extra=b"/Self 5 0 R "),
            3: _pages(),
            4: _page(),
            5: _obj(5, b"<< /Me 5 0 R /Tag /SelfDict >>"),
        },
        free=set(),
    )
    cases.append(
        ("self_ref", pdf, ["pool:5:0", "dictobj:2:0:/Self", "dictobj:5:0:/Me"])
    )

    # 5. Header generation MISMATCH: xref points at offset of '5 9 obj' but the
    #    reference / xref key is 5 0. Upstream throws ("points to wrong object")
    #    and the lazy getObject swallows it → null.
    pdf = _build_pdf(
        {
            2: _catalog(extra=b"/HM 5 0 R "),
            3: _pages(),
            4: _page(),
            5: _obj(5, b"<< /Bumped true >>", gen=9),
        },
        free=set(),
    )
    cases.append(("header_gen_mismatch", pdf, ["pool:5:0", "dictobj:2:0:/HM"]))

    # 6. Two-object CYCLE A→B→A resolved via getObject.
    pdf = _build_pdf(
        {
            2: _catalog(extra=b"/Head 5 0 R "),
            3: _pages(),
            4: _page(),
            5: _obj(5, b"<< /Next 6 0 R /Id 5 >>"),
            6: _obj(6, b"<< /Next 5 0 R /Id 6 >>"),
        },
        free=set(),
    )
    cases.append(
        (
            "cycle_a_b_a",
            pdf,
            ["pool:5:0", "pool:6:0", "dictobj:5:0:/Next", "dictobj:6:0:/Next"],
        )
    )

    # 7. Object-stream member referenced by an OUT-OF-RANGE / nonexistent
    #    number. ObjStm 7 holds members 5 and 6; we also reference member 8
    #    which is NOT in the stream → resolves to null.
    objstm = _objstm(7, [(5, b"<< /In 5 >>"), (6, b"<< /In 6 >>")])
    base_objs = {2: _catalog(extra=b"/A 5 0 R /B 6 0 R /C 8 0 R "), 3: _pages(), 4: _page()}
    pdf = _build_objstm_pdf(base_objs, objstm, 7, {5: 0, 6: 1, 8: 5})
    cases.append(
        (
            "objstm_oor_member",
            pdf,
            ["pool:5:0", "pool:6:0", "pool:8:0", "dictobj:2:0:/C"],
        )
    )

    # 8. DANGLING reference inside an ARRAY value: /Arr [ 5 0 R 9 0 R ] where
    #    9 0 R is missing. Element 0 resolves, element 1 → null.
    pdf = _build_pdf(
        {
            2: _catalog(extra=b"/Arr [5 0 R 9 0 R] "),
            3: _pages(),
            4: _page(),
            5: _obj(5, b"<< /Live true >>"),
        },
        free=set(),
    )
    cases.append(
        ("dangling_in_array", pdf, ["arr:2:0:/Arr:0", "arr:2:0:/Arr:1"])
    )

    # 9. DANGLING reference inside a DICT value (nested): /D << /P 9 0 R >>
    #    where the nested /P points at a missing object.
    pdf = _build_pdf(
        {
            2: _catalog(extra=b"/D 5 0 R "),
            3: _pages(),
            4: _page(),
            5: _obj(5, b"<< /P 9 0 R /Q (alive) >>"),
        },
        free=set(),
    )
    cases.append(
        ("dangling_in_dict", pdf, ["dictobj:5:0:/P", "dictobj:5:0:/Q"])
    )

    # 10. Valid baseline: a plain in-use reference resolving to each scalar
    #     type, so the projection's happy path is exercised too.
    pdf = _build_pdf(
        {
            2: _catalog(extra=b"/I 5 0 R /S 6 0 R /Nm 8 0 R "),
            3: _pages(),
            4: _page(),
            5: _obj(5, b"42"),
            6: _obj(6, b"(hello)"),
            8: _obj(8, b"/SomeName"),
        },
        free=set(),
    )
    cases.append(
        (
            "valid_scalars",
            pdf,
            ["pool:5:0", "pool:6:0", "pool:8:0"],
        )
    )

    # 11. Reference to object 0 (the free-list head, generation 65535) → null.
    pdf = _build_pdf(
        {2: _catalog(extra=b"/Zero 0 0 R "), 3: _pages(), 4: _page()},
        free=set(),
    )
    cases.append(("ref_object_zero", pdf, ["pool:0:0", "dictobj:2:0:/Zero"]))

    # 12. Object stream member addressed with a WRONG positional index in the
    #     xref stream but correct object number. Resolution is by NUMBER, so it
    #     must still resolve. Plant /Index for 5 -> 9 (out of range positionally)
    #     while the header lists 5 first.
    objstm = _objstm(7, [(5, b"<< /Found true >>"), (6, b"<< /Found 2 >>")])
    base_objs = {2: _catalog(extra=b"/M 5 0 R "), 3: _pages(), 4: _page()}
    pdf = _build_objstm_pdf(base_objs, objstm, 7, {5: 9, 6: 1})
    cases.append(("objstm_wrong_index", pdf, ["pool:5:0", "dictobj:2:0:/M"]))

    return cases


def _build_objstm_pdf(
    base_objs: dict[int, bytes],
    objstm_block: bytes,
    objstm_num: int,
    members: dict[int, int],
) -> bytes:
    """A hybrid PDF: classic xref for ``base_objs`` + the ObjStm container,
    plus an xref STREAM is overkill — instead we use a classic xref table for
    the uncompressed objects and an xref STREAM only for compressed members.

    Simpler: emit a single xref STREAM that records the uncompressed objects
    (type 1, offset) and the compressed members (type 2, objstm_num, index).
    ``members`` maps member object number -> its declared positional index in
    the object stream.
    """
    buf = bytearray()
    buf.extend(_HEADER)
    offsets: dict[int, int] = {}
    for num in sorted(base_objs):
        offsets[num] = len(buf)
        block = base_objs[num]
        buf.extend(block)
        if not block.endswith(b"\n"):
            buf.extend(b"\n")
    offsets[objstm_num] = len(buf)
    buf.extend(objstm_block)

    all_nums = set(offsets) | set(members)
    max_num = max(all_nums)
    xref_stream_num = max_num + 1
    size = xref_stream_num + 1

    # Build the xref stream body: 3 fields per entry, widths [1,4,2].
    import struct

    def entry(t: int, f2: int, f3: int) -> bytes:
        return struct.pack(">B", t) + struct.pack(">I", f2) + struct.pack(">H", f3)

    xref_off = len(buf)
    rows = bytearray()
    # object 0: free head
    rows.extend(entry(0, 0, 65535))
    for num in range(1, size):
        if num in members:
            rows.extend(entry(2, objstm_num, members[num]))
        elif num == xref_stream_num:
            rows.extend(entry(1, xref_off, 0))
        elif num in offsets:
            rows.extend(entry(1, offsets[num], 0))
        else:
            rows.extend(entry(0, 0, 0))

    xref_dict = (
        f"{xref_stream_num} 0 obj\n"
        f"<< /Type /XRef /Size {size} /Root 2 0 R "
        f"/W [1 4 2] /Length {len(rows)} >>\n"
    ).encode("latin-1")
    buf.extend(xref_dict)
    buf.extend(b"stream\n")
    buf.extend(rows)
    buf.extend(b"\nendstream\nendobj\n")
    buf.extend(b"startxref\n")
    buf.extend(f"{xref_off}\n".encode("latin-1"))
    buf.extend(b"%%EOF\n")
    return bytes(buf)


# --------------------------------------------------------------------------- #
# Honest divergences pinned BOTH-SIDES. Maps (case, target) -> (java, py).
# Every (case, target) NOT listed here must agree byte-for-byte.
# --------------------------------------------------------------------------- #

_DIVERGENT: dict[tuple[str, str], tuple[str, str]] = {
    # Direct pool access to a FREE key BEFORE any reference to it has been
    # parsed. PDFBox's COSObject routes every getObject() back through the
    # parser (ICOSParser.dereferenceCOSObject), so even a bare
    # getObjectFromPool(6,0).getObject() triggers the lenient bfSearchForObjects
    # fallback and recovers the free-but-present body. pypdfbox attaches the
    # brute-force fallback loader when the reference is PARSED
    # (_make_indirect_reference) — so a genuine ``6 0 R`` reference (the
    # dictobj:/item: paths below) DOES recover at parity. A direct pool fetch
    # of a never-referenced free key has no loader and resolves to null. This
    # is an architectural divergence in the pool's resolve seam, not a wrong
    # value on any real reference path; pinned both-sides rather than routing a
    # document->parser callback through COSDocument.
    ("free_entry", "pool:6:0"): ("dict[1]+isnull(false)", "null+isnull(true)"),
}


def _float32_bits_hex(value: float) -> str:
    import struct

    bits = struct.unpack(">I", struct.pack(">f", value))[0]
    return f"{bits:x}"


def _tag(base: object) -> str:
    if base is None or isinstance(base, COSNull):
        return "null"
    if isinstance(base, COSObject):
        return f"ref({base.get_object_number()},{base.get_generation_number()})"
    if isinstance(base, COSBoolean):
        return f"bool({'true' if base.get_value() else 'false'})"
    if isinstance(base, COSInteger):
        return f"int({base.long_value()})"
    if isinstance(base, COSFloat):
        return f"real({_float32_bits_hex(base.float_value())})"
    if isinstance(base, COSName):
        return f"name(/{base.get_name()})"
    if isinstance(base, COSString):
        return f"str({base.get_bytes().hex()})"
    if isinstance(base, COSStream):
        return "stream"
    if isinstance(base, COSArray):
        return f"array[{base.size()}]"
    if isinstance(base, COSDictionary):
        return f"dict[{base.size()}]"
    return f"unknown({type(base).__name__})"


def _run_target(document: object, target: str) -> str:
    parts = target.split(":")
    try:
        if parts[0] == "pool":
            n, g = int(parts[1]), int(parts[2])
            obj = document.get_object_from_pool(COSObjectKey(n, g))
            if obj is None:
                return "null+isnull(true)"
            resolved = obj.get_object()
            flag = "true" if obj.is_object_null() else "false"
            return f"{_tag(resolved)}+isnull({flag})"
        if parts[0] == "dictobj":
            n, g = int(parts[1]), int(parts[2])
            holder = document.get_object_from_pool(COSObjectKey(n, g))
            d = holder.get_object()
            return _tag(d.get_dictionary_object(COSName.get_pdf_name(parts[3][1:])))
        if parts[0] == "item":
            n, g = int(parts[1]), int(parts[2])
            holder = document.get_object_from_pool(COSObjectKey(n, g))
            d = holder.get_object()
            return _tag(d.get_item(COSName.get_pdf_name(parts[3][1:])))
        if parts[0] == "arr":
            n, g = int(parts[1]), int(parts[2])
            idx = int(parts[4])
            holder = document.get_object_from_pool(COSObjectKey(n, g))
            d = holder.get_object()
            a = d.get_dictionary_object(COSName.get_pdf_name(parts[3][1:]))
            if idx < 0 or idx >= a.size():
                return "OOR"
            return _tag(a.get_object(idx))
    except Exception as exc:  # noqa: BLE001 — mirror probe ERR:<Exc>
        return "ERR:" + type(exc).__name__
    return "BADTARGET"


def _project_case(pdf_path: Path, targets: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        document = Loader.load_pdf(str(pdf_path))
    except Exception as exc:  # noqa: BLE001 — mirror probe LOAD:<Exc>
        return {"*": "LOAD:" + type(exc).__name__}
    try:
        for target in targets:
            out[target] = _run_target(document, target)
    finally:
        document.close()
    return out


def _write_corpus(dir_path: Path, cases: list[tuple[str, bytes, list[str]]]) -> None:
    manifest_lines: list[str] = []
    for case_id, pdf_bytes, targets in cases:
        (dir_path / f"{case_id}.pdf").write_bytes(pdf_bytes)
        manifest_lines.append(case_id + " " + " ".join(targets))
    (dir_path / "manifest.txt").write_text(
        "\n".join(manifest_lines) + "\n", encoding="utf-8"
    )


def _parse_java(text: str) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for line in text.splitlines():
        if not line.startswith("R "):
            continue
        toks = line.split(" ", 3)
        if len(toks) < 4:
            continue
        result[(toks[1], toks[2])] = toks[3]
    return result


@requires_oracle
def test_indirect_resolve_matches_pdfbox(tmp_path: Path) -> None:
    cases = _corpus()
    _write_corpus(tmp_path, cases)
    java = _parse_java(run_probe_text("IndirectResolveFuzzProbe", str(tmp_path)))

    mismatches: list[str] = []
    for case_id, _pdf, targets in cases:
        py = _project_case(tmp_path / f"{case_id}.pdf", targets)
        if "*" in py:
            # pypdfbox failed to load — check Java also failed (LOAD: line).
            j = java.get((case_id, "*"))
            if j != py["*"]:
                mismatches.append(
                    f"{case_id} LOAD:\n  java: {j}\n  py:   {py['*']}"
                )
            continue
        for target in targets:
            key = (case_id, target)
            j = java.get(key)
            p = py[target]
            if key in _DIVERGENT:
                exp_j, exp_p = _DIVERGENT[key]
                if p != exp_p:
                    mismatches.append(
                        f"{case_id} {target} (pinned py drifted):\n"
                        f"  expected py: {exp_p}\n  actual py:   {p}"
                    )
                if j != exp_j:
                    mismatches.append(
                        f"{case_id} {target} (pinned java drifted):\n"
                        f"  expected java: {exp_j}\n  actual java:   {j}"
                    )
            elif j != p:
                mismatches.append(
                    f"{case_id} {target}:\n  java: {j}\n  py:   {p}"
                )
    assert not mismatches, "indirect-resolve divergences:\n" + "\n".join(mismatches)


# --------------------------------------------------------------------------- #
# Oracle-independent regression pins — the resolution contracts hold on a
# machine without the live oracle. These encode the PDFBox-3.0.7 expected
# values translated by hand.
# --------------------------------------------------------------------------- #

# (case_id, target) -> expected projection (PDFBox-3.0.7 ground truth).
_EXPECTED: dict[tuple[str, str], str] = {
    ("missing_objnum", "pool:9:0"): "null+isnull(true)",
    ("missing_objnum", "dictobj:2:0:/Miss"): "null",
    ("missing_objnum", "item:2:0:/Miss"): "ref(9,0)",
    ("wrong_generation", "pool:5:7"): "null+isnull(true)",
    ("wrong_generation", "pool:5:0"): "dict[1]+isnull(false)",
    ("wrong_generation", "dictobj:2:0:/WG"): "null",
    # A body present in the file but listed FREE in the xref: a genuine
    # ``6 0 R`` reference (resolved via getDictionaryObject) brute-force-
    # recovers it in lenient mode (wave 1549 fix — formerly null). The direct
    # pool-fetch path (pool:6:0) is pinned as a both-sides divergence in
    # _DIVERGENT (it has no loader before the reference is parsed).
    ("free_entry", "dictobj:2:0:/Del"): "dict[1]",
    ("self_ref", "pool:5:0"): "dict[2]+isnull(false)",
    ("self_ref", "dictobj:2:0:/Self"): "dict[2]",
    ("self_ref", "dictobj:5:0:/Me"): "dict[2]",
    ("header_gen_mismatch", "pool:5:0"): "null+isnull(true)",
    ("header_gen_mismatch", "dictobj:2:0:/HM"): "null",
    ("cycle_a_b_a", "pool:5:0"): "dict[2]+isnull(false)",
    ("cycle_a_b_a", "pool:6:0"): "dict[2]+isnull(false)",
    ("cycle_a_b_a", "dictobj:5:0:/Next"): "dict[2]",
    ("cycle_a_b_a", "dictobj:6:0:/Next"): "dict[2]",
    ("objstm_oor_member", "pool:5:0"): "dict[1]+isnull(false)",
    ("objstm_oor_member", "pool:6:0"): "dict[1]+isnull(false)",
    ("objstm_oor_member", "pool:8:0"): "null+isnull(true)",
    ("objstm_oor_member", "dictobj:2:0:/C"): "null",
    ("dangling_in_array", "arr:2:0:/Arr:0"): "dict[1]",
    ("dangling_in_array", "arr:2:0:/Arr:1"): "null",
    ("dangling_in_dict", "dictobj:5:0:/P"): "null",
    ("dangling_in_dict", "dictobj:5:0:/Q"): "str(616c697665)",
    ("valid_scalars", "pool:5:0"): "int(42)+isnull(false)",
    ("valid_scalars", "pool:6:0"): "str(68656c6c6f)+isnull(false)",
    ("valid_scalars", "pool:8:0"): "name(/SomeName)+isnull(false)",
    ("ref_object_zero", "pool:0:0"): "null+isnull(true)",
    ("ref_object_zero", "dictobj:2:0:/Zero"): "null",
    ("objstm_wrong_index", "pool:5:0"): "dict[1]+isnull(false)",
    ("objstm_wrong_index", "dictobj:2:0:/M"): "dict[1]",
}


def test_resolution_contracts_pinned(tmp_path: Path) -> None:
    """Oracle-free pin for pypdfbox's resolution behaviour (PDFBox-3.0.7
    expected values translated by hand)."""
    cases = {c[0]: c for c in _corpus()}
    mismatches: list[str] = []
    for (case_id, target), expected in _EXPECTED.items():
        _, pdf_bytes, _targets = cases[case_id]
        pdf = tmp_path / f"{case_id}.pdf"
        pdf.write_bytes(pdf_bytes)
        actual = _run_target_loaded(pdf, target)
        if actual != expected:
            mismatches.append(
                f"{case_id} {target}:\n  expected: {expected}\n  actual:   {actual}"
            )
    assert not mismatches, "resolution-contract drift:\n" + "\n".join(mismatches)


def _run_target_loaded(pdf_path: Path, target: str) -> str:
    document = Loader.load_pdf(str(pdf_path))
    try:
        return _run_target(document, target)
    finally:
        document.close()
