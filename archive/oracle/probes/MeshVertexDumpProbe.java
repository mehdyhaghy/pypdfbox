package org.apache.pdfbox.pdmodel.graphics.shading;

import java.awt.geom.AffineTransform;
import java.awt.geom.Point2D;
import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe: dump the parsed mesh-shading geometry that Apache PDFBox
 * decodes from a Type 4 / 5 / 6 / 7 shading stream, BEFORE any user-space
 * transform (identity matrix + identity xform). This isolates the
 * bit-stream decoder — coordinate / colour dequantisation and the per-vertex
 * byte-alignment padding (PDF 32000-1 §8.7.4.5.5) — from the rasteriser, so a
 * parsing divergence that the render-grid oracle would smooth over (e.g. a
 * missing per-vertex byte alignment when BitsPerCoordinate is not a multiple
 * of 8) is caught exactly.
 *
 * Lives in package org.apache.pdfbox.pdmodel.graphics.shading so it can call
 * the package-private collectTriangles(...) on PDShadingType4/5 and read the
 * package-private ShadedTriangle.corner / .color fields.
 *
 * Usage: java -cp <jar>:<build> \
 *          org.apache.pdfbox.pdmodel.graphics.shading.MeshVertexDumpProbe \
 *          input.pdf shadingName
 *
 * Output (UTF-8, to stdout):
 *   Triangle meshes (Types 4/5):
 *     line 1: "TRIANGLES <count>"
 *     then one line per triangle: 6 coord floats then 3*n colour floats,
 *       space-separated, formatted "%.6f": x0 y0 x1 y1 x2 y2 c0... c1... c2...
 *   Patch meshes (Types 6/7):
 *     line 1: "PATCHES <count>"
 *     then per patch the triangulated geometry the renderer actually uses,
 *       same per-triangle line shape as above (Patch.listOfTriangles).
 */
public final class MeshVertexDumpProbe
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
            if (type == 4 || type == 5)
            {
                PDTriangleBasedShadingType tri = (PDTriangleBasedShadingType) shading;
                List<ShadedTriangle> list = tri.collectTriangles(xform, matrix);
                out.println("TRIANGLES " + list.size());
                for (ShadedTriangle t : list)
                {
                    emitTriangle(out, t.corner, t.color);
                }
            }
            else if (type == 6 || type == 7)
            {
                PDMeshBasedShadingType mesh = (PDMeshBasedShadingType) shading;
                int controlPoints = (type == 6) ? 12 : 16;
                List<Patch> patches = mesh.collectPatches(xform, matrix, controlPoints);
                int total = 0;
                for (Patch p : patches)
                {
                    total += p.listOfTriangles.size();
                }
                out.println("PATCHES " + total);
                for (Patch p : patches)
                {
                    for (ShadedTriangle t : p.listOfTriangles)
                    {
                        emitTriangle(out, t.corner, t.color);
                    }
                }
            }
            else
            {
                out.println("UNSUPPORTED " + type);
            }
        }
    }

    private static void emitTriangle(PrintStream out, Point2D[] corner, float[][] color)
    {
        StringBuilder sb = new StringBuilder();
        for (Point2D p : corner)
        {
            sb.append(String.format("%.6f %.6f ", p.getX(), p.getY()));
        }
        for (float[] c : color)
        {
            for (float v : c)
            {
                sb.append(String.format("%.6f ", v));
            }
        }
        out.println(sb.toString().trim());
    }
}
