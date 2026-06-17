# pypdfbox.pdmodel.graphics — color, shading, blend, transparency, XObjects

Everything below `pypdfbox.pdmodel.graphics` deals with the PDF graphics
state machinery: color spaces, shadings (gradients and meshes), blend
modes, transparency groups, patterns, and X-objects (forms + images).
Class names match upstream PDFBox 1:1 and the inheritance hierarchy under
`PDColorSpace` is preserved.

## Public surface (top level)

| Class | Purpose |
| --- | --- |
| `BlendMode` | The 16 PDF blend modes (PDF 32000 §11.3.5). `BlendMode.NORMAL`, `MULTIPLY`, `SCREEN`, `OVERLAY`, `DARKEN`, `LIGHTEN`, `COLOR_DODGE`, `COLOR_BURN`, `HARD_LIGHT`, `SOFT_LIGHT`, `DIFFERENCE`, `EXCLUSION`, `HUE`, `SATURATION`, `COLOR`, `LUMINOSITY`. |
| `PDXObject` | Abstract X-object. Two subtypes exist in PDF: `PDFormXObject` (a reusable content-stream snippet) and `PDImageXObject` (an image). Both live under `pypdfbox.pdmodel.graphics.form` and `.image`. |

## Color spaces (`pypdfbox.pdmodel.graphics.color`)

| Class | Purpose |
| --- | --- |
| `PDColor` | A point in a color space. Carries the components tuple + the `PDColorSpace`. `to_rgb()` converts via the space's transform. |
| `PDColorSpace` | Abstract root. `get_number_of_components`, `get_default_decode(bits)`, `to_rgb(values)`, `to_rgb_image(raster, width, height)`, `get_initial_color`. |
| `PDDeviceColorSpace` | Common base for device spaces (`DeviceGray`, `DeviceRGB`, `DeviceCMYK`). |
| `PDDeviceGray` | Singleton. 1 component. |
| `PDDeviceRGB` | Singleton. 3 components. |
| `PDDeviceCMYK` | Singleton. 4 components. CMYK→RGB conversion via the ICC profile bundled in `pypdfbox/resources/icc/`. |
| `PDCIEBasedColorSpace` | Common base for CIE-based spaces (`CalGray`, `CalRGB`, `Lab`, `ICCBased`). |
| `PDCIEDictionaryBasedColorSpace` | Base for the CalGray / CalRGB / Lab spaces that share `/WhitePoint`, `/BlackPoint`. |
| `PDCalGray` | Calibrated grayscale. `set_gamma(value)`. |
| `PDCalRGB` | Calibrated RGB. `set_matrix(matrix)`. |
| `PDLab` | L*a*b* color space. |
| `PDICCBased` | ICC-profile color space. Parses the embedded profile through `pillow-heif`-free ICC handling (stdlib + bundled small parser). |
| `PDIndexed` | Palette-indexed color space (per PDF 1.3+). |
| `PDSeparation` | Single-channel spot color. Wraps a tint transform function. |
| `PDDeviceN` | N-channel spot color. Wraps a multivariate tint transform. |
| `PDPattern` | Pattern color space. Used with either a tiling or shading pattern. |
| `PDJPXColorSpace` | Color space pulled from a JPX (`JPEG2000`) image's codestream. |
| `PDOutputIntent` | `/OutputIntents` entry — ties a destination output condition to an ICC profile. |
| `PDGamma` | RGB gamma triple. |
| `PDTristimulus` | (X, Y, Z) tristimulus value used by Cal* color spaces. |

## Shadings (`pypdfbox.pdmodel.graphics.shading`)

Shading types 1-7 are fully decoded and rendered, including the
Coons/tensor patch `calcLevel` algorithm.

