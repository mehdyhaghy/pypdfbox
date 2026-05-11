"""Port of ``SplitBooklet`` (upstream ``SplitBooklet.java`` lines
33-97).

Splits each page of a "booklet"-style PDF in half via crop-box trims so
the output document holds twice as many pages, each showing one half of
the original.
"""

from __future__ import annotations

import sys

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


class SplitBooklet:
    """Mirrors ``SplitBooklet`` (final, package-private constructor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/util/
    SplitBooklet.java`` (lines 33-97).
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 43)."""
        argv = list(argv) if argv else []
        if len(argv) < 2:
            SplitBooklet.usage()
            raise SystemExit(-1)
        SplitBooklet.split(argv[0], argv[1])

    @staticmethod
    def split(src: str, dst: str) -> None:
        """Open ``src``, split each page in half, save the result to
        ``dst``. Promoted from the upstream inline ``main`` body."""
        with PDDocument.load(src) as document:
            outdoc = PDDocument()
            try:
                for page in document.get_pages():
                    crop_box_orig = page.get_crop_box()

                    # Re-wrap the COS array twice so each crop box is an
                    # independent COSArray and edits don't bleed. Upstream
                    # uses ``new PDRectangle(cropBox.getCOSArray())`` which
                    # maps to :meth:`PDRectangle.from_cos_array` in
                    # pypdfbox.
                    crop_box_left = PDRectangle.from_cos_array(
                        crop_box_orig.get_cos_array(),
                    )
                    crop_box_right = PDRectangle.from_cos_array(
                        crop_box_orig.get_cos_array(),
                    )

                    rotation = page.get_rotation()
                    if rotation in (90, 270):
                        crop_box_left.set_upper_right_y(
                            crop_box_orig.get_lower_left_y()
                            + crop_box_orig.get_height() / 2,
                        )
                        crop_box_right.set_lower_left_y(
                            crop_box_orig.get_lower_left_y()
                            + crop_box_orig.get_height() / 2,
                        )
                    else:
                        crop_box_left.set_upper_right_x(
                            crop_box_orig.get_lower_left_x()
                            + crop_box_orig.get_width() / 2,
                        )
                        crop_box_right.set_lower_left_x(
                            crop_box_orig.get_lower_left_x()
                            + crop_box_orig.get_width() / 2,
                        )

                    if rotation in (180, 270):
                        page_right = outdoc.import_page(page)
                        page_right.set_crop_box(crop_box_right)
                        page_left = outdoc.import_page(page)
                        page_left.set_crop_box(crop_box_left)
                    else:
                        page_left = outdoc.import_page(page)
                        page_left.set_crop_box(crop_box_left)
                        page_right = outdoc.import_page(page)
                        page_right.set_crop_box(crop_box_right)

                outdoc.save(dst)
            finally:
                outdoc.close()

    @staticmethod
    def usage() -> None:
        """Print the usage message — mirrors the private ``usage()``
        helper (line 92)."""
        sys.stderr.write("Usage: SplitBooklet <input-pdf> <output-pdf>\n")


if __name__ == "__main__":  # pragma: no cover
    SplitBooklet.main(sys.argv[1:])
