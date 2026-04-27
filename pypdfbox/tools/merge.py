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
3. Merges supported catalog ``/Names`` subtrees (``/Dests``,
   ``/EmbeddedFiles``, ``/JavaScript``). Duplicate names are preserved by
   suffixing later entries as ``#2``, ``#3``, ...; imported Link
   annotations that referenced a renamed named destination are rewritten
   to the suffixed name.

Cross-document references that were not imported (a link pointing at a
page outside the current source's import set) are left untouched and
will dangle. This is still a focused foundation, not the full
``PDFMergerUtility`` reconciliation surface (forms, structure trees,
outlines, and destination-module internals remain out of scope here).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSObject, COSString
from pypdfbox.pdmodel import PDDocument

_ANNOTS: COSName = COSName.get_pdf_name("Annots")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_LINK: COSName = COSName.get_pdf_name("Link")
_DEST: COSName = COSName.get_pdf_name("Dest")
_A: COSName = COSName.get_pdf_name("A")
_S: COSName = COSName.get_pdf_name("S")
_GOTO: COSName = COSName.get_pdf_name("GoTo")
_D: COSName = COSName.get_pdf_name("D")
_NAMES: COSName = COSName.get_pdf_name("Names")
_KIDS: COSName = COSName.get_pdf_name("Kids")
_TYPE: COSName = COSName.get_pdf_name("Type")
_PAGE: COSName = COSName.get_pdf_name("Page")
_PAGES: COSName = COSName.get_pdf_name("Pages")
_DESTS: COSName = COSName.get_pdf_name("Dests")
_EMBEDDED_FILES: COSName = COSName.get_pdf_name("EmbeddedFiles")
_JAVA_SCRIPT: COSName = COSName.get_pdf_name("JavaScript")


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "merge",
        help="concatenate input PDFs into one output (per-source link remap)",
        description="Concatenate every page of every input PDF, in CLI order, "
        "into a single output PDF. Pages are deep-copied via "
        "PDDocument.import_page; intra-source link/dest references between "
        "imported pages are remapped. Supported catalog /Names trees "
        "(named destinations, embedded files, JS) are merged.",
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
    src_to_imported: dict[object, COSDictionary] = {}
    pairs: list[tuple[COSDictionary, COSDictionary]] = []
    page_object_keys = _source_page_object_keys(src)
    for page_index, src_page in enumerate(src.get_pages()):
        src_dict = src_page.get_cos_object()
        new_page = target.import_page(src_page)
        new_dict = new_page.get_cos_object()
        src_to_imported[("id", id(src_dict))] = new_dict
        if page_index < len(page_object_keys):
            object_key = page_object_keys[page_index]
            if object_key is not None:
                src_to_imported[object_key] = new_dict
        pairs.append((src_dict, new_dict))

    renamed_dests = _merge_supported_names(src, target, src_to_imported)

    # Second pass: for each imported page, walk its /Annots in lockstep
    # with the source page's /Annots. import_page preserves order, so the
    # i-th imported annotation corresponds 1:1 to the i-th source annot.
    for src_dict, new_dict in pairs:
        _remap_page_links(src_dict, new_dict, src_to_imported, renamed_dests)


def _remap_page_links(
    src_page: COSDictionary,
    new_page: COSDictionary,
    src_to_imported: dict[object, COSDictionary],
    renamed_dests: dict[str, str] | None = None,
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
        _remap_one_link(src_annot, new_annot, src_to_imported, renamed_dests)


def _remap_one_link(
    src_annot: COSDictionary,
    new_annot: COSDictionary,
    src_to_imported: dict[object, COSDictionary],
    renamed_dests: dict[str, str] | None = None,
) -> None:
    """Remap a single Link annotation. Tries ``/Dest`` first, then ``/A``
    with a GoTo subtype + ``/D`` array."""
    # /Dest array form
    src_dest = src_annot.get_dictionary_object(_DEST)
    new_dest = new_annot.get_dictionary_object(_DEST)
    if isinstance(src_dest, COSArray) and isinstance(new_dest, COSArray):
        _remap_dest_array(src_dest, new_dest, src_to_imported)
    elif renamed_dests is not None:
        replacement = _renamed_dest_value(src_dest, renamed_dests)
        if replacement is not None:
            new_annot.set_item(_DEST, replacement)

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
    elif renamed_dests is not None:
        replacement = _renamed_dest_value(src_d, renamed_dests)
        if replacement is not None:
            new_action.set_item(_D, replacement)


def _remap_dest_array(
    src_dest: COSArray,
    new_dest: COSArray,
    src_to_imported: dict[object, COSDictionary],
) -> None:
    """If ``src_dest[0]`` resolves to a source page dict that's in our
    import map, overwrite ``new_dest[0]`` with the corresponding imported
    page dictionary."""
    if src_dest.size() < 1 or new_dest.size() < 1:
        return
    src_target_raw = src_dest.get(0)
    imported = None
    if isinstance(src_target_raw, COSObject):
        imported = src_to_imported.get(_object_key(src_target_raw))
        src_target = src_target_raw.get_object()
    else:
        src_target = src_target_raw
    if imported is None and isinstance(src_target, COSDictionary):
        imported = src_to_imported.get(("id", id(src_target)))
    if not isinstance(src_target, COSDictionary) and imported is None:
        return
    if imported is None:
        # Cross-doc / out-of-batch reference — leave the entry alone (it
        # was already deep-copied by import_page; the link will dangle).
        return
    new_dest.set(0, imported)


def _merge_supported_names(
    src: PDDocument,
    target: PDDocument,
    src_to_imported: dict[object, COSDictionary],
) -> dict[str, str]:
    """Merge the supported catalog /Names categories from one source.

    Returns a source-name -> target-name mapping for named destinations
    that had to be renamed due to collisions.
    """
    target_catalog = target.get_document_catalog().get_cos_object()
    target_names = _ensure_names_dictionary(target_catalog)
    src_catalog = src.get_document_catalog().get_cos_object()
    src_names = src_catalog.get_dictionary_object(_NAMES)

    renamed_dests: dict[str, str] = {}
    if isinstance(src_names, COSDictionary):
        renamed_dests.update(
            _merge_name_tree_category(
                src_names,
                target_names,
                _DESTS,
                target,
                src_to_imported,
                remap_destinations=True,
            )
        )
        _merge_name_tree_category(
            src_names,
            target_names,
            _EMBEDDED_FILES,
            target,
            src_to_imported,
            remap_destinations=False,
        )
        _merge_name_tree_category(
            src_names,
            target_names,
            _JAVA_SCRIPT,
            target,
            src_to_imported,
            remap_destinations=False,
        )

    # Legacy catalog-level /Dests entries are folded into the output's
    # proper /Names /Dests tree so named links have one lookup surface.
    legacy_dests = src_catalog.get_dictionary_object(_DESTS)
    if isinstance(legacy_dests, COSDictionary):
        renamed_dests.update(
            _merge_legacy_dests(
                legacy_dests,
                target_names,
                target,
                src_to_imported,
            )
        )

    if target_names.is_empty():
        target_catalog.remove_item(_NAMES)
    return renamed_dests


def _ensure_names_dictionary(catalog: COSDictionary) -> COSDictionary:
    names = catalog.get_dictionary_object(_NAMES)
    if isinstance(names, COSDictionary):
        return names
    names = COSDictionary()
    catalog.set_item(_NAMES, names)
    return names


def _merge_name_tree_category(
    src_names: COSDictionary,
    target_names: COSDictionary,
    category: COSName,
    target: PDDocument,
    src_to_imported: dict[object, COSDictionary],
    *,
    remap_destinations: bool,
) -> dict[str, str]:
    src_tree = src_names.get_dictionary_object(category)
    if not isinstance(src_tree, COSDictionary):
        return {}

    entries = _collect_name_tree_entries(src_tree)
    if not entries:
        return {}

    target_tree = _ensure_name_tree(target_names, category)
    merged = _collect_name_tree_entries(target_tree)
    used = {name for name, _ in merged}
    renamed: dict[str, str] = {}

    for name, value in entries:
        target_name = _deduplicate_name(name, used)
        used.add(target_name)
        if target_name != name:
            renamed[name] = target_name
        cloned = target._deep_copy_cos(value, set())
        if remap_destinations:
            _remap_destination_value(value, cloned, src_to_imported)
        merged.append((target_name, cloned))

    _set_flat_name_tree_entries(target_tree, merged)
    return renamed


def _merge_legacy_dests(
    legacy_dests: COSDictionary,
    target_names: COSDictionary,
    target: PDDocument,
    src_to_imported: dict[object, COSDictionary],
) -> dict[str, str]:
    target_tree = _ensure_name_tree(target_names, _DESTS)
    merged = _collect_name_tree_entries(target_tree)
    used = {name for name, _ in merged}
    renamed: dict[str, str] = {}

    for key in legacy_dests.key_set():
        name = key.get_name()
        value = legacy_dests.get_dictionary_object(key)
        if value is None:
            continue
        target_name = _deduplicate_name(name, used)
        used.add(target_name)
        if target_name != name:
            renamed[name] = target_name
        cloned = target._deep_copy_cos(value, set())
        _remap_destination_value(value, cloned, src_to_imported)
        merged.append((target_name, cloned))

    _set_flat_name_tree_entries(target_tree, merged)
    return renamed


def _ensure_name_tree(names_dict: COSDictionary, category: COSName) -> COSDictionary:
    tree = names_dict.get_dictionary_object(category)
    if isinstance(tree, COSDictionary):
        return tree
    tree = COSDictionary()
    names_dict.set_item(category, tree)
    return tree


def _collect_name_tree_entries(node: COSDictionary) -> list[tuple[str, COSBase]]:
    entries: list[tuple[str, COSBase]] = []
    names = node.get_dictionary_object(_NAMES)
    if isinstance(names, COSArray):
        i = 0
        while i + 1 < names.size():
            key = _name_key_text(names.get_object(i))
            value = names.get_object(i + 1)
            if key is not None and value is not None:
                entries.append((key, value))
            i += 2

    kids = node.get_dictionary_object(_KIDS)
    if isinstance(kids, COSArray):
        for i in range(kids.size()):
            kid = kids.get_object(i)
            if isinstance(kid, COSDictionary):
                entries.extend(_collect_name_tree_entries(kid))
    return entries


def _set_flat_name_tree_entries(
    node: COSDictionary,
    entries: list[tuple[str, COSBase]],
) -> None:
    entries_by_name: dict[str, COSBase] = {}
    for name, value in entries:
        entries_by_name[name] = value

    arr = COSArray()
    for name in sorted(entries_by_name):
        arr.add(COSString(name))
        arr.add(entries_by_name[name])
    node.set_item(_NAMES, arr)
    node.remove_item(_KIDS)


def _deduplicate_name(name: str, used: set[str]) -> str:
    if name not in used:
        return name
    index = 2
    while True:
        candidate = f"{name}#{index}"
        if candidate not in used:
            return candidate
        index += 1


def _remap_destination_value(
    src_value: COSBase,
    new_value: COSBase,
    src_to_imported: dict[object, COSDictionary],
) -> None:
    if isinstance(src_value, COSArray) and isinstance(new_value, COSArray):
        _remap_dest_array(src_value, new_value, src_to_imported)
        return
    if isinstance(src_value, COSDictionary) and isinstance(new_value, COSDictionary):
        src_inner = src_value.get_dictionary_object(_D)
        new_inner = new_value.get_dictionary_object(_D)
        if isinstance(src_inner, COSArray) and isinstance(new_inner, COSArray):
            _remap_dest_array(src_inner, new_inner, src_to_imported)


def _renamed_dest_value(
    src_dest: COSBase | None,
    renamed_dests: dict[str, str],
) -> COSString | None:
    src_name = _name_key_text(src_dest)
    if src_name is None:
        return None
    new_name = renamed_dests.get(src_name)
    if new_name is None:
        return None
    return COSString(new_name)


def _source_page_object_keys(src: PDDocument) -> list[tuple[str, int, int] | None]:
    root = src.get_document_catalog().get_pages().get_cos_object()
    keys: list[tuple[str, int, int] | None] = []
    _collect_page_object_keys(root, None, keys, set())
    return keys


def _collect_page_object_keys(
    node: COSBase,
    object_key: tuple[str, int, int] | None,
    keys: list[tuple[str, int, int] | None],
    seen: set[int],
) -> None:
    if isinstance(node, COSObject):
        object_key = _object_key(node)
        resolved = node.get_object()
        if resolved is None:
            return
        node = resolved
    if not isinstance(node, COSDictionary):
        return
    if id(node) in seen:
        return
    seen.add(id(node))

    type_name = node.get_name(_TYPE)
    if type_name == _PAGE or (type_name != _PAGES.get_name() and not node.contains_key(_KIDS)):
        keys.append(object_key)
        return

    kids = node.get_dictionary_object(_KIDS)
    if not isinstance(kids, COSArray):
        return
    for i in range(kids.size()):
        _collect_page_object_keys(kids.get(i), None, keys, seen)


def _object_key(obj: COSObject) -> tuple[str, int, int]:
    return ("obj", obj.get_object_number(), obj.get_generation_number())


def _name_key_text(key: object) -> str | None:
    if isinstance(key, COSString):
        return key.get_string()
    if isinstance(key, COSName):
        return key.get_name()
    return None
