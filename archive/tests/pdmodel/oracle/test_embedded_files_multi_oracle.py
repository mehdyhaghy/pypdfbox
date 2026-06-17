"""Live PDFBox differential parity for the *multi-attachment* embedded-files
surface: name-tree traversal across kid branches, dual ``/EF/F`` + ``/EF/UF``
embedded streams on the same file spec, ``/Desc`` round-trip, and Flate
filter chain on the embedded stream.

Backed by the Java probe ``oracle/probes/EmbeddedFilesMultiProbe.java`` —
companion to the single-rich-attachment ``EmbeddedFileDetailProbe``. Where the
detail probe pins ``/Params`` (Size / CheckSum / CreationDate / ModDate /
Subtype) on one file, this probe covers the surface those tests deliberately
do NOT exercise: multiple attachments flattened across a balanced name tree,
each with possibly two embedded slots, plus ``/Desc`` and the structural
shape (leaf count / kid count / total names) of the name tree.

The probe emits, for every embedded file (flattened + sorted by name)::

    ef \t name \t F \t UF \t Desc \t AFRelationship \t hasEFF \t hasEFUF \t
         declenF \t shaF \t declenUF \t shaUF

then a structural shape line::

    tree \t leafCount \t kidCount \t totalNames

then the catalog ``/AF`` array::

    af \t index \t F \t UF \t AFRelationship

pypdfbox reproduces the identical walk via the public PD model surface and
the test asserts the two dumps are byte-for-byte equal.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_embedded_file import PDEmbeddedFile
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary
from pypdfbox.pdmodel.pd_embedded_files_name_tree_node import (
    PDEmbeddedFilesNameTreeNode,
)
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_EF: COSName = COSName.get_pdf_name("EF")
_UF: COSName = COSName.get_pdf_name("UF")
_F: COSName = COSName.get_pdf_name("F")
_NAMES: COSName = COSName.get_pdf_name("Names")


# Three distinct attachments so a name-tree traversal regression that drops or
# reorders entries is caught. Payloads are chosen with different sizes/contents
# so SHA-1 collisions across slots are impossible.
_ATTACHMENTS: list[tuple[str, str, str, str, str, bytes]] = [
    # (tree-name, /F filename, /UF filename, /Desc, /AFRelationship, payload)
    (
        "alpha-attachment",
        "alpha.txt",
        "alpha.txt",
        "Alpha — first attachment",
        PDComplexFileSpecification.AF_RELATIONSHIP_DATA,
        b"alpha payload\n" * 4,
    ),
    (
        "beta-attachment",
        "beta.bin",
        "bêta-üñîçødé.bin",  # non-ASCII /UF
        "Bêta — middle attachment (non-ASCII /UF)",
        PDComplexFileSpecification.AF_RELATIONSHIP_SOURCE,
        bytes(range(256)) * 3,  # 768 bytes, every byte value
    ),
    (
        "gamma-attachment",
        "gamma.dat",
        "gamma.dat",
        "Gamma — final attachment",
        PDComplexFileSpecification.AF_RELATIONSHIP_SUPPLEMENT,
        b"GAMMA-DATA " * 100,
    ),
]


def _make_ef(doc: PDDocument, payload: bytes) -> PDEmbeddedFile:
    """Build a PDEmbeddedFile with the default Flate filter on its stream
    (the PDStream ctor compresses the input bytes), so the parity check
    exercises the actual filter-chain decode path on both sides."""
    return PDEmbeddedFile(doc, payload)


def _build_pdf(path: Path) -> None:
    """Create a PDF with three attachments registered in the name tree.

    The second attachment carries a dual ``/EF/F`` + ``/EF/UF`` slot to
    exercise the unicode-slot embedded-stream path (PDF 32000-1 §7.11.4 —
    a producer is allowed to supply both, typed identically). The catalog
    also carries an ``/AF`` array linking the same three specs."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())

        specs: list[PDComplexFileSpecification] = []
        names: dict[str, PDComplexFileSpecification] = {}
        for tree_name, f_name, uf_name, desc, rel, payload in _ATTACHMENTS:
            ef = _make_ef(doc, payload)
            spec = PDComplexFileSpecification()
            spec.set_file(f_name)
            spec.set_file_unicode(uf_name)
            spec.set_file_description(desc)
            spec.set_af_relationship(rel)
            spec.set_embedded_file(ef)
            # Dual-slot on "beta-attachment": same payload via /EF/UF too.
            # PDFBox 3.0.7 reads /EF/UF via getEmbeddedFileUnicode().
            if tree_name == "beta-attachment":
                ef_uf = _make_ef(doc, payload)
                spec.set_embedded_file_unicode(ef_uf)
            specs.append(spec)
            names[tree_name] = spec

        tree = PDEmbeddedFilesNameTreeNode()
        tree.set_names(names)

        catalog = doc.get_document_catalog()
        name_dict = PDDocumentNameDictionary(catalog)
        name_dict.set_embedded_files(tree)
        catalog.set_names(name_dict)

        # Catalog-level /AF — every spec linked for round-trip parity.
        catalog.set_associated_files(specs)

        doc.save(path)
    finally:
        doc.close()


