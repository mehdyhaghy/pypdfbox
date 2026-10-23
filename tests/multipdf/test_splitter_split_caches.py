"""Hand-written tests for the per-``split()`` caches in ``Splitter``.

* The resource-pruning scan uses a regex fast path that must collect exactly
  the names ``PDFStreamParser`` would, and caches the scan of shared
  dependent streams (form XObjects, ...) for the duration of one run.
* The structure-tree clone annotates the source /K tree once per run and
  skips subtrees that cannot contribute to a chunk; the cloned trees must be
  identical to the unskipped walk.
"""

import random

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.multipdf import Splitter
from pypdfbox.multipdf.splitter import _fast_scan_resource_names
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
    PDStructureElementNumberTreeNode,
)

_N = COSName.get_pdf_name
_K = _N("K")
_PG = _N("Pg")
_P = _N("P")
_S = _N("S")
_TYPE = _N("Type")
_RESOURCES = _N("Resources")


def _stream(payload: bytes) -> COSStream:
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(payload)
    return stream


def _fast_as_str(data: bytes) -> dict[str, frozenset[str]] | None:
    fast = _fast_scan_resource_names(data)
    if fast is None:
        return None
    return {
        c: frozenset(_N(raw).get_name() for raw in names)
        for c, names in fast.items()
    }


# ---------- fast resource-name scanner ----------

_ACCEPTED = [
    b"BT /F1 12 Tf (Hello) Tj ET",
    b"/Im0 Do q /GS1 gs /CS0 cs /P0 scn Q",
    b"/OC /MC0 BDC EMC /Span <</MCID 0>> BDC EMC",
    b"0 0 d0 /F2 Tf [(a) -20 (b(c)d)] TJ",
    b"1 0 0 RG /Pattern cs 0.5 .5 -.5 +5 5. /P1 scn",
    b"%comment /F9 Tf\n/F3 1 Tf <41 42> Tj true false null /Sh0 sh",
    b"/A <</B [1 2 <</C (x)>>] /D /E>> DP /F4 9 Tf",
    b"(a\\)b /F8 Tf) Tj /F5 1 Tf",
]

_REJECTED = [
    b"BI /W 1 /H 1 /CS /CS0 ID \x00 EI",  # inline image
    b"/F#31 1 Tf",  # name escape
    b"1-2 /F1 Tf",  # PDFBOX-4064 number quirk
    b"[1 0 R] /F1 Tf",  # keyword inside an array
    b"(unterminated /F1 Tf",
    b"<< /A 1 2 >> /X DP",  # dict value followed by a digit
    b"/F1 1 Tf }",
]


@pytest.mark.parametrize("data", _ACCEPTED, ids=range(len(_ACCEPTED)))
def test_fast_scan_matches_exact_parser(data: bytes) -> None:
    fast = _fast_as_str(data)
    assert fast is not None
    assert fast == Splitter._exact_scan_resource_names(data)


@pytest.mark.parametrize("data", _REJECTED, ids=range(len(_REJECTED)))
def test_fast_scan_rejects_constructs_outside_subset(data: bytes) -> None:
    assert _fast_scan_resource_names(data) is None


def test_fast_scan_collects_expected_names() -> None:
    found = _fast_as_str(b"/F1 1 Tf /Im0 Do /CS0 CS /GS0 gs /P0 SCN /Sh sh "
                         b"/OC /MC0 BDC")
    assert found is not None
    assert found["Font"] == {"F1"}
    assert found["XObject"] == {"Im0"}
    assert found["ColorSpace"] == {"CS0"}
    assert found["ExtGState"] == {"GS0"}
    assert found["Pattern"] == {"P0"}
    assert found["Shading"] == {"Sh"}
    assert found["Properties"] == {"MC0"}


