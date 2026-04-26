"""
``pypdfbox merge -i a.pdf b.pdf -o out.pdf`` — concatenate PDFs.

Mirrors upstream ``org.apache.pdfbox.tools.PDFMerger``, which delegates the
real work to ``org.apache.pdfbox.multipdf.PDFMergerUtility``. That utility
performs deep ``cloneForNewDocument`` graph copying so cross-document
references (named destinations, link annotations, structure trees, fonts,
XObjects) are remapped into the merged output.

**Wave 13 upgrade.** With ``PDDocument.import_page`` (deep-copy of page
+ resources + annotations) in place, this module now:

1. Imports each source page via ``import_page`` instead of mutating the
   page's ``/Parent`` pointer in place. Each source's pages and their
   resources / contents become independent COS subgraphs in the target.
2. Walks each newly-imported page's ``/Annots`` array and remaps Link
   annotations whose ``/Dest`` (or ``/A`` GoTo action's ``/D``) is an
   explicit destination array ``[page_ref, /Fit, ...]`` pointing at a
   page from the SAME source that was also imported in this batch — the
   ``/D[0]`` entry is rewritten to the new page dictionary in the target.

Cross-document references that were not imported (a link pointing at a
page outside the current source's import set) are left untouched and
will dangle. The catalog ``/Names`` tree (named destinations, embedded
files, JavaScript actions, etc.) is **not** merged — see ``CHANGES.md``
note: named destinations from sources are dropped on merge.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSObject
from pypdfbox.pdmodel import PDDocument

_ANNOTS: COSName = COSName.get_pdf_name("Annots")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_LINK: COSName = COSName.get_pdf_name("Link")
_DEST: COSName = COSName.get_pdf_name("Dest")
_A: COSName = COSName.get_pdf_name("A")
_S: COSName = COSName.get_pdf_name("S")
_GOTO: COSName = COSName.get_pdf_name("GoTo")
_D: COSName = COSName.get_pdf_name("D")


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "merge",
        help="concatenate input PDFs into one output (per-source link remap)",
        description="Concatenate every page of every input PDF, in CLI order, "
        "into a single output PDF. Pages are deep-copied via "
        "PDDocument.import_page; intra-source link/dest references between "
        "imported pages are remapped. /Names trees (named destinations, "
        "embedded files, JS) are NOT merged — see CHANGES.md.",
    )
    p.add_argument(
        "-i", "--input", dest="inputs", nargs="+", required=True,
        metavar="INFILE", help="PDF files to merge (two or more)",
    )
    p.add_argument(
        "-o", "--output", required=True, metavar="OUTFILE",
        help="output PDF path",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    inputs: list[str] = list(args.inputs)
    if len(inputs) < 2:
        print("merge: need at least two input files", flush=True)
        return 2
    output = Path(args.output)
    for raw in inputs:
        if not Path(raw).is_file():
            print(f"merge: {raw}: not a file", flush=True)
            return 4

    out_doc = PDDocument()
    # Keep input documents open until save completes — import_page deep-
    # copies streams' raw bytes already, but holding the source open is
    # cheap insurance against any lazily-resolved indirect refs.
    open_sources: list[PDDocument] = []
    try:
        for raw in inputs:
            src = PDDocument.load(raw)
            open_sources.append(src)
            _import_source(src, out_doc)
        out_doc.save(output)
    finally:
        out_doc.close()
        for src in open_sources:
            src.close()
    return 0


def _import_source(src: PDDocument, target: PDDocument) -> None:
    """Import every page of ``src`` into ``target`` and remap intra-source
    Link annotation destinations to point at the imported page set."""
    # Walk the source pages once, retaining each src page dict alongside
    # its freshly-imported counterpart. import_page deep-copies so the
    # imported dict is a separate object graph.
    src_to_imported: dict[int, COSDictionary] = {}
    pairs: list[tuple[COSDictionary, COSDictionary]] = []
    for src_page in src.get_pages():
        src_dict = src_page.get_cos_object()
        new_page = target.import_page(src_page)
        new_dict = new_page.get_cos_object()
        src_to_imported[id(src_dict)] = new_dict
        pairs.append((src_dict, new_dict))

    # Second pass: for each imported page, walk its /Annots in lockstep
    # with the source page's /Annots. import_page preserves order, so the
    # i-th imported annotation corresponds 1:1 to the i-th source annot.
    for src_dict, new_dict in pairs:
        _remap_page_links(src_dict, new_dict, src_to_imported)


def _remap_page_links(
    src_page: COSDictionary,
    new_page: COSDictionary,
    src_to_imported: dict[int, COSDictionary],
) -> None:
    src_annots = src_page.get_dictionary_object(_ANNOTS)
    new_annots = new_page.get_dictionary_object(_ANNOTS)
    if not isinstance(src_annots, COSArray) or not isinstance(new_annots, COSArray):
        return
    n = min(src_annots.size(), new_annots.size())
    for i in range(n):
        src_annot = src_annots.get_object(i)
        new_annot = new_annots.get_object(i)
        if not isinstance(src_annot, COSDictionary):
            continue
        if not isinstance(new_annot, COSDictionary):
            continue
        if src_annot.get_name(_SUBTYPE) != _LINK.get_name():
            continue
        _remap_one_link(src_annot, new_annot, src_to_imported)


def _remap_one_link(
    src_annot: COSDictionary,
    new_annot: COSDictionary,
    src_to_imported: dict[int, COSDictionary],
) -> None:
    """Remap a single Link annotation. Tries ``/Dest`` first, then ``/A``
    with a GoTo subtype + ``/D`` array."""
    # /Dest array form
    src_dest = src_annot.get_dictionary_object(_DEST)
    new_dest = new_annot.get_dictionary_object(_DEST)
    if isinstance(src_dest, COSArray) and isinstance(new_dest, COSArray):
        _remap_dest_array(src_dest, new_dest, src_to_imported)

    # /A action with /D array (only GoTo — RemoteGoTo / GoToE point into
    # other files / embedded streams and shouldn't be remapped here).
    src_action = src_annot.get_dictionary_object(_A)
    new_action = new_annot.get_dictionary_object(_A)
    if not isinstance(src_action, COSDictionary):
        return
    if not isinstance(new_action, COSDictionary):
        return
    if src_action.get_name(_S) != _GOTO.get_name():
        return
    src_d = src_action.get_dictionary_object(_D)
    new_d = new_action.get_dictionary_object(_D)
    if isinstance(src_d, COSArray) and isinstance(new_d, COSArray):
        _remap_dest_array(src_d, new_d, src_to_imported)


def _remap_dest_array(
    src_dest: COSArray,
    new_dest: COSArray,
    src_to_imported: dict[int, COSDictionary],
) -> None:
    """If ``src_dest[0]`` resolves to a source page dict that's in our
    import map, overwrite ``new_dest[0]`` with the corresponding imported
    page dictionary."""
    if src_dest.size() < 1 or new_dest.size() < 1:
        return
    src_target = src_dest.get(0)
    if isinstance(src_target, COSObject):
        src_target = src_target.get_object()
    if not isinstance(src_target, COSDictionary):
        return
    imported = src_to_imported.get(id(src_target))
    if imported is None:
        # Cross-doc / out-of-batch reference — leave the entry alone (it
        # was already deep-copied by import_page; the link will dangle).
        return
    new_dest.set(0, imported)
