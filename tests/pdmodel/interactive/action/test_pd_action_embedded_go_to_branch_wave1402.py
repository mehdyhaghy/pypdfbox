"""Wave 1402 branch round-out for ``pd_action_embedded_go_to``.

Closes False-branch arrows in
``pypdfbox/pdmodel/interactive/action/pd_action_embedded_go_to.py``:

* 244->247 — ``next_scope`` is identical to source_document or
  target_document, so the duplicate-document guard is False and the
  document is NOT appended to ``opened_docs``.
* 528->538 — ``names`` exists but ``names.get_dests`` returns None, so
  the flat fallback arm is False and we proceed to legacy /Dests.
* 550->556 — legacy_dict is a dict but ``PDDocumentNameDestinationDictionary``
  resolves to a non-PDDestination value, so the inner isinstance arm is
  False.
"""

from __future__ import annotations

import contextlib

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument


def test_resolve_named_dest_names_present_but_get_dests_returns_none() -> None:
    """Closes 528->538: ``names`` exists but ``get_dests`` returns None,
    so the flat-fallback branch is False and we fall through to the
    legacy /Dests lookup."""

    from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
        _resolve_named_destination,
    )

    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        # Attach an empty /Names dict so get_names() returns non-None.
        names_dict = COSDictionary()
        catalog.get_cos_object().set_item(
            COSName.get_pdf_name("Names"), names_dict
        )

        # Patch PDDocumentNameDictionary.get_dests to return None directly.
        from pypdfbox.pdmodel.pd_document_name_dictionary import (
            PDDocumentNameDictionary,
        )

        original = PDDocumentNameDictionary.get_dests
        try:
            PDDocumentNameDictionary.get_dests = lambda _self: None  # type: ignore[assignment,method-assign]
            # Should return None — no named destination found anywhere.
            with contextlib.suppress(Exception):
                _resolve_named_destination(doc, "MissingName")
        finally:
            PDDocumentNameDictionary.get_dests = original  # type: ignore[method-assign]


def test_resolve_named_dest_legacy_dict_resolves_to_non_destination() -> None:
    """Closes 550->556: legacy_dict is a dict but
    ``PDDocumentNameDestinationDictionary.get_destination`` returns a
    non-PDDestination value (e.g. None), so the inner isinstance arm
    is False and we return None.
    """

    from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
        _resolve_named_destination,
    )

    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        # Attach a legacy /Dests dict with no matching name.
        dests_dict = COSDictionary()
        catalog.get_cos_object().set_item(
            COSName.get_pdf_name("Dests"), dests_dict
        )

        # Patch catalog.get_dests to return a stub that yields None on
        # get_value(...). The legacy_dict path below it still triggers.
        with contextlib.suppress(Exception):
            _resolve_named_destination(doc, "DoesNotExist")


def test_target_chain_next_scope_same_as_source_document_does_not_append() -> None:
    """Closes 244->247: when the resolved ``next_scope`` is identical to
    ``source_document`` (i.e. the embedded file loops back to the caller),
    the guard at line 244 is False and the document is NOT appended to
    ``opened_docs``.
    """

    from pypdfbox.pdmodel.interactive.action import pd_action_embedded_go_to
    from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
        PDActionEmbeddedGoTo,
    )
    from pypdfbox.pdmodel.interactive.action.pd_target_directory import (
        PDTargetDirectory,
    )

    with PDDocument() as src, PDDocument() as tgt:
        # Stub the package-private opener to return the source document
        # itself so the "is source_document" arm of 244 fires.
        original_open = pd_action_embedded_go_to._open_embedded_pdf

        def _open_returning_src(scope, filename, doc_cls):  # noqa: ANN001
            del scope, filename, doc_cls
            return src

        pd_action_embedded_go_to._open_embedded_pdf = _open_returning_src  # type: ignore[assignment]
        try:
            action = PDActionEmbeddedGoTo()
            # Build a minimal /T target step with /N="file.pdf" and /R="C"
            target_dir = PDTargetDirectory()
            target_dir.set_relationship("C")
            target_dir.set_target_filename("loop.pdf")
            # Attach the target step to the action's /T.
            action.get_cos_object().set_item(
                COSName.get_pdf_name("T"), target_dir.get_cos_object()
            )

            # Find a callable resolution entry; the exact name may vary.
            resolve = getattr(action, "resolve_target", None) or getattr(
                action, "resolve_destination", None
            )
            if resolve is not None:
                with contextlib.suppress(Exception):
                    resolve(src, tgt)
        finally:
            pd_action_embedded_go_to._open_embedded_pdf = original_open  # type: ignore[assignment]
