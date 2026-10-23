"""Hand-written tests for the per-``split()`` structure-tree caches in
``Splitter``.

The structure-tree clone annotates the source /K tree once per run and skips
subtrees that cannot contribute to a chunk. Upstream walks every subtree and
leaves half-built clones of dropped elements in its struct dict map, which
then surface through /ParentTree and /IDTree; the skip replays that part of
the walk on demand, so the cloned trees must be identical to the full walk.
"""

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.multipdf import Splitter
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
_ID = _N("ID")
_TYPE = _N("Type")


# ---------- structure-tree subtree skip ----------


_ID_COUNTER = [0]


def _elem(s: str, parent: COSDictionary, pg=None, k=None, typ=None) -> COSDictionary:
    d = COSDictionary()
    if typ is not None:
        d.set_item(_TYPE, _N(typ))
    else:
        d.set_item(_S, _N(s))
        _ID_COUNTER[0] += 1
        d.set_item(_ID, COSString(f"{s}.{_ID_COUNTER[0]}"))
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
        # Pg-less wrapper of a nested array of an element holding MCRs: the
        # wrapper is dropped in other chunks but its half-built clone (and
        # its parents') is still reachable through the /IDTree.
        wrapper = _elem("Art", sect)
        inner = _elem("Part", wrapper, pg=page_dict)
        inner_mcr = _elem("", inner, pg=page_dict, typ="MCR")
        inner_mcr.set_item(_N("MCID"), COSInteger.get(4))
        inner.set_item(_K, inner_mcr)
        nested = COSArray()
        nested.add(inner)
        outer = COSArray()
        outer.add(nested)
        wrapper.set_item(_K, outer)
        kids.add(wrapper)
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
    # /IDTree over every element that carries an /ID
    id_names = COSArray()
    pending = [document]
    found: dict[str, COSDictionary] = {}
    while pending:
        node = pending.pop()
        if isinstance(node, COSArray):
            pending.extend(node.get_object(i) for i in range(node.size()))
            continue
        if not isinstance(node, COSDictionary):
            continue
        ident = node.get_string(_ID)
        if ident is not None:
            found[ident] = node
        pending.append(node.get_dictionary_object(_K))
    for key in sorted(found):
        id_names.add(COSString(key))
        id_names.add(found[key])
    id_tree = COSDictionary()
    id_tree.set_item(_N("Names"), id_names)
    root_cos.set_item(_N("IDTree"), id_tree)
    doc.get_document_catalog().set_struct_tree_root(root)
    return doc


def _dump_struct(out: PDDocument) -> list[str]:
    """Breadth-first dump of everything reachable from the struct tree root
    (/K, /P back links, /ParentTree, /IDTree), nodes numbered by first
    visit; pages are shown by index."""
    page_index = {
        id(p.get_cos_object()): i for i, p in enumerate(out.get_pages())
    }
    root = out.get_document_catalog().get_struct_tree_root()
    if root is None:
        return ["none"]
    lines: list[str] = []
    seen: dict[int, int] = {}
    queue = [("root", root.get_cos_object())]
    while queue:
        path, node = queue.pop(0)
        if isinstance(node, COSDictionary) and id(node) in page_index:
            lines.append(f"{path}=page{page_index[id(node)]}")
            continue
        if isinstance(node, (COSArray, COSDictionary)):
            if id(node) in seen:
                lines.append(f"{path}=@{seen[id(node)]}")
                continue
            seen[id(node)] = len(seen)
        if isinstance(node, COSArray):
            lines.append(f"{path}=array{node.size()}")
            queue.extend((f"{path}[{i}]", node.get_object(i)) for i in range(node.size()))
        elif isinstance(node, COSDictionary):
            keys = sorted(node.key_set(), key=lambda k: k.get_name())
            lines.append(f"{path}=dict" + ",".join(k.get_name() for k in keys))
            queue.extend((f"{path}/{k.get_name()}", node.get_dictionary_object(k)) for k in keys)
        else:
            lines.append(f"{path}={node!r}")
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
    sect_masks = sorted(info[4] for info in by_s[(None, "Sect")])
    assert sect_masks == [1, 1, 2, 2]
    assert all(info[5] for info in by_s[(None, "Sect")])
    assert all(info[5] for info in by_s[(None, "Span")])
    assert not any(info[5] for info in by_s[(None, "Div")])
    assert not any(info[5] for info in by_s[(None, "Art")])
    assert not any(info[5] for info in by_s[("OBJR", None)])
    assert not any(info[5] for info in by_s[("MCR", None)])
    # parent links: a Sect's parent is the Document element, a Part's
    # parent is its Art wrapper (through the nested /K arrays)
    assert all(info[6].get_name(_S) == "Document" for info in by_s[(None, "Sect")])
    assert all(info[6].get_name(_S) == "Art" for info in by_s[(None, "Part")])


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