def _build_kid_tree_pdf(path: Path) -> None:
    """Create a PDF whose embedded-files name tree has explicit /Kids.

    Bypass the auto-balancing in :meth:`set_names` (which only triggers
    above 64 names) by constructing the tree shape directly: a root with
    two leaf kids, each holding a slice of the attachments. This exercises
    the recursive ``get_names()`` walk that the leaf-only path does not."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())

        all_specs: list[PDComplexFileSpecification] = []
        all_names: dict[str, PDComplexFileSpecification] = {}
        for tree_name, f_name, uf_name, desc, rel, payload in _ATTACHMENTS:
            ef = _make_ef(doc, payload)
            spec = PDComplexFileSpecification()
            spec.set_file(f_name)
            spec.set_file_unicode(uf_name)
            spec.set_file_description(desc)
            spec.set_af_relationship(rel)
            spec.set_embedded_file(ef)
            all_specs.append(spec)
            all_names[tree_name] = spec

        # Split sorted keys into two leaves: ["alpha-attachment"] + the rest.
        sorted_keys = sorted(all_names)
        split = 1
        left_names = {k: all_names[k] for k in sorted_keys[:split]}
        right_names = {k: all_names[k] for k in sorted_keys[split:]}

        left_leaf = PDEmbeddedFilesNameTreeNode()
        left_leaf.set_names(left_names)
        right_leaf = PDEmbeddedFilesNameTreeNode()
        right_leaf.set_names(right_names)

        root = PDEmbeddedFilesNameTreeNode()
        root.set_kids([left_leaf, right_leaf])

        catalog = doc.get_document_catalog()
        name_dict = PDDocumentNameDictionary(catalog)
        name_dict.set_embedded_files(root)
        catalog.set_names(name_dict)
        catalog.set_associated_files(all_specs)

        doc.save(path)
    finally:
        doc.close()


# Number of attachments that forces ``set_names`` past its 64-name leaf cap so
# the auto-balancing /Kids split fires (upstream ``setNames`` would write a
# single flat /Names array regardless — see the divergence note below).
_AUTO_SPLIT_COUNT = 100


def _auto_split_payload(i: int) -> bytes:
    return f"auto-split payload #{i:03d}\n".encode() * (i % 5 + 1)


def _build_auto_split_pdf(path: Path) -> None:
    """Register ``_AUTO_SPLIT_COUNT`` attachments via a single ``set_names``
    call so pypdfbox's auto-balancing kicks in and the embedded-files tree is
    written as a multi-level /Kids structure.

    pypdfbox's ``PDNameTreeNode.set_names`` splits any map larger than 64 names
    into a balanced /Kids tree (deliberate divergence from upstream PDFBox
    ``setNames``, which always emits one flat /Names array). The oracle must
    still read every attachment back from the resulting tree."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        names: dict[str, PDComplexFileSpecification] = {}
        for i in range(_AUTO_SPLIT_COUNT):
            tree_name = f"file{i:03d}"
            payload = _auto_split_payload(i)
            ef = _make_ef(doc, payload)
            spec = PDComplexFileSpecification()
            spec.set_file(f"{tree_name}.txt")
            spec.set_file_unicode(f"{tree_name}.txt")
            spec.set_embedded_file(ef)
            names[tree_name] = spec
        tree = PDEmbeddedFilesNameTreeNode()
        tree.set_names(names)
        catalog = doc.get_document_catalog()
        name_dict = PDDocumentNameDictionary(catalog)
        name_dict.set_embedded_files(tree)
        catalog.set_names(name_dict)
        doc.save(path)
    finally:
        doc.close()


