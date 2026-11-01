from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .axial_shading_context import AxialShadingContext
    from .axial_shading_paint import AxialShadingPaint
    from .coons_patch import CoonsPatch
    from .cubic_bezier_curve import CubicBezierCurve
    from .gouraud_shading_context import GouraudShadingContext
    from .line import Line
    from .patch import Patch
    from .patch_meshes_shading_context import PatchMeshesShadingContext
    from .pd_mesh_based_shading_type import PDMeshBasedShadingType
    from .pd_shading import PDShading
    from .pd_shading_type1 import PDShadingType1
    from .pd_shading_type2 import PDShadingType2
    from .pd_shading_type3 import PDShadingType3
    from .pd_shading_type4 import PDShadingType4
    from .pd_shading_type5 import PDShadingType5
    from .pd_shading_type6 import PDShadingType6
    from .pd_shading_type7 import PDShadingType7
    from .pd_triangle_based_shading_type import PDTriangleBasedShadingType
    from .radial_shading_context import RadialShadingContext
    from .radial_shading_paint import RadialShadingPaint
    from .shaded_triangle import ShadedTriangle
    from .shading_context import ShadingContext
    from .shading_paint import ShadingPaint
    from .tensor_patch import TensorPatch
    from .triangle_based_shading_context import TriangleBasedShadingContext
    from .type1_shading_context import Type1ShadingContext
    from .type1_shading_paint import Type1ShadingPaint
    from .type4_shading_paint import Type4ShadingPaint
    from .type5_shading_paint import Type5ShadingPaint
    from .type6_shading_paint import Type6ShadingPaint
    from .type7_shading_paint import Type7ShadingPaint
    from .vertex import Vertex

__getattr__, __dir__ = _attach(
    __name__,
    {
        "AxialShadingContext": ".axial_shading_context",
        "AxialShadingPaint": ".axial_shading_paint",
        "CoonsPatch": ".coons_patch",
        "CubicBezierCurve": ".cubic_bezier_curve",
        "GouraudShadingContext": ".gouraud_shading_context",
        "Line": ".line",
        "Patch": ".patch",
        "PatchMeshesShadingContext": ".patch_meshes_shading_context",
        "PDMeshBasedShadingType": ".pd_mesh_based_shading_type",
        "PDShading": ".pd_shading",
        "PDShadingType1": ".pd_shading_type1",
        "PDShadingType2": ".pd_shading_type2",
        "PDShadingType3": ".pd_shading_type3",
        "PDShadingType4": ".pd_shading_type4",
        "PDShadingType5": ".pd_shading_type5",
        "PDShadingType6": ".pd_shading_type6",
        "PDShadingType7": ".pd_shading_type7",
        "PDTriangleBasedShadingType": ".pd_triangle_based_shading_type",
        "RadialShadingContext": ".radial_shading_context",
        "RadialShadingPaint": ".radial_shading_paint",
        "ShadedTriangle": ".shaded_triangle",
        "ShadingContext": ".shading_context",
        "ShadingPaint": ".shading_paint",
        "TensorPatch": ".tensor_patch",
        "TriangleBasedShadingContext": ".triangle_based_shading_context",
        "Type1ShadingContext": ".type1_shading_context",
        "Type1ShadingPaint": ".type1_shading_paint",
        "Type4ShadingPaint": ".type4_shading_paint",
        "Type5ShadingPaint": ".type5_shading_paint",
        "Type6ShadingPaint": ".type6_shading_paint",
        "Type7ShadingPaint": ".type7_shading_paint",
        "Vertex": ".vertex",
    },
)

__all__ = [
    "AxialShadingContext",
    "AxialShadingPaint",
    "CoonsPatch",
    "CubicBezierCurve",
    "GouraudShadingContext",
    "Line",
    "PDMeshBasedShadingType",
    "PDShading",
    "PDShadingType1",
    "PDShadingType2",
    "PDShadingType3",
    "PDShadingType4",
    "PDShadingType5",
    "PDShadingType6",
    "PDShadingType7",
    "PDTriangleBasedShadingType",
    "Patch",
    "PatchMeshesShadingContext",
    "RadialShadingContext",
    "RadialShadingPaint",
    "ShadedTriangle",
    "ShadingContext",
    "ShadingPaint",
    "TensorPatch",
    "TriangleBasedShadingContext",
    "Type1ShadingContext",
    "Type1ShadingPaint",
    "Type4ShadingPaint",
    "Type5ShadingPaint",
    "Type6ShadingPaint",
    "Type7ShadingPaint",
    "Vertex",
]
