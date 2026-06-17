import org.apache.pdfbox.util.Matrix;
import org.apache.pdfbox.util.Vector;
import java.awt.geom.AffineTransform;
import java.awt.geom.Point2D;

/**
 * Emits canonical Float.toString values exercising the 32-bit float storage of
 * org.apache.pdfbox.util.Matrix / Vector so pypdfbox (float64) parity can be
 * verified at the exact narrowed values.
 *
 * Each line: "label=<value>". Values are Java floats (Float.toString) unless
 * noted; transformed points use the Point2D.Float components (also floats).
 */
public final class MatrixFloat32Probe
{
    private static void m(String label, Matrix mtx)
    {
        float[][] v = mtx.getValues();
        // emit the six geometric cells in toCOSArray order: 0 1 3 4 6 7
        System.out.println(label + ".sx=" + v[0][0]);
        System.out.println(label + ".hy=" + v[0][1]);
        System.out.println(label + ".hx=" + v[1][0]);
        System.out.println(label + ".sy=" + v[1][1]);
        System.out.println(label + ".tx=" + v[2][0]);
        System.out.println(label + ".ty=" + v[2][1]);
    }

    public static void main(String[] args)
    {
        // --- getRotateInstance at non-trivial angles (cos/sin narrowed to float) ---
        m("rot_0p1", Matrix.getRotateInstance(0.1, 0f, 0f));
        m("rot_30deg", Matrix.getRotateInstance(Math.toRadians(30), 5f, 7f));
        m("rot_1rad", Matrix.getRotateInstance(1.0, 0f, 0f));
        m("rot_2p5", Matrix.getRotateInstance(2.5, -3f, 4f));

        // --- chain of 10 rotate-translate concatenations (float32 accumulation) ---
        Matrix chain = new Matrix();
        for (int i = 0; i < 10; i++)
        {
            chain.concatenate(Matrix.getRotateInstance(0.1, 1f, 2f));
        }
        m("chain10", chain);

        // --- multiply order (this-times-other) ---
        Matrix a = Matrix.getRotateInstance(0.3, 0f, 0f);
        Matrix b = Matrix.getScaleInstance(2.5f, 1.3f);
        m("a_mul_b", a.multiply(b));
        m("b_mul_a", b.multiply(a));
        // static concatenate(a,b) == b.multiply(a)
        m("concat_ab", Matrix.concatenate(a, b));

        // --- getScalingFactorX/Y on a sheared matrix (PDFBOX-4148 sqrt) ---
        Matrix shear = new Matrix(2f, 4f, 4f, 2f, 0f, 0f);
        System.out.println("shear.sfx=" + shear.getScalingFactorX());
        System.out.println("shear.sfy=" + shear.getScalingFactorY());
        Matrix shear2 = new Matrix(0.7f, 0.13f, 0.31f, 0.9f, 0f, 0f);
        System.out.println("shear2.sfx=" + shear2.getScalingFactorX());
        System.out.println("shear2.sfy=" + shear2.getScalingFactorY());
        // zero-shear path returns raw element
        Matrix nos = new Matrix(0.1f, 0f, 0f, 0.7f, 0f, 0f);
        System.out.println("nos.sfx=" + nos.getScalingFactorX());
        System.out.println("nos.sfy=" + nos.getScalingFactorY());

        // --- raw accessors after rotate (float storage) ---
        Matrix r = Matrix.getRotateInstance(0.1, 0f, 0f);
        System.out.println("r.scaleX=" + r.getScaleX());
        System.out.println("r.shearY=" + r.getShearY());
        System.out.println("r.shearX=" + r.getShearX());
        System.out.println("r.scaleY=" + r.getScaleY());

        // --- transformPoint (Point2D.Float -> float components) ---
        Matrix tp = Matrix.getRotateInstance(0.1, 3f, 4f);
        Point2D.Float p = tp.transformPoint(1.234f, 5.678f);
        System.out.println("tp.x=" + p.x);
        System.out.println("tp.y=" + p.y);

        // --- transform(Vector) ---
        Vector tv = tp.transform(new Vector(1.234f, 5.678f));
        System.out.println("tv.x=" + tv.getX());
        System.out.println("tv.y=" + tv.getY());

        // --- createAffineTransform round-trip (double getters off float store) ---
        AffineTransform at = Matrix.getRotateInstance(0.1, 0f, 0f).createAffineTransform();
        System.out.println("at.m00=" + at.getScaleX());
        System.out.println("at.m10=" + at.getShearY());
        System.out.println("at.m01=" + at.getShearX());
        System.out.println("at.m11=" + at.getScaleY());

        // --- Matrix(AffineTransform) constructor narrows doubles to float ---
        AffineTransform src = new AffineTransform(0.1, 0.2, 0.3, 0.4, 0.5, 0.6);
        m("from_at", new Matrix(src));

        // --- Vector float32 narrowing + scale ---
        Vector v = new Vector(0.1f, 0.2f);
        System.out.println("vec.x=" + v.getX());
        System.out.println("vec.y=" + v.getY());
        Vector vs = v.scale(0.3f);
        System.out.println("vec_scaled.x=" + vs.getX());
        System.out.println("vec_scaled.y=" + vs.getY());
        // narrowing from a double literal
        Vector vd = new Vector((float) 0.1, (float) (1.0 / 3.0));
        System.out.println("vecd.x=" + vd.getX());
        System.out.println("vecd.y=" + vd.getY());

        // --- toString format (float rendering) ---
        System.out.println("rot_tostr=" + Matrix.getRotateInstance(0.1, 0f, 0f).toString());

        // --- toCOSArray float values for a rotate matrix ---
        Matrix rc = Matrix.getRotateInstance(0.1, 1.5f, 2.5f);
        org.apache.pdfbox.cos.COSArray ca = rc.toCOSArray();
        for (int i = 0; i < 6; i++)
        {
            System.out.println("cos[" + i + "]=" + ((org.apache.pdfbox.cos.COSNumber) ca.get(i)).floatValue());
        }
    }
}
