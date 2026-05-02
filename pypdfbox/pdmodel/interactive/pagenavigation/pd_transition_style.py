from __future__ import annotations


class PDTransitionStyle:
    """Transition style names. Mirrors PDFBox ``PDTransitionStyle`` enum.

    See PDF 32000-1:2008 table 162.
    """

    SPLIT = "Split"
    BLINDS = "Blinds"
    BOX = "Box"
    WIPE = "Wipe"
    DISSOLVE = "Dissolve"
    GLITTER = "Glitter"
    R = "R"
    FLY = "Fly"
    PUSH = "Push"
    COVER = "Cover"
    UNCOVER = "Uncover"
    FADE = "Fade"

    # ---------- enum-shape helpers ----------
    #
    # Upstream PDFBox ``PDTransitionStyle`` is a Java enum, so callers reach
    # for ``values()`` / ``valueOf(name)``. We are a plain class with string
    # constants but expose the same shape so PDFBox developers can port code
    # mechanically.

    @classmethod
    def values(cls) -> tuple[str, ...]:
        """Return every valid transition style name in declaration order.

        Mirrors Java ``PDTransitionStyle.values()``.
        """
        return (
            cls.SPLIT,
            cls.BLINDS,
            cls.BOX,
            cls.WIPE,
            cls.DISSOLVE,
            cls.GLITTER,
            cls.R,
            cls.FLY,
            cls.PUSH,
            cls.COVER,
            cls.UNCOVER,
            cls.FADE,
        )

    @classmethod
    def value_of(cls, name: str) -> str:
        """Return ``name`` if it is a valid transition style, else raise.

        Mirrors Java ``PDTransitionStyle.valueOf(String)`` — case-sensitive,
        raises :class:`ValueError` (Python's ``IllegalArgumentException``
        analogue) for unknown names.
        """
        if name in cls.values():
            return name
        raise ValueError(f"No transition style for name {name!r}")

    @classmethod
    def is_valid(cls, name: str | None) -> bool:
        """Return ``True`` when ``name`` is one of the spec-defined transition
        styles. ``None`` and unknown strings return ``False``."""
        if name is None:
            return False
        return name in cls.values()

    # ---------- attribute-applicability predicates ----------
    #
    # The PDF spec restricts which transition styles honour each of /M, /Dm,
    # /Di and /SS. These predicates encode the same applicability matrix that
    # the upstream PDFBox ``PDTransition`` setters' Javadoc spells out, so
    # callers can guard their writes ("only set /Dm when the style supports
    # it") without re-deriving the rules from the spec.

    @classmethod
    def supports_motion(cls, name: str | None) -> bool:
        """``True`` when the style honours ``/M`` (``Split``, ``Blinds``,
        ``Fly``)."""
        return name in (cls.SPLIT, cls.BLINDS, cls.FLY)

    @classmethod
    def supports_dimension(cls, name: str | None) -> bool:
        """``True`` when the style honours ``/Dm`` (``Split``, ``Blinds``)."""
        return name in (cls.SPLIT, cls.BLINDS)

    @classmethod
    def supports_direction(cls, name: str | None) -> bool:
        """``True`` when the style honours ``/Di`` (``Wipe``, ``Glitter``,
        ``Fly``, ``Cover``, ``Uncover``, ``Push``)."""
        return name in (
            cls.WIPE,
            cls.GLITTER,
            cls.FLY,
            cls.COVER,
            cls.UNCOVER,
            cls.PUSH,
        )

    @classmethod
    def supports_fly_scale(cls, name: str | None) -> bool:
        """``True`` when the style honours ``/SS`` and ``/B`` (``Fly``
        only)."""
        return name == cls.FLY


__all__ = ["PDTransitionStyle"]
