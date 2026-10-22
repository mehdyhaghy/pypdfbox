from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_thread import PDThread
    from .pd_thread_bead import PDThreadBead
    from .pd_transition import PDTransition
    from .pd_transition_dimension import PDTransitionDimension
    from .pd_transition_direction import PDTransitionDirection
    from .pd_transition_motion import PDTransitionMotion
    from .pd_transition_style import PDTransitionStyle

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDThread": ".pd_thread",
        "PDThreadBead": ".pd_thread_bead",
        "PDTransition": ".pd_transition",
        "PDTransitionDimension": ".pd_transition_dimension",
        "PDTransitionDirection": ".pd_transition_direction",
        "PDTransitionMotion": ".pd_transition_motion",
        "PDTransitionStyle": ".pd_transition_style",
    },
)

__all__ = [
    "PDThread",
    "PDThreadBead",
    "PDTransition",
    "PDTransitionDimension",
    "PDTransitionDirection",
    "PDTransitionMotion",
    "PDTransitionStyle",
]
