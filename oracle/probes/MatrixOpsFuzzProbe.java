import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.util.Matrix;
import org.apache.pdfbox.util.Vector;
import java.awt.geom.Point2D;

/**
 * Differential fuzz of org.apache.pdfbox.util.Matrix OPERATIONS + createMatrix
 * coercion (the angle MatrixFloat32Probe does not cover: createMatrix from a
 * malformed COSArray, multiply/concatenate values, transformPoint at extreme
 * inputs, rotate/scale/translate edge angles, getScalingFactor on rotated/
 * sheared/zero matrices, getTranslateX/Y, getValues round-trip).
 *
 * Each line: "label=<value>". Matrix cells are emitted in toCOSArray order
 * (0 1 3 4 6 7) as Java Float.toString. createMatrix on a base that yields the
 * identity in upstream emits the identity cells; a non-COSArray/short/non-number
 * base is "NULL" if upstream returns null, else the identity cells under "<lbl>".
 */
public final class MatrixOpsFuzzProbe
{
    private static void m(String label, Matrix mtx)
    {
        if (mtx == null)
        {
            System.out.println(label + "=NULL");
            return;
        }
        float[][] v = mtx.getValues();
        System.out.println(label + ".sx=" + v[0][0]);
        System.out.println(label + ".hy=" + v[0][1]);
        System.out.println(label + ".hx=" + v[1][0]);
        System.out.println(label + ".sy=" + v[1][1]);
        System.out.println(label + ".tx=" + v[2][0]);
        System.out.println(label + ".ty=" + v[2][1]);
    }

    private static COSArray nums(double... vals)
    {
        COSArray a = new COSArray();
        for (double d : vals)
        {
            a.add(new COSFloat((float) d));
        }
        return a;
    }

