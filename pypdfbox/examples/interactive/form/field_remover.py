"""Port of ``FieldRemover`` (upstream ``FieldRemover.java`` lines 39-161).

Removes an AcroForm field by fully-qualified name and strips its widget
annotations from any pages that referenced them.
"""

from __future__ import annotations

import sys

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.form.pd_field import PDField
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.pd_document import PDDocument


class FieldRemover:
    """Mirrors ``FieldRemover`` (public no-arg constructor, line 41).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/
    interactive/form/FieldRemover.java`` (lines 39-161).
    """

    def __init__(self) -> None:
        # Mirrors upstream's empty default constructor.
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 46)."""
        argv = list(argv) if argv else []
        if len(argv) != 3:
            FieldRemover.usage()
            return
        FieldRemover().remove(argv[0], argv[1], argv[2])

    def remove_recursive(
        self, fields: list[PDField], field: PDField
    ) -> bool:
        """Walk the field tree under ``fields`` and remove ``field``.

        Promoted from upstream's ``private boolean removeRecursive`` so
        tests can drive it directly (line 66)."""
        for field_item in fields:
            if isinstance(field_item, PDNonTerminalField):
                children = field_item.get_children()
                if field in children:
                    children.remove(field)
                    field_item.set_children(children)
                    return True
                if self.remove_recursive(children, field):
                    return True
        return False

    def remove(
        self, src: str, dst: str, fully_qualified_fieldname: str
    ) -> bool:
        """Open ``src``, remove ``fully_qualified_fieldname``, save the
        result to ``dst``. Returns ``True`` when the field was located and
        removed. Mirrors upstream's ``remove`` (line 98)."""
        with PDDocument.load(src) as doc:
            widget_set: list = []
            acro_form = doc.get_document_catalog().get_acro_form()
            if acro_form is None:
                return False
            field = acro_form.get_field(fully_qualified_fieldname)
            if field is None:
                sys.stdout.write(
                    f"field '{fully_qualified_fieldname}' not found\n",
                )
                return False
            fields = acro_form.get_fields()
            removed = False
            # Compare via underlying COS so wrapper identity mismatches
            # (PDField is rebuilt on each ``get_field`` / ``get_fields``)
            # don't hide the match.
            field_cos = field.get_cos_object()
            for f in list(fields):
                if f.get_cos_object() is field_cos:
                    fields.remove(f)
                    removed = True
                    break
            if not removed:
                removed = self.remove_recursive(fields, field)
            if removed:
                # ``get_fields()`` returns a fresh list — push the trimmed
                # list back through ``set_fields`` so the form COS reflects
                # the removal on save.
                acro_form.set_fields(fields)
            if removed:
                widgets = field.get_widgets()
                widget_set.extend(widgets)
            # ``widget.get_page()`` returns a COSDictionary in pypdfbox
            # whereas upstream returns a typed PDPage; rather than
            # round-tripping through a wrapper, walk every page and remove
            # the widget annotation wherever it appears.
            if widget_set:
                for page in doc.get_pages():
                    annotations = page.get_annotations()
                    for w in widget_set:
                        if w in annotations:
                            annotations.remove(w)
            if removed:
                doc.set_all_security_to_be_removed(True)
                doc.get_document_catalog().get_cos_object().remove_item(
                    COSName.get_pdf_name("Perms")
                )
                doc.save(dst)
            return removed

    @staticmethod
    def usage() -> None:
        """Print the upstream usage message — mirrors the private
        ``usage()`` helper (line 157)."""
        sys.stderr.write(
            "usage: org.apache.pdfbox.examples.interactive.form.RemoveField "
            "<pdf-file> <saved-pdf-file> <fully-qualified-field-name>\n",
        )


if __name__ == "__main__":  # pragma: no cover
    FieldRemover.main(sys.argv[1:])
