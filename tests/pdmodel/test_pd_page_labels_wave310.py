from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel import PDDocument, PDPageLabelRange, PDPageLabels


def _name(name: str) -> COSName:
    return COSName.get_pdf_name(name)


def test_malformed_kids_hide_same_node_nums_wave310() -> None:
    # Upstream PDNumberTreeNode.getKids() turns a non-dictionary kid into an
    # empty node, and a node with /Kids never has its /Nums read (PDFBOX-6296).
    nums = COSArray()
    nums.add(COSInteger.get(2))
    range_dict = COSDictionary()
    range_dict.set_name(_name("S"), PDPageLabelRange.STYLE_ROMAN_UPPER)
    range_dict.set_int(_name("St"), 4)
    nums.add(range_dict)

    root = COSDictionary()
    kids = COSArray()
    kids.add(COSString("not-a-number-tree-node"))
    kids.add(COSInteger.get(9))
    root.set_item(_name("Kids"), kids)
    root.set_item(_name("Nums"), nums)

    with PDDocument() as doc:
        labels = PDPageLabels(doc, root)

        assert labels.get_page_label_range(2) is None
        assert labels.get_page_indices() == [0]
        assert labels.get_label_for_page(2) == "3"