    public static void main(String[] args)
    {
        // ---- createMatrix coercion -------------------------------------
        // null base
        m("cm_null", Matrix.createMatrix(null));
        // non-COSArray base
        m("cm_name", Matrix.createMatrix(COSName.getPDFName("Foo")));
        m("cm_string", Matrix.createMatrix(new COSString("abc")));
        m("cm_int", Matrix.createMatrix(COSInteger.get(5)));
        // empty array
        m("cm_len0", Matrix.createMatrix(new COSArray()));
        // length 3
        m("cm_len3", Matrix.createMatrix(nums(1, 2, 3)));
        // length 5
        m("cm_len5", Matrix.createMatrix(nums(1, 2, 3, 4, 5)));
        // length 6 valid
        m("cm_len6", Matrix.createMatrix(nums(2, 0, 0, 2, 10, 20)));
        // length 9 (extra trailing ignored?)
        m("cm_len9", Matrix.createMatrix(nums(1, 2, 3, 4, 5, 6, 7, 8, 9)));
        // length 6 with a non-number entry at index 2
        COSArray mixed = new COSArray();
        mixed.add(new COSFloat(1f));
        mixed.add(new COSFloat(0f));
        mixed.add(COSName.getPDFName("X"));
        mixed.add(new COSFloat(1f));
        mixed.add(new COSFloat(0f));
        mixed.add(new COSFloat(0f));
        m("cm_mixed", Matrix.createMatrix(mixed));
        // length 6 integers (COSInteger is a COSNumber)
        COSArray ints = new COSArray();
        for (int i = 0; i < 6; i++) ints.add(COSInteger.get(i + 1));
        m("cm_ints", Matrix.createMatrix(ints));
        // length 6 with null entry
        COSArray withNull = new COSArray();
        withNull.add(new COSFloat(1f));
        withNull.add(new COSFloat(0f));
        withNull.add(null);
        withNull.add(new COSFloat(1f));
        withNull.add(new COSFloat(0f));
        withNull.add(new COSFloat(0f));
        m("cm_nullentry", Matrix.createMatrix(withNull));

        // ---- multiply: associativity & values --------------------------
        Matrix a = new Matrix(2f, 1f, 3f, 4f, 5f, 6f);
        Matrix b = new Matrix(0.5f, 0f, 0f, 2f, 1f, 1f);
        Matrix c = new Matrix(1f, 1f, 0f, 1f, 0f, 0f);
        m("ab", a.multiply(b));
        m("a_bc", a.multiply(b.multiply(c)));
        m("ab_c", a.multiply(b).multiply(c));
        // multiply with self
        m("aa", a.multiply(a));
        // multiply by identity
        m("a_id", a.multiply(new Matrix()));
        m("id_a", new Matrix().multiply(a));

        // ---- concatenate (in place; this = other * this) ----------------
        Matrix con = new Matrix(2f, 1f, 3f, 4f, 5f, 6f);
        con.concatenate(b);
        m("concat", con);

        // ---- rotate edge angles ----------------------------------------
        m("rot_0", Matrix.getRotateInstance(0.0, 0f, 0f));
        m("rot_pi", Matrix.getRotateInstance(Math.PI, 0f, 0f));
        m("rot_2pi", Matrix.getRotateInstance(2 * Math.PI, 0f, 0f));
        m("rot_halfpi", Matrix.getRotateInstance(Math.PI / 2, 0f, 0f));
        m("rot_neg", Matrix.getRotateInstance(-1.0, 0f, 0f));

        // rotate in place (concatenate get_rotate)
        Matrix rin = new Matrix(2f, 0f, 0f, 2f, 0f, 0f);
        rin.rotate(Math.PI / 2);
        m("rotate_inplace", rin);

        // ---- scale edge values -----------------------------------------
        Matrix sc = new Matrix(2f, 1f, 3f, 4f, 5f, 6f);
        sc.scale(0f, 0f);
        m("scale_zero", sc);
        Matrix sc2 = new Matrix(2f, 1f, 3f, 4f, 5f, 6f);
        sc2.scale(-1f, -2f);
        m("scale_neg", sc2);
        m("scale_inst_zero", Matrix.getScaleInstance(0f, 0f));
        m("scale_inst_neg", Matrix.getScaleInstance(-1.5f, -2.5f));

        // ---- translate -------------------------------------------------
        Matrix tr = new Matrix(2f, 1f, 3f, 4f, 5f, 6f);
        tr.translate(10f, 20f);
        m("translate", tr);
        Matrix trv = new Matrix(2f, 1f, 3f, 4f, 5f, 6f);
        trv.translate(new Vector(10f, 20f));
        m("translate_vec", trv);
        m("translate_inst", Matrix.getTranslateInstance(-3.5f, 4.25f));

        // ---- getScalingFactor on rotated / sheared / zero --------------
        Matrix rot45 = Matrix.getRotateInstance(Math.PI / 4, 0f, 0f);
        System.out.println("rot45.sfx=" + rot45.getScalingFactorX());
        System.out.println("rot45.sfy=" + rot45.getScalingFactorY());
        Matrix zero = new Matrix(0f, 0f, 0f, 0f, 0f, 0f);
        System.out.println("zero.sfx=" + zero.getScalingFactorX());
        System.out.println("zero.sfy=" + zero.getScalingFactorY());

        // ---- getTranslateX/Y, getScaleX/Y ------------------------------
        Matrix g = new Matrix(2f, 1f, 3f, 4f, 5f, 6f);
        System.out.println("g.tx=" + g.getTranslateX());
        System.out.println("g.ty=" + g.getTranslateY());
        System.out.println("g.scx=" + g.getScaleX());
        System.out.println("g.scy=" + g.getScaleY());
        System.out.println("g.shx=" + g.getShearX());
        System.out.println("g.shy=" + g.getShearY());

        // ---- transformPoint extreme/zero values ------------------------
        Matrix tm = new Matrix(2f, 1f, 3f, 4f, 5f, 6f);
        Point2D.Float p0 = tm.transformPoint(0f, 0f);
        System.out.println("tp0.x=" + p0.x);
        System.out.println("tp0.y=" + p0.y);
        Point2D.Float pbig = tm.transformPoint(1e30f, -1e30f);
        System.out.println("tpbig.x=" + pbig.x);
        System.out.println("tpbig.y=" + pbig.y);
        Point2D.Float pneg = tm.transformPoint(-12345.678f, 9876.543f);
        System.out.println("tpneg.x=" + pneg.x);
        System.out.println("tpneg.y=" + pneg.y);

        // ---- clone independence ----------------------------------------
        Matrix orig = new Matrix(2f, 1f, 3f, 4f, 5f, 6f);
        Matrix cl = orig.clone();
        cl.translate(100f, 100f);
        m("clone_orig", orig);
        m("clone_mod", cl);

        // ---- createMatrix -> toCOSArray round trip ---------------------
        Matrix rt = Matrix.createMatrix(nums(1.5, 2.5, 3.5, 4.5, 5.5, 6.5));
        COSArray ca = rt.toCOSArray();
        for (int i = 0; i < 6; i++)
        {
            System.out.println("rt[" + i + "]=" + ((org.apache.pdfbox.cos.COSNumber) ca.get(i)).floatValue());
        }
    }
}
