import java.awt.geom.GeneralPath;
import java.awt.geom.Point2D;
import java.awt.geom.PathIterator;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.util.Matrix;

/**
 * Differential fuzz of the PDRectangle <-> Matrix INTERACTION (wave 1561).
 *
 * Existing probes split this surface: RectangleFuzzProbe covers
 * PDRectangle(COSArray) malformed construction + accessors; MatrixOpsFuzzProbe
 * and MatrixFloat32Probe cover Matrix algebra in isolation. This probe pins the
 * crossing edges neither covers:
 *
 *  - PDRectangle.transform(Matrix): the four corners projected through a
 *    rotation / scale / shear / translate / singular matrix, read back from the
 *    returned java.awt.geom.GeneralPath via its PathIterator.
 *  - getScalingFactorX/Y on a rotated-then-scaled matrix and a sheared matrix.
 *  - contains(x,y) exactly on each of the four edges and the corners.
 *  - rotate by 90 / 45 then transform a rectangle's corners.
 *  - Matrix multiply order applied to a rectangle (scale-then-rotate vs
 *    rotate-then-scale produce different corner projections).
 *
 * Every emitted scalar is a Java float (PDFBox Matrix is float[]); the Python
 * test compares with float32 awareness via Float.toString-equivalent rendering.
 *
 * Output lines: "label=value" (floats as Float.toString) and "label=true|false"
 * for contains.
 */
public final class RectMatrixFuzzProbe
{
    private static COSArray box(double llx, double lly, double urx, double ury)
    {
        COSArray a = new COSArray();
        a.add(new COSFloat((float) llx));
        a.add(new COSFloat((float) lly));
        a.add(new COSFloat((float) urx));
        a.add(new COSFloat((float) ury));
        return a;
    }

    /** Emit the corner sequence of a transform(Matrix) GeneralPath. */
    private static void path(String label, PDRectangle rect, Matrix m)
    {
        GeneralPath gp = rect.transform(m);
        PathIterator it = gp.getPathIterator(null);
        float[] coords = new float[6];
        int i = 0;
        while (!it.isDone())
        {
            int type = it.currentSegment(coords);
            if (type == PathIterator.SEG_MOVETO || type == PathIterator.SEG_LINETO)
            {
                System.out.println(label + ".p" + i + ".x=" + coords[0]);
                System.out.println(label + ".p" + i + ".y=" + coords[1]);
                i++;
            }
            it.next();
        }
        System.out.println(label + ".n=" + i);
    }

    private static void dims(String label, PDRectangle rect)
    {
        System.out.println(label + ".llx=" + rect.getLowerLeftX());
        System.out.println(label + ".lly=" + rect.getLowerLeftY());
        System.out.println(label + ".urx=" + rect.getUpperRightX());
        System.out.println(label + ".ury=" + rect.getUpperRightY());
        System.out.println(label + ".w=" + rect.getWidth());
        System.out.println(label + ".h=" + rect.getHeight());
    }