def test_fast_scan_fuzz_agrees_with_exact_parser() -> None:
    vocab = [
        b"/F1", b"/Im0", b"/P0", b"/MC0", b"/OC", b"1", b"-2", b".5", b"5.",
        b"Tf", b"Do", b"gs", b"cs", b"scn", b"SCN", b"sh", b"BDC", b"DP",
        b"d0", b"d", b"Q]", b"true", b"null", b"(a)", b"(a(b)c)", b"(a\\)",
        b"<41>", b"<</MCID 1>>", b"[(a) 1 (b)]", b"[", b"]", b"<<", b">>",
        b"'", b"%c\n", b"BI", b"f*", b"(", b")", b"\x80", b"{",
    ]
    rng = random.Random(1622)
    accepted = 0
    for _ in range(3000):
        data = b"".join(
            rng.choice(vocab) + rng.choice([b" ", b"\n", b"", b"\r\n"])
            for _ in range(rng.randint(1, 20))
        )
        fast = _fast_as_str(data)
        if fast is None:
            continue
        accepted += 1
        assert fast == Splitter._exact_scan_resource_names(data), data
    assert accepted > 100


# ---------- shared-stream scan cache ----------


def _doc_with_shared_form(n_pages: int) -> PDDocument:
    form = _stream(b"/F1 1 Tf (x) Tj")
    form.set_item(_N("Subtype"), _N("Form"))
    fonts = COSDictionary()
    for name in ("F1", "F2"):
        fonts.set_item(_N(name), COSDictionary())
    xobjects = COSDictionary()
    xobjects.set_item(_N("Fm0"), form)
    resources = COSDictionary()
    resources.set_item(_N("Font"), fonts)
    resources.set_item(_N("XObject"), xobjects)
    doc = PDDocument()
    for i in range(n_pages):
        page = PDPage()
        page.get_cos_object().set_item(_RESOURCES, resources)
        page.get_cos_object().set_item(
            _N("Contents"), _stream(b"/Fm0 Do %page " + str(i).encode("utf-8"))
        )
        doc.add_page(page)
    return doc


def test_shared_form_is_scanned_once_per_split(monkeypatch) -> None:
    calls: list[bytes] = []
    original = Splitter._scan_resource_names

    def counting(data: bytes) -> dict[str, frozenset[str]]:
        calls.append(bytes(data))
        return original(data)

    monkeypatch.setattr(Splitter, "_scan_resource_names", staticmethod(counting))
    doc = _doc_with_shared_form(4)
    splitter = Splitter()
    outputs = splitter.split(doc)
    assert len(outputs) == 4
    # import_page copies the form per page, but the scan cache is keyed by
    # content: 4 distinct page streams + the shared form exactly once.
    assert calls.count(b"/F1 1 Tf (x) Tj") == 1
    assert len(calls) == 5
    # The cache does not outlive the run.
    assert splitter._resource_scan_cache == {}

    # Every output page still gets its own pruned resource dictionary.
    seen_res: list[COSDictionary] = []
    for out in outputs:
        res = out.get_page(0).get_cos_object().get_dictionary_object(_RESOURCES)
        assert isinstance(res, COSDictionary)
        fonts = res.get_dictionary_object(_N("Font"))
        assert [k.get_name() for k in fonts.key_set()] == ["F1"]
        assert all(res is not other for other in seen_res)
        seen_res.append(res)

    # A second run starts with a fresh cache and scans the form again.
    calls.clear()
    Splitter().split(doc)
    assert calls.count(b"/F1 1 Tf (x) Tj") == 1


# ---------- structure-tree subtree skip ----------


def _elem(s: str, parent: COSDictionary, pg=None, k=None, typ=None) -> COSDictionary:
    d = COSDictionary()
    if typ is not None:
        d.set_item(_TYPE, _N(typ))
    else:
        d.set_item(_S, _N(s))
    d.set_item(_P, parent)
    if pg is not None:
        d.set_item(_PG, pg)
    if k is not None:
        d.set_item(_K, k)
    return d


