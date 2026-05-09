from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.multipdf import Splitter
from tests.multipdf import test_splitter_signatures as signatures


def test_existing_sigflags_assertion_runs_when_acroform_survives(
    monkeypatch,
) -> None:
    def remove_sigflags_but_keep_acroform(
        self: Splitter,
        destination_document,
    ) -> None:
        del self
        catalog = destination_document.get_document_catalog().get_cos_object()
        acroform = catalog.get_dictionary_object(signatures._ACROFORM)
        assert isinstance(acroform, COSDictionary)
        assert acroform.contains_key(signatures._SIG_FLAGS)
        acroform.remove_item(signatures._SIG_FLAGS)

    monkeypatch.setattr(
        Splitter,
        "_scrub_acroform",
        remove_sigflags_but_keep_acroform,
    )

    signatures.test_acroform_sigflags_cleared_when_signature_dropped()
