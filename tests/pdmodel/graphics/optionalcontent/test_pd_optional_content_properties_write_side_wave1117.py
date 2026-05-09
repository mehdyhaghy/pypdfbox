from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)
from tests.pdmodel.graphics.optionalcontent import (
    test_pd_optional_content_properties_write_side as write_side,
)


def test_wave1117_remove_group_cleanup_loop_checks_remaining_off_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_build = write_side._build

    def build_with_unrelated_hidden_layer(
        *names: str,
    ) -> tuple[PDOptionalContentProperties, list[PDOptionalContentGroup]]:
        props, groups = original_build(*names)
        props.set_hidden(groups[1])
        return props, groups

    monkeypatch.setattr(write_side, "_build", build_with_unrelated_hidden_layer)

    write_side.test_remove_group_by_object_clears_ocgs_and_d()