| Class | Shading type |
| --- | --- |
| `PDShading` | Abstract root. `PDShading.create(cos_dict_or_stream)` factory dispatches on `/ShadingType`. |
| `PDShadingType1` | Function-based (1) |
| `PDShadingType2` | Axial gradient (2) |
| `PDShadingType3` | Radial gradient (3) |
| `PDShadingType4` | Free-form Gouraud-shaded triangle mesh (4) |
| `PDShadingType5` | Lattice-form Gouraud-shaded triangle mesh (5) |
| `PDShadingType6` | Coons patch mesh (6) |
| `PDShadingType7` | Tensor-product patch mesh (7) |
| `PDTriangleBasedShadingType` | Common base for types 4/5. |
| `PDMeshBasedShadingType` | Common base for types 6/7. |
| `ShadingContext`, `Type1ShadingContext`, `AxialShadingContext`, `RadialShadingContext`, `GouraudShadingContext`, `TriangleBasedShadingContext`, `PatchMeshesShadingContext` | Per-type rendering contexts. |
| `ShadingPaint`, `Type1ShadingPaint`, `AxialShadingPaint`, `RadialShadingPaint`, `Type4ShadingPaint`, `Type5ShadingPaint`, `Type6ShadingPaint`, `Type7ShadingPaint` | Per-type Skia paints. |
| `Patch`, `CoonsPatch`, `TensorPatch` | Patch geometry. `Patch.calc_level(...)` returns the subdivision level. |
| `CubicBezierCurve`, `Line`, `Vertex`, `IntPoint`, `ShadedTriangle` | Mesh primitives. |

## Blend (`pypdfbox.pdmodel.graphics.blend`)

| Class | Purpose |
| --- | --- |
| `BlendFunction` | Pure-color blend operator for the 16 separable modes (Multiply, Screen, Overlay, ...). |
| `BlendChannelFunction` | Per-channel adapter used by the soft-mask pipeline. |
| `BlendComposite` | Skia `Composite` adapter — wraps `BlendFunction` for the rendering backend. |

## Transparency + groups

`pypdfbox.rendering.group_graphics.GroupGraphics` and
`pypdfbox.rendering.page_drawer.TransparencyGroup` together implement
isolated / knockout / non-isolated group composition per PDF 32000 §11.4.5.
The `/Group` dictionary on a form XObject is decoded into a
`PDTransparencyGroupAttributes` in `pypdfbox.pdmodel.graphics.form`.

## Patterns + state + image + optional content + form (sub-packages)

| Sub-package | Notable classes |
| --- | --- |
| `pypdfbox.pdmodel.graphics.pattern` | `PDAbstractPattern`, `PDTilingPattern`, `PDShadingPattern`. |
| `pypdfbox.pdmodel.graphics.state` | `PDExtendedGraphicsState`, `PDLineDashPattern`, `PDSoftMask`, `RenderingIntent`. |
| `pypdfbox.pdmodel.graphics.image` | `PDImageXObject`, `PDInlineImage`, `JPEGFactory`, `LosslessFactory`, `CCITTFactory`. |
| `pypdfbox.pdmodel.graphics.optionalcontent` | `PDOptionalContentProperties`, `PDOptionalContentGroup`. |
| `pypdfbox.pdmodel.graphics.form` | `PDFormXObject`, `PDTransparencyGroupAttributes`. |

## Typical usage

```python
from pypdfbox.pdmodel.graphics.color import PDDeviceRGB, PDColor
from pypdfbox.pdmodel.graphics.blend import BlendFunction

red = PDColor((1.0, 0.0, 0.0), PDDeviceRGB.INSTANCE)
print(red.to_rgb())  # (255, 0, 0)

# Multiply blend at the pixel level
fn = BlendFunction.for_mode("Multiply")
print(fn((0.8, 0.2, 0.5), (0.5, 0.5, 0.5)))
```

## PDFBox divergence

- `BlendMode.compatibleName(name)` → `BlendMode.compatible_name(name)`.
- `PDColorSpace.toRGB(float[])` → `to_rgb(values)` accepts any sequence.
- `PDShading.create(...)` returns the correct subclass; the Java factory
  raises `IOException` on unknown `/ShadingType`, pypdfbox raises
  `ValueError`.

## See also

- [contentstream.md](contentstream.md) — graphics state stack + color
  operators.
- [rendering.md](rendering.md) — how these spaces and shadings are painted.
- [guides/colors-and-shading.md](../guides/colors-and-shading.md).