def _tagged_doc(n_pages: int, share_node: bool = False) -> PDDocument:
    doc = PDDocument()
    pages = []
    for i in range(n_pages):
        page = PDPage()
        page.set_struct_parents(i)
        annot = COSDictionary()
        annot.set_item(_TYPE, _N("Annot"))
        annot.set_item(_N("Subtype"), _N("Link"))
        annot.set_item(_N("StructParent"), COSInteger.get(100 + i))
        annots = COSArray()
        annots.add(annot)
        page.get_cos_object().set_item(_N("Annots"), annots)
        doc.add_page(page)
        pages.append((page.get_cos_object(), annot))

    root = PDStructureTreeRoot()
    root_cos = root.get_cos_object()
    document = _elem("Document", root_cos)
    doc_kids = COSArray()
    numbers: dict[int, COSDictionary | COSArray] = {}
    shared = None
    for i, (page_dict, annot) in enumerate(pages):
        sect = _elem("Sect", document)
        kids = COSArray()
        # Leaf with /Pg + MCID.
        para = _elem("P", sect, pg=page_dict, k=COSInteger.get(0))
        kids.add(para)
        # Pg-less element whose MCID inherits the page from nowhere: it
        # survives in every chunk (live subtree).
        kids.add(_elem("Span", sect, k=COSInteger.get(1)))
        # Element whose kids are MCRs (with and without /Pg).
        mcr_holder = _elem("Note", sect, pg=page_dict)
        mcrs = COSArray()
        mcr = _elem("", mcr_holder, pg=page_dict, k=None, typ="MCR")
        mcr.set_item(_N("MCID"), COSInteger.get(2))
        mcrs.add(mcr)
        bare_mcr = _elem("", mcr_holder, typ="MCR")
        bare_mcr.set_item(_N("MCID"), COSInteger.get(3))
        mcrs.add(bare_mcr)
        mcr_holder.set_item(_K, mcrs)
        kids.add(mcr_holder)
        # Link element with a Pg-less OBJR.
        link = _elem("Link", sect, pg=page_dict)
        objr = _elem("", link, typ="OBJR")
        objr.set_item(_N("Obj"), annot)
        link.set_item(_K, objr)
        kids.add(link)
        # Pg-less container of an OBJR only: never survives.
        holder = _elem("Div", sect)
        objr2 = _elem("", holder, typ="OBJR")
        objr2.set_item(_N("Obj"), annot)
        holder.set_item(_K, objr2)
        kids.add(holder)
        if share_node:
            if shared is None:
                shared = para
            else:
                kids.add(shared)
        sect.set_item(_K, kids)
        doc_kids.add(sect)
        arr = COSArray()
        arr.add(para)
        numbers[i] = arr
        numbers[100 + i] = link
    document.set_item(_K, doc_kids)
    root_cos.set_item(_K, document)
    pt = PDStructureElementNumberTreeNode(COSDictionary())
    pt.set_numbers(numbers)
    root.set_parent_tree(pt)
    root.set_parent_tree_next_key(200)
    doc.get_document_catalog().set_struct_tree_root(root)
    return doc


def _dump_struct(out: PDDocument) -> list[str]:
    page_index = {
        id(p.get_cos_object()): i for i, p in enumerate(out.get_pages())
    }
    lines: list[str] = []
    seen: dict[int, int] = {}

    def walk(node, depth: int) -> None:
        if isinstance(node, COSArray):
            for i in range(node.size()):
                walk(node.get_object(i), depth)
            return
        if not isinstance(node, COSDictionary):
            lines.append(f"{depth}:{node!r}")
            return
        if id(node) in seen:
            lines.append(f"{depth}:dup{seen[id(node)]}")
            return
        seen[id(node)] = len(seen)
        pg = node.get_dictionary_object(_PG)
        keys = ",".join(sorted(k.get_name() for k in node.key_set()))
        lines.append(
            f"{depth}:{node.get_name(_TYPE)}:{node.get_name(_S)}:"
            f"pg={page_index.get(id(pg)) if pg is not None else None}:{keys}"
        )
        walk(node.get_dictionary_object(_K), depth + 1)

    root = out.get_document_catalog().get_struct_tree_root()
    if root is None:
        return ["none"]
    walk(root.get_cos_object().get_dictionary_object(_K), 0)
    pt = root.get_parent_tree()
    if pt is not None:
        for key, value in sorted(Splitter._get_number_tree_as_map(pt).items()):
            ids = (
                [seen.get(id(value.get_object(i)), -1) for i in range(value.size())]
                if isinstance(value, COSArray)
                else [seen.get(id(value), -1)]
            )
            lines.append(f"pt{key}={ids}")
    return lines


