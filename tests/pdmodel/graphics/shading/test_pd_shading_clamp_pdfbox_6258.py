"""PDFBOX-6258 (3.0 branch, unreleased 3.0.9): ``PDShading.eval_function``
clamps through the shading's color space instead of always to 0..1."""

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.graphics.shading.pd_shading import PDShading


def _shading(color_space, c0, c1) -> PDShading:
    fn = COSDictionary()
    fn.set_item(COSName.get_pdf_name("FunctionType"), COSInteger.get(2))
    fn.set_item(COSName.get_pdf_name("Domain"), COSArray([COSFloat(0), COSFloat(1)]))
    fn.set_item(COSName.get_pdf_name("C0"), COSArray([COSFloat(v) for v in c0]))
    fn.set_item(COSName.get_pdf_name("C1"), COSArray([COSFloat(v) for v in c1]))
    fn.set_item(COSName.get_pdf_name("N"), COSInteger.get(1))
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("ShadingType"), COSInteger.get(2))
    if color_space is not None:
        d.set_item(COSName.get_pdf_name("ColorSpace"), color_space)
    d.set_item(COSName.get_pdf_name("Function"), fn)
    return PDShading.create(d)


def _lab() -> COSArray:
    params = COSDictionary()
    params.set_item(
        COSName.get_pdf_name("WhitePoint"),
        COSArray([COSFloat(0.9505), COSFloat(1.0), COSFloat(1.089)]),
    )
    params.set_item(
        COSName.get_pdf_name("Range"),
        COSArray([COSFloat(-50), COSFloat(50), COSFloat(-60), COSFloat(60)]),
    )
    return COSArray([COSName.get_pdf_name("Lab"), params])


def test_lab_shading_uses_lab_ranges():
    shading = _shading(_lab(), [80, -70, 70], [80, -70, 70])
    assert shading.eval_function(0.5) == [80.0, -50.0, 60.0]


def test_device_rgb_shading_clamps_to_unit_range():
    shading = _shading(COSName.get_pdf_name("DeviceRGB"), [-1, 0.5, 2], [-1, 0.5, 2])
    assert shading.eval_function(0.5) == [0.0, 0.5, 1.0]


def test_missing_color_space_falls_back_to_unit_range():
    shading = _shading(None, [-1, 0.5, 2], [-1, 0.5, 2])
    assert shading.eval_function(0.5) == [0.0, 0.5, 1.0]
