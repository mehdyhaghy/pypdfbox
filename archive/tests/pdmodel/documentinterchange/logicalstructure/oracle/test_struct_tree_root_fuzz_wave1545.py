"""Live PDFBox differential fuzz for PDStructureTreeRoot resolution (wave 1545).

Angle distinct from wave 1533 (StructureTreeRootFuzzProbe, accessor SHAPE: K /
kids / idtree / parent-tree presence / role-map SIZE / class-map entry shape)
and StructParentTreeProbe (whole /ParentTree dump of a real tagged PDF). This
drills into two surfaces wave 1533 only touched at "size" granularity:

* ``get_role_map()`` CONTENT — exact key->value conversion of every basic COS
  type (Name/String/Integer/Float/Boolean) and the all-or-nothing collapse to
  ``{}`` when an unconvertible value (Array/Dictionary/Null) is present. This
  pins the wave-1545 fix that made pypdfbox mirror upstream
  ``COSDictionaryMap.convertBasicTypesToMap`` (previously it only handled
  Name/String and silently DROPPED other entries instead of collapsing).

* ``get_parent_tree().get_value(k)`` — number-tree value LOOKUP over malformed
  ``/Nums`` arrays: out-of-order keys, duplicate keys, odd-size array,
  non-integer key slot (collapses the leaf), negative keys, dict-vs-array
  leaves, and absent-key lookups.

The single-hop vs multi-hop role-map RESOLUTION contract is already pinned by
``tests/.../oracle/test_role_map_resolve_oracle.py`` (upstream
``getStandardStructureType`` is single-hop). ``resolve_role_map`` is a pypdfbox
addition with no upstream equivalent, so its multi-hop behaviour is pinned here
as Python-only honest-divergence guards (see the bottom of the file).
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure import PDStructureTreeRoot
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


def _array(*values: COSBase) -> COSArray:
    out = COSArray()
    for value in values:
        out.add(value)
    return out


def _role_map_dict(*kv: object) -> COSDictionary:
    rm = COSDictionary()
    for i in range(0, len(kv) - 1, 2):
        rm.set_item(_N(str(kv[i])), kv[i + 1])  # type: ignore[arg-type]
    return rm


def _val_tag(value: object) -> str:
    """Canonical, locale/JVM-independent rendering matching the Java probe."""
    if value is None:
        return "null"
    # ``bool`` must precede ``int`` (bool is an int subclass in Python).
    if isinstance(value, bool):
        return f"bool:{'true' if value else 'false'}"
    if isinstance(value, str):
        return f"str:{value}"
    if isinstance(value, int):
        return f"int:{value}"
    if isinstance(value, float):
        # Match Java's Float.toString for the values used here (e.g. 2.5).
        return f"float:{value}"
    return f"other:{type(value).__name__}"


def _role_line(name: str, role_map: COSBase | None) -> str:
    root = COSDictionary()
    if role_map is not None:
        root.set_item(_N("RoleMap"), role_map)
    tree = PDStructureTreeRoot(root)
    rm = tree.get_role_map()
    body = ",".join(f"{k}={_val_tag(rm[k])}" for k in sorted(rm))
    return f"ROLE {name} size={len(rm)} {{{body}}}"


def _leaf_tag_normalised(value: object) -> str:
    """Both libraries expose a parent-tree leaf differently: upstream wraps it
    in ``PDParentTreeValue`` (via the typed number-tree override), pypdfbox's
    ``PDStructureElementNumberTreeNode.get_value`` returns the raw COS leaf.
    The OBSERVABLE fact is presence + leaf KIND, so normalise both sides to
    ``null`` / ``present`` here. The Java probe emits ``PDParentTreeValue`` for
    every present leaf, so the Python projection collapses any non-None leaf to
    ``present`` and the test rewrites the Java token to match."""
    return "null" if value is None else "present"


def _parent_line(name: str, nums: COSArray | None, lookups: list[int]) -> str:
    root = COSDictionary()
    pt = COSDictionary()
    if nums is not None:
        pt.set_item(_N("Nums"), nums)
    root.set_item(_N("ParentTree"), pt)
    tree = PDStructureTreeRoot(root)
    node = tree.get_parent_tree()
    parts: list[str] = []
    for k in lookups:
        value = None if node is None else node.get_value(k)
        parts.append(f"{k}->{_leaf_tag_normalised(value)}")
    return f"PT {name} {{{','.join(parts)}}}"


def _py_dump() -> str:
    lines: list[str] = []

    # ===== /RoleMap content =====
    lines.append(_role_line("absent", None))
    lines.append(_role_line("non_dict_array", COSArray()))
    lines.append(_role_line("non_dict_int", COSInteger.get(7)))
    lines.append(_role_line("empty", COSDictionary()))

    lines.append(_role_line("name_value", _role_map_dict("Custom", _N("P"))))
    lines.append(_role_line("string_value", _role_map_dict("Custom", COSString("Sect"))))
    lines.append(_role_line("int_value", _role_map_dict("Custom", COSInteger.get(3))))
    lines.append(_role_line("float_value", _role_map_dict("Custom", COSFloat(2.5))))
    lines.append(_role_line("bool_value", _role_map_dict("Custom", COSBoolean.TRUE)))

    lines.append(
        _role_line(
            "mixed",
            _role_map_dict(
                "A", _N("P"), "B", COSString("Sect"), "C", COSInteger.get(1)
            ),
        )
    )

    lines.append(_role_line("array_value", _role_map_dict("Custom", COSArray())))
    lines.append(_role_line("dict_value", _role_map_dict("Custom", COSDictionary())))
    lines.append(_role_line("null_value", _role_map_dict("Custom", COSNull.NULL)))
    lines.append(
        _role_line(
            "one_bad_among_good",
            _role_map_dict("A", _N("P"), "Bad", COSArray(), "B", _N("Sect")),
        )
    )

    lines.append(_role_line("self_map", _role_map_dict("A", _N("A"))))
    lines.append(_role_line("cycle_ab", _role_map_dict("A", _N("B"), "B", _N("A"))))
    lines.append(
        _role_line("chain", _role_map_dict("A", _N("B"), "B", _N("C"), "C", _N("P")))
    )
    lines.append(_role_line("dangling", _role_map_dict("A", _N("Missing"))))

    # ===== /ParentTree number-tree get_value() =====
    probe = [0, 1, 2, 5, -1]

    lines.append(
        _parent_line(
            "ordered",
            _array(
                COSInteger.get(0), _array(COSDictionary()),
                COSInteger.get(1), _array(COSDictionary(), COSDictionary()),
            ),
            probe,
        )
    )
    lines.append(
        _parent_line(
            "out_of_order",
            _array(
                COSInteger.get(2), _array(COSDictionary()),
                COSInteger.get(0), _array(COSDictionary()),
            ),
            probe,
        )
    )
    lines.append(
        _parent_line(
            "dup_keys",
            _array(
                COSInteger.get(1), _array(COSDictionary()),
                COSInteger.get(1), _array(COSDictionary(), COSDictionary()),
            ),
            probe,
        )
    )
    lines.append(
        _parent_line(
            "dict_leaf",
            _array(
                COSInteger.get(0), COSDictionary(),
                COSInteger.get(1), _array(COSDictionary()),
            ),
            probe,
        )
    )
    lines.append(
        _parent_line(
            "odd_size",
            _array(
                COSInteger.get(0), _array(COSDictionary()),
                COSInteger.get(1),
            ),
            probe,
        )
    )
    lines.append(
        _parent_line(
            "non_int_key",
            _array(
                _N("x"), _array(COSDictionary()),
                COSInteger.get(1), _array(COSDictionary()),
            ),
            probe,
        )
    )
    lines.append(
        _parent_line(
            "negative_key",
            _array(
                COSInteger.get(-1), _array(COSDictionary()),
                COSInteger.get(0), _array(COSDictionary()),
            ),
            [-1, 0, 1],
        )
    )
    lines.append(_parent_line("empty_nums", COSArray(), probe))
    lines.append(_parent_line("no_nums", None, probe))

    return "".join(line + "\n" for line in lines)


def _normalise_java(text: str) -> str:
    """Rewrite the Java probe's parent-tree leaf token to the normalised
    presence tag. Upstream wraps every present leaf in ``PDParentTreeValue``;
    we only assert presence + null, so collapse the wrapper to ``present``
    (see :func:`_leaf_tag_normalised`)."""
    return text.replace("->PDParentTreeValue", "->present")


@requires_oracle
def test_struct_tree_root_fuzz_matches_pdfbox() -> None:
    java = _normalise_java(run_probe_text("StructTreeRootFuzzProbe"))
    assert _py_dump() == java


def test_role_map_basic_type_conversion_collapse() -> None:
    """Non-oracle guard for the wave-1545 fix: ``get_role_map`` converts every
    basic COS type and COLLAPSES the whole map to ``{}`` on an unconvertible
    value (mirroring upstream ``convertBasicTypesToMap`` raising IOException,
    which ``getRoleMap`` swallows). The previous implementation silently
    dropped just the bad entry and ignored int/float/bool entirely."""
    # All basic scalars survive with their converted Python types.
    root = COSDictionary()
    root.set_item(
        _N("RoleMap"),
        _role_map_dict(
            "n", _N("P"),
            "s", COSString("Sect"),
            "i", COSInteger.get(4),
            "f", COSFloat(1.5),
            "b", COSBoolean.FALSE,
        ),
    )
    rm = PDStructureTreeRoot(root).get_role_map()
    assert rm == {"n": "P", "s": "Sect", "i": 4, "f": 1.5, "b": False}

    # One unconvertible entry collapses the whole map.
    bad = COSDictionary()
    bad.set_item(
        _N("RoleMap"),
        _role_map_dict("ok", _N("P"), "arr", COSArray()),
    )
    assert PDStructureTreeRoot(bad).get_role_map() == {}

    # Non-dictionary /RoleMap -> empty (getCOSDictionary returns null upstream).
    nondict = COSDictionary()
    nondict.set_item(_N("RoleMap"), COSArray())
    assert PDStructureTreeRoot(nondict).get_role_map() == {}


def test_resolve_role_map_multi_hop_is_pypdfbox_only() -> None:
    """Honest-divergence guard: ``resolve_role_map`` is a pypdfbox addition
    (no upstream equivalent — upstream ``getStandardStructureType`` is
    single-hop, pinned in test_role_map_resolve_oracle). It walks the chain,
    short-circuits on standard types, breaks cycles, and stops on a
    non-string (int/float/bool) target."""
    root = COSDictionary()
    root.set_item(
        _N("RoleMap"),
        _role_map_dict(
            "A", _N("B"),
            "B", _N("C"),
            "C", _N("P"),  # P is a standard type -> stops here
            "Self", _N("Self"),  # self-cycle
            "X", _N("Y"),  # Y -> X cycle
            "Y", _N("X"),
            "Num", COSInteger.get(9),  # non-string target
        ),
    )
    tree = PDStructureTreeRoot(root)
    # Multi-hop A -> B -> C -> P (standard, stop).
    assert tree.resolve_role_map("A") == "P"
    # Self-cycle terminates, returns the name itself.
    assert tree.resolve_role_map("Self") == "Self"
    # Two-name cycle terminates without infinite loop.
    assert tree.resolve_role_map("X") in {"X", "Y"}
    # Non-string target stops the walk at the mapping name.
    assert tree.resolve_role_map("Num") == "Num"
    # Already-standard input returned unchanged.
    assert tree.resolve_role_map("Document") == "Document"
    # None passes through.
    assert tree.resolve_role_map(None) is None
