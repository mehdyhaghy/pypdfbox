"""Saving deeply nested direct (inline) arrays / dictionaries.

``COSWriter`` recurses once per nesting level of a direct container. Past
``_DIRECT_FAST_PATH_MAX_DEPTH`` it hands the subtree to an explicit-stack
walker, so a 5000-deep inline structure saves without ``RecursionError``
and the bytes are identical to what the recursive visitor produces.
"""

from __future__ import annotations

import io
import random
import re
import sys
from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdfwriter import cos_writer as cos_writer_module
from pypdfbox.pdfwriter.compress import CompressParameters
from pypdfbox.pdmodel import PDDocument

DEPTH = 5000
_DEEP = COSName.get_pdf_name("Deep")
_K = COSName.get_pdf_name("K")
_REF = COSName.get_pdf_name("Ref")
_LEAF = COSName.get_pdf_name("Leaf")
_ID_RE = re.compile(rb"/ID ?\[ ?<[0-9A-Fa-f]*> ?<[0-9A-Fa-f]*> ?\]")
_FIXTURE = Path(__file__).parent.parent / "fixtures" / "text" / "rotated_text_dir.pdf"


def _container(is_dict: bool) -> COSArray | COSDictionary:
    if is_dict:
        d = COSDictionary()
        d.set_direct(True)
        return d
    return COSArray()


def _build(depth: int, shape: str) -> tuple[COSArray | COSDictionary, COSDictionary]:
    """Return ``(root, leaf)``: a chain of ``depth`` direct containers
    (``shape`` is ``"array"``, ``"dict"`` or ``"mixed"``); the innermost one
    holds an indirect reference to ``leaf``. Array level ``i`` is
    ``[i child]``, dictionary level is ``<< /K child >>``. Built iteratively."""
    leaf = COSDictionary()
    leaf.set_item(_LEAF, COSString(b"bottom"))
    kinds = [
        shape == "dict" or (shape == "mixed" and i % 2 == 1) for i in range(depth)
    ]
    nodes = [_container(k) for k in kinds]
    for i, node in enumerate(nodes):
        child = nodes[i + 1] if i + 1 < depth else None
        if isinstance(node, COSDictionary):
            if child is None:
                node.set_item(_REF, leaf)
            else:
                node.set_item(_K, child)
        else:
            node.add(COSInteger.get(i))
            node.add(leaf if child is None else child)
    return nodes[0], leaf


def _expected(depth: int, shape: str, ref: bytes) -> bytes:
    """Independent reference serialization of :func:`_build`'s structure,
    following the ``COSWriter`` layout rules: arrays are ``[`` + items
    separated by a space + ``]`` + EOL; dictionaries are ``<<`` EOL, one
    ``key value`` line per entry, ``>>`` EOL (a nested container's own
    trailing EOL is not doubled)."""
    head: list[bytes] = []
    tail: list[bytes] = []
    for i in range(depth):
        is_dict = shape == "dict" or (shape == "mixed" and i % 2 == 1)
        innermost = i == depth - 1
        if is_dict:
            if innermost:
                head.append(b"<<\n/Ref " + ref + b"\n>>\n")
            else:
                head.append(b"<<\n/K ")
                tail.append(b">>\n")
        else:
            if innermost:
                head.append(b"[%d %s]\n" % (i, ref))
            else:
                head.append(b"[%d " % i)
                tail.append(b"]\n")
    return b"".join(head) + b"".join(reversed(tail))


def _catalog_body(data: bytes, catalog_number: int) -> bytes:
    """Bytes of the LAST ``N 0 obj ... endobj`` frame of the catalog."""
    marker = b"\n%d 0 obj\n" % catalog_number
    start = data.rindex(marker) + len(marker)
    end = data.index(b"\nendobj", start)
    return data[start:end]


