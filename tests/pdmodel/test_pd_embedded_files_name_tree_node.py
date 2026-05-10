"""Hand-written tests for ``PDEmbeddedFilesNameTreeNode``. Covers the
typed convertCOSToPD/createChildNode contract and the inherited generic
name-tree behaviour as exercised through the embedded-files subclass.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.pd_embedded_files_name_tree_node import (
    PDEmbeddedFilesNameTreeNode,
)

_NAMES = COSName.get_pdf_name("Names")
_KIDS = COSName.KIDS  # type: ignore[attr-defined]


def _spec(filename: str) -> PDComplexFileSpecification:
    fs = PDComplexFileSpecification()
    fs.set_file(filename)
    return fs


def test_set_names_round_trips_to_complex_file_spec() -> None:
    tree = PDEmbeddedFilesNameTreeNode()
    tree.set_names({"hello.txt": _spec("hello.txt"), "data.bin": _spec("data.bin")})

    names = tree.get_names()
    assert names is not None
    assert set(names) == {"hello.txt", "data.bin"}
    assert isinstance(names["hello.txt"], PDComplexFileSpecification)
    assert names["hello.txt"].get_file() == "hello.txt"
    assert names["data.bin"].get_file() == "data.bin"


def test_get_value_resolves_typed_spec() -> None:
    tree = PDEmbeddedFilesNameTreeNode()
    tree.set_names({"a.txt": _spec("a.txt")})

    resolved = tree.get_value("a.txt")
    assert isinstance(resolved, PDComplexFileSpecification)
    assert resolved.get_file() == "a.txt"
    assert tree.get_value("missing") is None


def test_create_child_node_returns_same_type() -> None:
    tree = PDEmbeddedFilesNameTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, PDEmbeddedFilesNameTreeNode)


def test_convert_cos_to_value_rejects_non_dictionary() -> None:
    """Mirrors upstream: a leaf value that is not a COSDictionary raises."""
    tree = PDEmbeddedFilesNameTreeNode()
    with pytest.raises(OSError):
        tree.convert_cos_to_value(COSString("not a dict"))


def test_get_names_walks_kids() -> None:
    leaf_one = PDEmbeddedFilesNameTreeNode()
    leaf_one.set_names({"a.txt": _spec("a.txt")})
    leaf_two = PDEmbeddedFilesNameTreeNode()
    leaf_two.set_names({"z.bin": _spec("z.bin")})
    root = PDEmbeddedFilesNameTreeNode()
    root.set_kids([leaf_one, leaf_two])

    # Root has /Kids only, no /Names.
    assert root.get_cos_object().get_dictionary_object(_NAMES) is None
    assert isinstance(root.get_cos_object().get_dictionary_object(_KIDS), COSArray)

    # get_names flattens through kids; get_value walks via /Limits.
    assert set(root.get_names() or {}) == {"a.txt", "z.bin"}
    assert root.get_value("a.txt").get_file() == "a.txt"
    assert root.get_value("z.bin").get_file() == "z.bin"


def test_round_trip_via_existing_cos_dictionary() -> None:
    """Wrap a hand-built /Names dictionary through the embedded-files
    subclass and verify the typed accessor materialises COMPLEX file specs."""
    spec_dict = _spec("inline.txt").get_cos_object()
    arr = COSArray()
    arr.add(COSString("inline.txt"))
    arr.add(spec_dict)
    raw = COSDictionary()
    raw.set_item(_NAMES, arr)

    tree = PDEmbeddedFilesNameTreeNode(raw)
    fetched = tree.get_value("inline.txt")
    assert isinstance(fetched, PDComplexFileSpecification)
    assert fetched.get_file() == "inline.txt"
    assert fetched.get_cos_object() is spec_dict


def test_convert_cos_to_pd_returns_complex_file_spec() -> None:
    """``convert_cos_to_pd`` is the snake_case alias of upstream
    ``convertCOSToPD`` — typed-equivalent of ``convert_cos_to_value``."""
    tree = PDEmbeddedFilesNameTreeNode()
    spec_dict = _spec("alias.txt").get_cos_object()
    resolved = tree.convert_cos_to_pd(spec_dict)
    assert isinstance(resolved, PDComplexFileSpecification)
    assert resolved.get_file() == "alias.txt"


def test_convert_cos_to_pd_rejects_non_dictionary() -> None:
    """Upstream contract: non-COSDictionary leaves raise IOException →
    OSError in pypdfbox."""
    tree = PDEmbeddedFilesNameTreeNode()
    with pytest.raises(OSError):
        tree.convert_cos_to_pd(COSString("nope"))
