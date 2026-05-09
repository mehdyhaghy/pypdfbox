from __future__ import annotations

from collections.abc import Callable

import pytest

from tests.xmpbox.upstream import test_dom_xmp_parser as upstream_dom


@pytest.mark.parametrize(
    "placeholder",
    [
        upstream_dom.test_pdfbox5835,
        upstream_dom.test_pdfbox6106,
        upstream_dom.test_exif,
        upstream_dom.test_layer,
        upstream_dom.test_history,
    ],
)
def test_wave881_upstream_dom_parser_placeholder_bodies(placeholder: Callable[[], None]) -> None:
    assert placeholder() is None
