package org.apache.pdfbox.pdmodel.graphics.shading;

import java.awt.geom.AffineTransform;
import java.awt.geom.Point2D;
import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe: dump the *parsed* patch geometry that Apache PDFBox
 * decodes from a Type 6 (Coons) / Type 7 (tensor) patch-mesh shading stream,
 * BEFORE any triangulation. This isolates the patch-stream parser — edge-flag
 * continuation chains (flags 1/2/3 reuse 4 boundary control points + 2 corner
 * colours from the previous patch), control-point dequantisation, the
 * per-corner colour assignment order, and the raw-1D -> reshaped 4x4 control
 * grid mapping (CoonsPatch / TensorPatch reshapeControlPoints) — from the
 * Bezier / tensor surface evaluator the render-grid oracle exercises.
 *
 * Crucially, Types 6/7 do NOT byte-align per patch (unlike Types 4/5 which
 * byte-align per vertex, PDF 32000-1 §8.7.4.5.5); a probe that dumps the
 * reshaped control grid for a non-byte-multiple bit layout catches a stray
 * per-patch alignment that the render oracle would smooth over.
 *
 * Lives in package org.apache.pdfbox.pdmodel.graphics.shading so it can call
 * the package-private collectPatches(...) on PDMeshBasedShadingType and read
 * the package-private Patch.controlPoints (reshaped 4x4 grid) and
 * Patch.cornerColor (4 corner colours) fields.
 *
 * Usage: java -cp <jar>:<build> \
 *          org.apache.pdfbox.pdmodel.graphics.shading.PatchMeshDecodeProbe \
 *          input.pdf shadingName
 *
 * Output (UTF-8, to stdout):
 *   line 1: "PATCHES <count>"
 *   then per patch two lines:
 *     line a: 32 coord floats — the reshaped 4x4 control grid row-major
 *             (controlPoints[i][j].x controlPoints[i][j].y), "%.6f"
 *     line b: 4*n colour floats — cornerColor[0..3] flattened, "%.6f"
 */
public final class PatchMeshDecodeProbe
{
    public static void main(String[] args) throws Exception
    {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0])))
        {
            String shName = args[1];
            PDPage page = doc.getPage(0);
            PDResources res = page.getResources();
            PDShading shading = res.getShading(COSName.getPDFName(shName));

            AffineTransform xform = new AffineTransform();
            Matrix matrix = new Matrix();

            int type = shading.getShadingType();
            if (type != 6 && type != 7)
            {
                out.println("UNSUPPORTED " + type);
                return;
            }
            PDMeshBasedShadingType mesh = (PDMeshBasedShadingType) shading;
            int controlPoints = (type == 6) ? 12 : 16;
            List<Patch> patches = mesh.collectPatches(xform, matrix, controlPoints);
            out.println("PATCHES " + patches.size());
            for (Patch p : patches)
            {
                StringBuilder grid = new StringBuilder();
                for (int i = 0; i < 4; i++)
                {
                    for (int j = 0; j < 4; j++)
                    {
                        Point2D pt = p.controlPoints[i][j];
                        grid.append(String.format("%.6f %.6f ", pt.getX(), pt.getY()));
                    }
                }
                out.println(grid.toString().trim());

                StringBuilder col = new StringBuilder();
                for (float[] c : p.cornerColor)
                {
                    for (float v : c)
                    {
                        col.append(String.format("%.6f ", v));
                    }
                }
                out.println(col.toString().trim());
            }
        }
    }
}
