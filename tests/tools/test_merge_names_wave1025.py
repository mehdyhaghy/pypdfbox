from __future__ import annotations

import tests.tools.test_merge_names_wave950 as wave950


def test_wave1025_wave950_fake_document_catalog_branch(
    monkeypatch,
    tmp_path,
) -> None:
    wave950.test_wave950_named_destination_link_action_branch_is_exercised(
        monkeypatch,
        tmp_path,
    )