    public static void main(String[] args)
    {
        // ---- normalization of an inverted MediaBox --------------------------
        PDRectangle inv = new PDRectangle(box(400, 300, 50, 100));
        dims("inv", inv);
        PDRectangle invY = new PDRectangle(box(50, 300, 400, 100));
        dims("invY", invY);
        PDRectangle neg = new PDRectangle(box(-100, -200, -50, -60));
        dims("neg", neg);
        PDRectangle zero = new PDRectangle(box(5, 5, 5, 5));
        dims("zeroarea", zero);

        // ---- contains on edges / corners of a normalized box ---------------
        PDRectangle r = new PDRectangle(box(10, 20, 110, 220));
        System.out.println("c.ll=" + r.contains(10f, 20f));
        System.out.println("c.ur=" + r.contains(110f, 220f));
        System.out.println("c.lr=" + r.contains(110f, 20f));
        System.out.println("c.ul=" + r.contains(10f, 220f));
        System.out.println("c.left=" + r.contains(10f, 120f));
        System.out.println("c.right=" + r.contains(110f, 120f));
        System.out.println("c.bottom=" + r.contains(60f, 20f));
        System.out.println("c.top=" + r.contains(60f, 220f));
        System.out.println("c.in=" + r.contains(60f, 120f));
        System.out.println("c.outL=" + r.contains(9.999f, 120f));
        System.out.println("c.outR=" + r.contains(110.001f, 120f));
        System.out.println("c.outB=" + r.contains(60f, 19.999f));
        System.out.println("c.outT=" + r.contains(60f, 220.001f));

        // ---- createRetranslatedRectangle of an inverted box ----------------
        PDRectangle re = inv.createRetranslatedRectangle();
        dims("re", re);

        // ---- transform corners by various matrices -------------------------
        PDRectangle unit = new PDRectangle(box(0, 0, 100, 200));

        path("t_id", unit, new Matrix());
        path("t_scale", unit, Matrix.getScaleInstance(2f, 3f));
        path("t_translate", unit, Matrix.getTranslateInstance(50f, -25f));
        path("t_rot90", unit, Matrix.getRotateInstance(Math.PI / 2, 0f, 0f));
        path("t_rot45", unit, Matrix.getRotateInstance(Math.PI / 4, 0f, 0f));
        path("t_rot180", unit, Matrix.getRotateInstance(Math.PI, 0f, 0f));
        // shear matrix (hx=0.5, hy=0.25)
        path("t_shear", unit, new Matrix(1f, 0.25f, 0.5f, 1f, 0f, 0f));
        // singular matrix (rank-1: collapses all points onto a line)
        path("t_singular", unit, new Matrix(1f, 2f, 2f, 4f, 0f, 0f));

        // multiply order: scale-then-rotate vs rotate-then-scale
        Matrix scale = Matrix.getScaleInstance(2f, 3f);
        Matrix rot = Matrix.getRotateInstance(Math.PI / 4, 0f, 0f);
        path("t_scale_rot", unit, scale.multiply(rot));
        path("t_rot_scale", unit, rot.multiply(scale));

        // transform an inverted (now normalized) box
        path("t_inv_rot90", inv, Matrix.getRotateInstance(Math.PI / 2, 0f, 0f));

        // ---- getScalingFactor on rotated+scaled / sheared matrices ---------
        Matrix rs = Matrix.getScaleInstance(2f, 3f);
        rs.rotate(Math.PI / 4);
        System.out.println("rs.sfx=" + rs.getScalingFactorX());
        System.out.println("rs.sfy=" + rs.getScalingFactorY());
        Matrix sheared = new Matrix(1f, 0.25f, 0.5f, 1f, 0f, 0f);
        System.out.println("sheared.sfx=" + sheared.getScalingFactorX());
        System.out.println("sheared.sfy=" + sheared.getScalingFactorY());
        Matrix singular = new Matrix(1f, 2f, 2f, 4f, 0f, 0f);
        System.out.println("singular.sfx=" + singular.getScalingFactorX());
        System.out.println("singular.sfy=" + singular.getScalingFactorY());
        // rotate90 then scaling factors
        Matrix rot90 = Matrix.getRotateInstance(Math.PI / 2, 0f, 0f);
        System.out.println("rot90.sfx=" + rot90.getScalingFactorX());
        System.out.println("rot90.sfy=" + rot90.getScalingFactorY());

        // ---- transformPoint on a rotated+scaled matrix ---------------------
        Point2D.Float p = rs.transformPoint(10f, 20f);
        System.out.println("rs.tp.x=" + p.x);
        System.out.println("rs.tp.y=" + p.y);

        // ---- float32 rounding of a chained product -------------------------
        Matrix chain = new Matrix(1.1f, 2.2f, 3.3f, 4.4f, 5.5f, 6.6f);
        Matrix chain2 = new Matrix(0.7f, 0.3f, 0.9f, 0.1f, 0.2f, 0.8f);
        Matrix prod = chain.multiply(chain2);
        float[][] v = prod.getValues();
        System.out.println("prod.sx=" + v[0][0]);
        System.out.println("prod.hy=" + v[0][1]);
        System.out.println("prod.hx=" + v[1][0]);
        System.out.println("prod.sy=" + v[1][1]);
        System.out.println("prod.tx=" + v[2][0]);
        System.out.println("prod.ty=" + v[2][1]);

        // getCOSArray size after transform-derived rectangle
        System.out.println("re.ca=" + re.getCOSArray().size());
    }
}