# --------------------------------------------------------------------------
# Python-side dump mirroring the probe's output line-for-line.


def _spec_detail(spec: PDComplexFileSpecification | None) -> str:
    if spec is None:
        return "-\t-\t-\t-\tN\tN\t-1\t-\t-1\t-"
    f = spec.get_file() or "-"
    uf = spec.get_file_unicode() or "-"
    desc = spec.get_file_description() or "-"
    rel = spec.get_af_relationship() or "-"

    # Probe each /EF slot independently from raw COS (don't fall back).
    fs_dict = spec.get_cos_object()
    ef_dict_base = fs_dict.get_dictionary_object(_EF)
    has_f = False
    has_uf = False
    declen_f = -1
    declen_uf = -1
    sha_f = "-"
    sha_uf = "-"
    if isinstance(ef_dict_base, COSDictionary):
        has_f = ef_dict_base.get_dictionary_object(_F) is not None
        has_uf = ef_dict_base.get_dictionary_object(_UF) is not None
    if has_f:
        ef_f = spec.get_embedded_file()
        if ef_f is not None:
            data = ef_f.to_byte_array()
            declen_f = len(data)
            sha_f = hashlib.sha1(data).hexdigest()  # noqa: S324 — parity hash
    if has_uf:
        ef_uf = spec.get_embedded_file_unicode()
        if ef_uf is not None:
            data = ef_uf.to_byte_array()
            declen_uf = len(data)
            sha_uf = hashlib.sha1(data).hexdigest()  # noqa: S324 — parity hash

    return (
        f"{f}\t{uf}\t{desc}\t{rel}\t"
        f"{'Y' if has_f else 'N'}\t{'Y' if has_uf else 'N'}\t"
        f"{declen_f}\t{sha_f}\t{declen_uf}\t{sha_uf}"
    )


def _collect(node, sink: dict[str, PDComplexFileSpecification]) -> None:
    """Flatten a name tree into ``sink`` by walking own ``/Names`` + ``/Kids``.

    Mirrors ``EmbeddedFilesMultiProbe.collect``: ``get_names()`` returns only
    this node's own leaf entries (upstream ``PDNameTreeNode.getNames()`` is
    non-recursive — see CHANGES.md), so a multi-level tree is flattened by
    also recursing through ``get_kids()``."""
    leaf = node.get_names()
    if leaf:
        sink.update(leaf)
    kids = node.get_kids()
    if kids is not None:
        for kid in kids:
            _collect(kid, sink)


def _walk_shape(node, counters: dict[str, int]) -> None:
    dict_ = node.get_cos_object()
    if isinstance(dict_.get_dictionary_object(_NAMES), COSArray):
        counters["leaf"] += 1
    if isinstance(dict_.get_dictionary_object(COSName.KIDS), COSArray):
        counters["kid"] += 1
    kids = node.get_kids()
    if kids is not None:
        for kid in kids:
            _walk_shape(kid, counters)


def _pypdfbox_dump(path: Path) -> str:
    doc = PDDocument.load(path)
    try:
        catalog = doc.get_document_catalog()
        lines: list[str] = []

        name_dict = catalog.get_names()
        flat: dict[str, PDComplexFileSpecification] = {}
        root = None
        if name_dict is not None:
            root = name_dict.get_embedded_files()
            if root is not None:
                _collect(root, flat)
        for name in sorted(flat):
            lines.append(f"ef\t{name}\t{_spec_detail(flat[name])}")

        counters = {"leaf": 0, "kid": 0}
        if root is not None:
            _walk_shape(root, counters)
        lines.append(f"tree\t{counters['leaf']}\t{counters['kid']}\t{len(flat)}")

        for i, spec in enumerate(catalog.get_associated_files()):
            f = "-"
            uf = "-"
            rel = "-"
            if isinstance(spec, PDComplexFileSpecification):
                f = spec.get_file() or "-"
                uf = spec.get_file_unicode() or "-"
                rel = spec.get_af_relationship() or "-"
            lines.append(f"af\t{i}\t{f}\t{uf}\t{rel}")

        return "".join(line + "\n" for line in lines)
    finally:
        doc.close()


