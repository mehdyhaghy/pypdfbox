"""PDFBOX-6274 / PDFBOX-6275 (3.0 branch, unreleased 3.0.9): the flattened
recursive ``get_tree_as_map`` on name and number tree nodes."""

from pypdfbox.cos import COSBase, COSDictionary, COSInteger
from pypdfbox.pdmodel.common.pd_number_tree_node import PDNumberTreeNode
from pypdfbox.pdmodel.common.pd_string_name_tree_node import PDStringNameTreeNode


class _IntNumberTreeNode(PDNumberTreeNode[int]):
    def convert_cos_to_value(self, base: COSBase) -> int:
        assert isinstance(base, COSInteger)
        return int(base.value)

    def convert_value_to_cos(self, value: int) -> COSBase:
        return COSInteger.get(value)

    def create_child_node(self, dic: COSDictionary) -> _IntNumberTreeNode:
        return _IntNumberTreeNode(dic)


def test_name_tree_as_map_empty_node_is_empty_dict() -> None:
    assert PDStringNameTreeNode().get_tree_as_map() == {}


def test_name_tree_as_map_flattens_all_levels() -> None:
    root = PDStringNameTreeNode()
    kid1 = PDStringNameTreeNode()
    kid1.set_names({"a": "1", "b": "2"})
    kid2 = PDStringNameTreeNode()
    grandkid = PDStringNameTreeNode()
    grandkid.set_names({"c": "3"})
    kid2.set_kids([grandkid])
    root.set_kids([kid1, kid2])

    # get_names reads only THIS level, get_tree_as_map reads ALL levels.
    assert root.get_names() is None
    tree = root.get_tree_as_map()
    assert tree == {"a": "1", "b": "2", "c": "3"}
    assert list(tree) == ["a", "b", "c"]


def test_name_tree_as_map_returns_a_copy() -> None:
    leaf = PDStringNameTreeNode()
    leaf.set_names({"x": "y"})
    tree = leaf.get_tree_as_map()
    tree["z"] = "w"
    assert leaf.get_tree_as_map() == {"x": "y"}


def test_number_tree_as_map_empty_node_is_empty_dict() -> None:
    assert _IntNumberTreeNode().get_tree_as_map() == {}


def test_number_tree_as_map_flattens_all_levels() -> None:
    root = _IntNumberTreeNode()
    kid1 = _IntNumberTreeNode()
    kid1.set_numbers({0: 10, 1: 11})
    kid2 = _IntNumberTreeNode()
    grandkid = _IntNumberTreeNode()
    grandkid.set_numbers({5: 15, 7: 17})
    kid2.set_kids([grandkid])
    root.set_kids([kid1, kid2])

    tree = root.get_tree_as_map()
    assert tree == {0: 10, 1: 11, 5: 15, 7: 17}
    assert list(tree) == [0, 1, 5, 7]


def test_number_tree_as_map_returns_a_copy() -> None:
    leaf = _IntNumberTreeNode()
    leaf.set_numbers({3: 4})
    tree = leaf.get_tree_as_map()
    tree[9] = 9
    assert leaf.get_tree_as_map() == {3: 4}