def _check(data: bytes, depth: int, shape: str) -> None:
    root_match = re.findall(rb"/Root (\d+) 0 R", data)
    assert root_match, "trailer /Root not found"
    body = _catalog_body(data, int(root_match[-1]))
    pos = body.index(b"/Deep ") + len(b"/Deep ")
    deep = body[pos:]
    ref_match = re.search(rb"(\d+) 0 R", deep)
    assert ref_match is not None
    ref = ref_match.group(0)
    expected = _expected(depth, shape, ref)
    assert deep[: len(expected)] == expected
    # The referenced leaf object was queued and written (top-level, or
    # packed into an object stream when those are on).
    leaf_number = int(ref_match.group(1))
    if b"/Type /ObjStm" not in data:
        frame = data.index(b"\n%d 0 obj\n" % leaf_number)
        assert data[frame:].split(b"endobj", 1)[0].count(b"/Leaf (bottom)") == 1


def _new_doc(depth: int, shape: str) -> PDDocument:
    doc = PDDocument()
    root, _leaf = _build(depth, shape)
    doc.get_document_catalog().get_cos_object().set_item(_DEEP, root)
    return doc


@pytest.mark.parametrize("shape", ["array", "dict", "mixed"])
@pytest.mark.parametrize(
    "params",
    [CompressParameters.NO_COMPRESSION, CompressParameters.DEFAULT_COMPRESSION],
    ids=["no_objstm", "objstm"],
)
def test_full_save_deep_direct_containers(
    shape: str, params: CompressParameters
) -> None:
    doc = _new_doc(DEPTH, shape)
    try:
        out = io.BytesIO()
        doc.save(out, params)
    finally:
        doc.close()
    _check(out.getvalue(), DEPTH, shape)


@pytest.mark.parametrize("shape", ["array", "dict", "mixed"])
def test_incremental_save_deep_direct_containers(shape: str) -> None:
    doc = PDDocument.load(_FIXTURE.read_bytes())
    try:
        root, leaf = _build(DEPTH, shape)
        leaf.set_needs_to_be_updated(True)
        catalog = doc.get_document_catalog().get_cos_object()
        catalog.set_item(_DEEP, root)
        catalog.set_needs_to_be_updated(True)
        out = io.BytesIO()
        doc.save_incremental(out)
    finally:
        doc.close()
    data = out.getvalue()
    assert data.startswith(_FIXTURE.read_bytes())
    _check(data, DEPTH, shape)


def _random_structure(seed: int, depth: int) -> COSArray:
    """A deep, irregular structure exercising every emit branch: leaves of
    every kind, ``None`` slots, arrays longer than 10 (EOL separators),
    indirect dictionaries / arrays / streams, and PDFBOX-3684
    ``/Resources`` / ``/XObject`` sub-dictionaries."""
    rnd = random.Random(seed)

    def leaf() -> object:
        c = rnd.randrange(9)
        if c == 0:
            return COSInteger.get(rnd.randrange(-50, 1000))
        if c == 1:
            return COSFloat(rnd.random() * 100)
        if c == 2:
            return COSString(b"secretmarker%d" % rnd.randrange(99))
        if c == 3:
            return COSName.get_pdf_name(f"n{rnd.randrange(20)}")
        if c == 4:
            return COSBoolean.TRUE
        if c == 5:
            return COSNull.NULL
        if c == 6:
            ind = COSDictionary()
            ind.set_item(_LEAF, COSString(b"secretmarker"))
            return ind
        if c == 7:
            arr = COSArray([COSInteger.get(1)])
            arr.set_direct(False)
            return arr
        stream = COSStream()
        stream.set_item(COSName.TYPE, COSName.XOBJECT)
        with stream.create_output_stream() as sink:
            sink.write(b"q Q")
        return stream

    root = COSArray()
    parent: COSArray | COSDictionary = root
    for level in range(depth):
        if rnd.random() < 0.5:
            node: COSArray | COSDictionary = COSArray()
            for _ in range(rnd.randrange(0, 13)):
                node.add(None if rnd.random() < 0.1 else leaf())
        else:
            node = COSDictionary()
            node.set_direct(True)
            for j in range(rnd.randrange(0, 4)):
                if rnd.random() < 0.3:
                    sub = COSDictionary()
                    sub.set_direct(rnd.random() < 0.5)
                    sub.set_item(COSName.XOBJECT, COSDictionary())
                    sub.set_item(COSName.RESOURCES, COSDictionary())
                    node.set_item(COSName.get_pdf_name(f"S{j}"), sub)
                else:
                    node.set_item(COSName.get_pdf_name(f"E{j}"), leaf())
        if isinstance(parent, COSArray):
            parent.add(node)
        else:
            key = rnd.choice([_K, COSName.RESOURCES, COSName.XOBJECT])
            parent.set_item(key, node)
        if level % 7 == 0 and isinstance(parent, COSArray):
            parent.add(leaf())
        parent = node
    return root