# --------------------------------------------------------------------------
# Tests.


@requires_oracle
def test_multi_attachment_matches_pdfbox(tmp_path):
    """Three attachments flattened in a single leaf, with one carrying a
    dual /EF/F + /EF/UF embedded stream, all Flate-compressed."""
    pdf = tmp_path / "embedded_multi.pdf"
    _build_pdf(pdf)
    java = run_probe_text("EmbeddedFilesMultiProbe", str(pdf))
    py = _pypdfbox_dump(pdf)
    assert py == java


@requires_oracle
def test_kid_tree_traversal_matches_pdfbox(tmp_path):
    """Two leaf kids under a single root — exercises the recursive
    ``get_names()`` flatten that the leaf-only test cannot."""
    pdf = tmp_path / "embedded_kid_tree.pdf"
    _build_kid_tree_pdf(pdf)
    java = run_probe_text("EmbeddedFilesMultiProbe", str(pdf))
    py = _pypdfbox_dump(pdf)
    assert py == java


@requires_oracle
def test_flate_decoded_bytes_round_trip(tmp_path):
    """Pin the decoded payload of every attachment to its known SHA-1 so a
    Flate filter regression on the embedded-file stream is caught even if
    the Java probe drifted identically."""
    pdf = tmp_path / "embedded_multi.pdf"
    _build_pdf(pdf)
    py = _pypdfbox_dump(pdf)

    # Build name -> expected SHA-1 from the source payloads.
    expected_sha: dict[str, str] = {}
    expected_len: dict[str, int] = {}
    expected_uf_sha: dict[str, str] = {}
    for tree_name, _f, _uf, _desc, _rel, payload in _ATTACHMENTS:
        expected_sha[tree_name] = hashlib.sha1(payload).hexdigest()  # noqa: S324
        expected_len[tree_name] = len(payload)
        if tree_name == "beta-attachment":
            expected_uf_sha[tree_name] = hashlib.sha1(payload).hexdigest()  # noqa: S324

    for line in py.splitlines():
        if not line.startswith("ef\t"):
            continue
        cols = line.split("\t")
        # ef name F UF Desc AFRel hasEFF hasEFUF declenF shaF declenUF shaUF
        name = cols[1]
        has_f = cols[6]
        sha_f = cols[9]
        len_f = int(cols[8])
        assert has_f == "Y", name
        assert sha_f == expected_sha[name], name
        assert len_f == expected_len[name], name
        if name in expected_uf_sha:
            assert cols[7] == "Y"  # hasEFUF
            assert cols[11] == expected_uf_sha[name]
            assert int(cols[10]) == expected_len[name]
        else:
            assert cols[7] == "N"


@requires_oracle
def test_desc_and_af_relationship_round_trip(tmp_path):
    """Independent of the oracle string: pin /Desc + /AFRelationship for every
    attachment and the /AF array linkage."""
    pdf = tmp_path / "embedded_multi.pdf"
    _build_pdf(pdf)
    py = _pypdfbox_dump(pdf)
    by_name: dict[str, list[str]] = {}
    af_lines: list[list[str]] = []
    for line in py.splitlines():
        cols = line.split("\t")
        if cols[0] == "ef":
            by_name[cols[1]] = cols
        elif cols[0] == "af":
            af_lines.append(cols)
    for tree_name, f_name, uf_name, desc, rel, _payload in _ATTACHMENTS:
        cols = by_name[tree_name]
        assert cols[2] == f_name
        assert cols[3] == uf_name
        assert cols[4] == desc
        assert cols[5] == rel
    # /AF round-trips the three specs in insertion order.
    assert len(af_lines) == len(_ATTACHMENTS)
    for i, (_tree, f_name, uf_name, _desc, rel, _payload) in enumerate(_ATTACHMENTS):
        assert af_lines[i][1] == str(i)
        assert af_lines[i][2] == f_name
        assert af_lines[i][3] == uf_name
        assert af_lines[i][4] == rel