def _split_dumps(doc: PDDocument, length: int, skip: bool, monkeypatch):
    if not skip:
        monkeypatch.setattr(Splitter, "_build_k_skip_info", lambda self, k: None)
    splitter = Splitter()
    splitter.set_split_at_page(length)
    dumps = [_dump_struct(out) for out in splitter.split(doc)]
    monkeypatch.undo()
    return dumps, splitter


@pytest.mark.parametrize("length", [1, 2, 3])
def test_struct_skip_matches_full_walk(length: int, monkeypatch) -> None:
    doc = _tagged_doc(6)
    reference, _ = _split_dumps(doc, length, skip=False, monkeypatch=monkeypatch)
    skipped, splitter = _split_dumps(doc, length, skip=True, monkeypatch=monkeypatch)
    assert skipped == reference
    # The per-run caches are released after split().
    assert splitter._k_node_cache is None
    assert not splitter._k_skip_enabled


def test_struct_skip_info_marks_chunks_and_liveness() -> None:
    doc = _tagged_doc(4)
    splitter = Splitter()
    splitter.set_split_at_page(2)
    captured: dict[str, object] = {}
    original = Splitter._build_k_skip_info

    def capture(self, src_k) -> None:
        original(self, src_k)
        captured["enabled"] = self._k_skip_enabled
        captured["cache"] = dict(self._k_node_cache)

    Splitter._build_k_skip_info = capture
    try:
        splitter.split(doc)
    finally:
        Splitter._build_k_skip_info = original
    assert captured["enabled"] is True
    by_s = {}
    for info in captured["cache"].values():
        by_s.setdefault((info[3], info[0].get_name(_S)), []).append(info)
    # Sections of pages 0-1 map to chunk 0, pages 2-3 to chunk 1; each is
    # live because of its Pg-less MCID Span.
    sect_masks = sorted(info[5] for info in by_s[(None, "Sect")])
    assert sect_masks == [1, 1, 2, 2]
    assert all(info[6] for info in by_s[(None, "Sect")])
    assert all(info[6] for info in by_s[(None, "Span")])
    assert not any(info[6] for info in by_s[(None, "Div")])
    assert not any(info[6] for info in by_s[("OBJR", None)])
    assert not any(info[6] for info in by_s[("MCR", None)])


def test_struct_skip_disabled_for_shared_nodes(monkeypatch) -> None:
    doc = _tagged_doc(4, share_node=True)
    reference, _ = _split_dumps(doc, 1, skip=False, monkeypatch=monkeypatch)
    enabled: list[bool] = []
    original = Splitter._build_k_skip_info

    def record(self, src_k) -> None:
        original(self, src_k)
        enabled.append(self._k_skip_enabled)

    monkeypatch.setattr(Splitter, "_build_k_skip_info", record)
    splitter = Splitter()
    splitter.set_split_at_page(1)
    skipped = [_dump_struct(out) for out in splitter.split(doc)]
    assert enabled == [False]
    assert skipped == reference


def test_direct_k_clone_outside_split_does_not_cache() -> None:
    splitter = Splitter()
    src = COSDictionary()
    src.set_item(_S, _N("P"))
    src.set_item(_K, COSInteger.get(0))
    parent = COSDictionary()
    clone = splitter._k_create_clone(src, parent, None, object())
    assert isinstance(clone, COSDictionary)
    assert splitter._k_node_cache is None
