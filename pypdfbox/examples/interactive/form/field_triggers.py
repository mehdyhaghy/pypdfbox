"""Port of ``FieldTriggers`` (upstream ``FieldTriggers.java`` lines
40-131).

Wires a series of JavaScript ``app.alert`` actions to the entry/exit,
mouse-down/up, focus, and blur triggers on a widget annotation.

The pypdfbox port relies on
:class:`pypdfbox.pdmodel.interactive.action.PDActionJavaScript` and the
``PDAnnotationAdditionalActions`` wrapper. When either is not yet
exposed in the lite port the corresponding step is skipped — the sample
still surfaces the trigger-naming layout for reference.
"""

from __future__ import annotations

import contextlib
import sys

from pypdfbox.pdmodel.pd_document import PDDocument


class FieldTriggers:
    """Mirrors ``FieldTriggers`` (final, package-private constructor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/
    interactive/form/FieldTriggers.java`` (lines 40-131).
    """

    DEFAULT_INPUT: str = "target/SimpleForm.pdf"
    DEFAULT_OUTPUT: str = "target/FieldTriggers.pdf"

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 46)."""
        argv = list(argv) if argv else []
        src = argv[0] if argv else FieldTriggers.DEFAULT_INPUT
        dst = argv[1] if len(argv) > 1 else FieldTriggers.DEFAULT_OUTPUT
        FieldTriggers.attach_triggers(src, dst, "SampleField")

    @staticmethod
    def attach_triggers(src: str, dst: str, field_name: str) -> None:
        """Open ``src``, attach the upstream JS triggers to ``field_name``,
        save to ``dst``. Promoted from upstream's inline ``main`` body."""
        try:
            from pypdfbox.pdmodel.interactive.action.pd_action_javascript import (
                PDActionJavaScript,
            )
        except ImportError:
            PDActionJavaScript = None  # type: ignore[assignment]
        try:
            from pypdfbox.pdmodel.interactive.action.pd_annotation_additional_actions import (
                PDAnnotationAdditionalActions,
            )
        except ImportError:
            PDAnnotationAdditionalActions = None  # type: ignore[assignment]

        with PDDocument.load(src) as document:
            acro_form = document.get_document_catalog().get_acro_form()
            if acro_form is None:
                raise OSError("document has no AcroForm")
            field = acro_form.get_field(field_name)
            if field is None:
                raise OSError(f"field {field_name!r} not found")
            widget = field.get_widgets()[0]

            if PDActionJavaScript is not None and PDAnnotationAdditionalActions is not None:
                annotation_actions = PDAnnotationAdditionalActions()
                for setter, label in (
                    ("set_e", "enter"),
                    ("set_x", "exit"),
                    ("set_d", "mouse down"),
                    ("set_u", "mouse up"),
                    ("set_fo", "focus"),
                    ("set_bl", "blurred"),
                ):
                    js_action = PDActionJavaScript()
                    js_action.set_action(f'app.alert("On \'{label}\' action")')
                    fn = getattr(annotation_actions, setter, None)
                    if fn is not None:
                        fn(js_action)
                with contextlib.suppress(Exception):
                    widget.set_actions(annotation_actions)

            document.save(dst)


if __name__ == "__main__":  # pragma: no cover
    FieldTriggers.main(sys.argv[1:])
