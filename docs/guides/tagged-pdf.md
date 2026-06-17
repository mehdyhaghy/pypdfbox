# Tagged PDF and accessibility

Pypdfbox ports the
[`pypdfbox.pdmodel.documentinterchange.logicalstructure`](../api/pdmodel.md)
package and the standard structure attribute owners under
`taggedpdf`. Together they cover the PDF 32000-1 §14.7 (Logical
Structure) and §14.8 (Tagged PDF) tagging surfaces.

## Read the StructTreeRoot

```python
from pypdfbox.pdmodel import PDDocument

with PDDocument.load("tagged.pdf") as doc:
    catalog = doc.get_document_catalog()
    root = catalog.get_struct_tree_root()
    if root is None:
        print("Untagged document.")
    else:
        print("kids:", root.count_kids())
        print("role-map:", root.get_role_map())
```

The catalog's `/StructTreeRoot` entry is the entry point. `count_kids()`
returns the immediate child count; `has_id_tree()` /
`has_parent_tree()` predicates report whether the auxiliary lookups
are populated.

## Iterate structure elements

`iter_descendants()` does a depth-first walk over every
`PDStructureElement` reachable from the root:

```python
for element in root.iter_descendants():
    indent = "  " * element.get_revision_number()
    structure_type = element.get_standard_structure_type() or element.get_structure_type()
    label = element.get_title() or element.get_actual_text() or ""
    print(f"{indent}{structure_type}: {label!r}")
```

`get_standard_structure_type()` first applies the catalog's role map
to resolve a custom tag back to a standard PDF tag (`P`, `H1`, `LI`,
`Table`, etc.).

## Find an element by ID

The `/IDTree` maps `ID` strings to elements. Use the lookup helper
to avoid walking the tree manually:

```python
target = root.get_struct_element_for_id("section-3")
if target is not None:
    print(target.get_standard_structure_type(), target.get_title())
```

`get_struct_element_for_mcid(page, mcid)` does the same lookup against
a page + marked-content identifier pair via the parent-tree.

## Standard structure types

Pypdfbox exposes the upstream
`StandardStructureTypes` enum so you can compare without hand-coding
the names:

```python
from pypdfbox.pdmodel.documentinterchange.logicalstructure.standard_structure_types import (
    StandardStructureTypes,
)

headings = list(root.find_by_role(StandardStructureTypes.H1))
print(len(headings), "H1 headings")
```

`find_by_role` filters descendants whose resolved (role-map-applied)
type matches; `find_first_by_role` returns the first match or `None`.

## Attribute objects

Structure attributes attach typed metadata to an element. The
upstream subclasses for the five standard attribute owners are
ported: `Layout`, `List`, `PrintField`, `Table`, and `ExportFormat`.

```python
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_layout_attribute_object import (
    PDLayoutAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_list_attribute_object import (
    PDListAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_print_field_attribute_object import (
    PDPrintFieldAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_table_attribute_object import (
    PDTableAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_export_format_attribute_object import (
    PDExportFormatAttributeObject,
)

layout = PDLayoutAttributeObject()
layout.set_placement("Block")
layout.set_writing_mode("LrTb")
layout.set_text_align("Center")

list_attr = PDListAttributeObject()
list_attr.set_list_numbering("Decimal")

table_attr = PDTableAttributeObject()
table_attr.set_row_span(2)
table_attr.set_column_span(3)

print_attr = PDPrintFieldAttributeObject()
print_attr.set_role("cb")        # checkbox
print_attr.set_checked("on")
print_attr.set_description("Subscribe to newsletter")

export = PDExportFormatAttributeObject()
export.set_placement("Block")
```

Attach the attribute object to a structure element via
`element.add_attribute(attribute)` — the `/A` entry can hold either
a single dictionary or an array of them.

`PDExportFormatAttributeObject` inherits from `PDLayoutAttributeObject`
so it carries every layout setter plus its own ExportFormat-specific
keys; `PDStandardAttributeObject` is the shared base class.

## Mark info: /Marked, /UserProperties, /Suspects

The catalog's `/MarkInfo` dictionary advertises whether a document
is tagged and which optional features are in use:

```python
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_mark_info import (
    PDMarkInfo,
)

mark_info = doc.get_document_catalog().get_mark_info()
if mark_info is None:
    mark_info = PDMarkInfo()
    doc.get_document_catalog().set_mark_info(mark_info)

mark_info.set_marked(True)            # the document is Tagged PDF
mark_info.set_user_properties(True)   # contains /UserProperties attributes
mark_info.set_suspects(False)         # no suspect content blocks
```

`mark_info.is_tagged()` is an alias for `is_marked()` aligning with
the PDF 32000-1 §14.7 *Tagged PDF* terminology. Predicate helpers
distinguish "key absent (default false)" from "key explicitly false":
`has_marked()`, `has_user_properties()`, `has_suspects()`. Drop an
explicit value with the matching `clear_*()` helper.

`mark_info.is_empty()` returns True when the dictionary holds no
entries — useful for serialisers that elide vacant optional
dictionaries from the catalog.

## See also

- [API reference: `pypdfbox.pdmodel`](../api/pdmodel.md)
- [Documentation index](../index.md)