def _save_random(seed: int, depth: int, params: CompressParameters,
                 encrypt: bool) -> bytes:
    doc = PDDocument()
    try:
        catalog = doc.get_document_catalog().get_cos_object()
        catalog.set_item(_DEEP, _random_structure(seed, depth))
        if encrypt:
            from pypdfbox.pdmodel.encryption import (
                AccessPermission,
                StandardProtectionPolicy,
            )

            policy = StandardProtectionPolicy("o", "u", AccessPermission())
            policy.set_encryption_key_length(128)
            policy.set_prefer_aes(False)
            doc.protect(policy)
        out = io.BytesIO()
        doc.save(out, params)
        return out.getvalue()
    finally:
        doc.close()


@pytest.mark.parametrize("encrypt", [False, True], ids=["plain", "rc4"])
@pytest.mark.parametrize(
    "params",
    [CompressParameters.NO_COMPRESSION, CompressParameters.DEFAULT_COMPRESSION],
    ids=["no_objstm", "objstm"],
)
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_iterative_walker_matches_recursive_visitor(
    monkeypatch: pytest.MonkeyPatch,
    seed: int,
    params: CompressParameters,
    encrypt: bool,
) -> None:
    """Same document saved with the explicit-stack walker forced from the
    first level (threshold 0) and with pure recursion (threshold huge) is
    byte-identical, including encrypted strings in nested containers."""
    import os
    import time

    depth = 150

    def run(threshold: int) -> bytes:
        rng = random.Random(seed)
        monkeypatch.setattr(os, "urandom", rng.randbytes)
        monkeypatch.setattr(cos_writer_module.secrets, "token_bytes", rng.randbytes)
        monkeypatch.setattr(time, "time_ns", lambda: 1_700_000_000_000_000_000)
        monkeypatch.setattr(
            cos_writer_module, "_DIRECT_FAST_PATH_MAX_DEPTH", threshold
        )
        return _save_random(seed, depth, params, encrypt)

    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, 20 * depth + 1000))
    try:
        recursive = run(10**9)
    finally:
        sys.setrecursionlimit(old_limit)
    iterative = run(0)
    boundary = run(3)
    assert iterative == recursive
    assert boundary == recursive
    assert (b"secretmarker" in recursive) is not encrypt


def test_shallow_save_unchanged_by_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fixture saved with the walker forced everywhere matches the
    default (recursive) save once /ID is blanked."""
    data = _FIXTURE.read_bytes()

    def run(threshold: int) -> bytes:
        monkeypatch.setattr(
            cos_writer_module, "_DIRECT_FAST_PATH_MAX_DEPTH", threshold
        )
        doc = PDDocument.load(data)
        try:
            out = io.BytesIO()
            doc.save(out, CompressParameters.NO_COMPRESSION)
        finally:
            doc.close()
        return _ID_RE.sub(b"/ID []", out.getvalue())

    assert run(0) == run(64)


def test_depth_counter_restored_after_save() -> None:
    doc = _new_doc(200, "mixed")
    try:
        from pypdfbox.pdfwriter import COSWriter

        out = io.BytesIO()
        writer = COSWriter(out)
        writer.write(doc)
        assert writer._direct_depth == 0
    finally:
        doc.close()
    _check(out.getvalue(), 200, "mixed")
