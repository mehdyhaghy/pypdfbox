"""Wave 1276 — :meth:`FontBoxFont.get_font_b_box` is declared on the
Protocol class.

Wave 1275 added a module-level :func:`get_font_b_box` helper that
dispatches to either spelling; wave 1276 promotes the strict spelling
to a Protocol method declaration so parity tooling counts it as an
interface member of upstream ``FontBoxFont`` (java L48
``getFontBBox`` → strict snake_case ``get_font_b_box``).

The method is intentionally *excluded* from the runtime-checkable
structural check (via ``__protocol_attrs__.discard``) so duck-typed
implementers that only expose the contracted ``get_font_bbox`` still
satisfy ``isinstance(obj, FontBoxFont)``.
"""

from __future__ import annotations

from pypdfbox.fontbox.font_box_font import FontBoxFont, get_font_b_box


class _OnlyContracted:
    """Implements only the contracted ``get_font_bbox`` spelling."""

    def get_name(self) -> str:
        return "OnlyContracted"

    def get_font_bbox(self) -> tuple[float, float, float, float]:
        return (-1.0, -2.0, 3.0, 4.0)

    def get_font_matrix(self) -> list[float]:
        return [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]

    def get_path(self, name: str) -> list[tuple[str, ...]]:
        return []

    def get_width(self, name: str) -> float:
        return 0.0

    def has_glyph(self, name: str) -> bool:
        return False


class _Strict(_OnlyContracted):
    def get_font_b_box(self) -> tuple[float, float, float, float]:
        return (10.0, 20.0, 30.0, 40.0)


def test_method_is_declared_on_protocol_class() -> None:
    # Parity tooling looks up methods on the class object; the strict
    # spelling must be present as an attribute.
    assert hasattr(FontBoxFont, "get_font_b_box")


def test_duck_typed_implementer_without_strict_still_isinstance() -> None:
    # Wave 1275's runtime-checkable contract must be preserved.
    assert isinstance(_OnlyContracted(), FontBoxFont)


def test_strict_implementer_is_also_isinstance() -> None:
    assert isinstance(_Strict(), FontBoxFont)


def test_module_helper_prefers_strict_spelling() -> None:
    # Wave 1275 behaviour: the helper picks strict if present, else
    # falls back to the contracted spelling.
    assert get_font_b_box(_Strict()) == (10.0, 20.0, 30.0, 40.0)
    assert get_font_b_box(_OnlyContracted()) == (-1.0, -2.0, 3.0, 4.0)


def test_strict_excluded_from_protocol_attrs() -> None:
    # Implementation detail covered explicitly so a future Python
    # version that renames ``__protocol_attrs__`` flips this test
    # rather than silently breaking the duck-typing contract.
    attrs = getattr(FontBoxFont, "__protocol_attrs__", None)
    if attrs is not None:
        assert "get_font_b_box" not in attrs