@requires_oracle
def test_kid_tree_shape_is_two_leaves(tmp_path):
    """Pin the structural shape of the kid-tree build path: root with 2 kids,
    each a leaf carrying /Names. PDFBox flattens both into the same 3-name
    map regardless."""
    pdf = tmp_path / "embedded_kid_tree.pdf"
    _build_kid_tree_pdf(pdf)
    py = _pypdfbox_dump(pdf)
    tree_line = next(line for line in py.splitlines() if line.startswith("tree\t"))
    cols = tree_line.split("\t")
    # tree leafCount kidCount totalNames
    assert int(cols[1]) == 2  # two leaf nodes
    assert int(cols[2]) == 1  # one internal node with /Kids
    assert int(cols[3]) == len(_ATTACHMENTS)


@requires_oracle
def test_auto_split_tree_is_readable_by_pdfbox(tmp_path):
    """DIVERGENCE PIN: pypdfbox's ``set_names`` auto-splits a >64-name map into
    a balanced /Kids tree (upstream ``setNames`` always writes one flat /Names
    array). Verify the auto-balanced multi-level tree pypdfbox produces is read
    back identically by Java PDFBox 3.0.7 — the dumps must be byte-for-byte
    equal across every flattened attachment and the structural shape line."""
    pdf = tmp_path / "embedded_auto_split.pdf"
    _build_auto_split_pdf(pdf)
    java = run_probe_text("EmbeddedFilesMultiProbe", str(pdf))
    py = _pypdfbox_dump(pdf)
    assert py == java


@requires_oracle
def test_auto_split_tree_oracle_reads_all_names(tmp_path):
    """Oracle-confirmed: every one of the ``_AUTO_SPLIT_COUNT`` attachments is
    enumerated by PDFBox from the auto-balanced tree, and the structural shape
    line reports a real /Kids split (kidCount >= 1, leafCount > 1)."""
    pdf = tmp_path / "embedded_auto_split.pdf"
    _build_auto_split_pdf(pdf)
    java = run_probe_text("EmbeddedFilesMultiProbe", str(pdf))
    ef_lines = [ln for ln in java.splitlines() if ln.startswith("ef\t")]
    assert len(ef_lines) == _AUTO_SPLIT_COUNT
    # Names enumerated by PDFBox cover the full set, sorted.
    names = [ln.split("\t")[1] for ln in ef_lines]
    assert names == [f"file{i:03d}" for i in range(_AUTO_SPLIT_COUNT)]
    tree_line = next(ln for ln in java.splitlines() if ln.startswith("tree\t"))
    cols = tree_line.split("\t")
    # tree leafCount kidCount totalNames — a genuine multi-level split.
    assert int(cols[1]) > 1  # more than one leaf
    assert int(cols[2]) >= 1  # at least one internal /Kids node
    assert int(cols[3]) == _AUTO_SPLIT_COUNT


def test_auto_split_write_shape_is_kids_tree_not_flat(tmp_path):
    """Non-oracle pin of the deliberate write-shape divergence: ``set_names``
    with >64 embedded files writes a root carrying /Kids (no own /Names),
    NOT a single flat /Names array the way upstream ``setNames`` would. The
    saved file round-trips through pypdfbox's own reader to all names."""
    pdf = tmp_path / "embedded_auto_split.pdf"
    _build_auto_split_pdf(pdf)
    doc = PDDocument.load(pdf)
    try:
        root = doc.get_document_catalog().get_names().get_embedded_files()
        root_dict = root.get_cos_object()
        # Root is a /Kids node, not a flat /Names leaf.
        assert isinstance(root_dict.get_dictionary_object(COSName.KIDS), COSArray)
        assert root_dict.get_dictionary_object(_NAMES) is None
        # All attachments are still reachable via the flatten walk.
        flat: dict[str, PDComplexFileSpecification] = {}
        _collect(root, flat)
        assert sorted(flat) == [f"file{i:03d}" for i in range(_AUTO_SPLIT_COUNT)]
    finally:
        doc.close()
