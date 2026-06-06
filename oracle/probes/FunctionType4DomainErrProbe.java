import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Live oracle probe: Apache PDFBox PDFunctionType4 numeric-domain edge cases
 * (wave 1500, agent C — parity audit round 7).
 *
 * Pins the cases where upstream's arithmetic operators do NOT raise but instead
 * emit an IEEE-754 special value that the trailing /Range clip absorbs:
 *  - div by zero  => +/-Infinity (or NaN for 0/0) => clamped to range bound.
 *  - ln/log of 0  => -Infinity => range min;  of negative => NaN (passes clip).
 *  - exp negative base, fractional exponent => Math.pow NaN.
 * Plus the cases that legitimately throw (idiv/mod by zero, sqrt of negative)
 * and the int/float type-discipline cases (strict integer operators reject a
 * Float operand with a ClassCastException; lenient stack operators accept it).
 *
 * Line grammar:  FUNC <name> <in0,...> -> <out...>  | "-> ERR" | "-> ERR:<Cls>".
 */
public final class FunctionType4DomainErrProbe {

    static PrintStream out;

    static String fmt(float v) {
        if (Float.isNaN(v)) {
            return "NaN";
        }
        if (Float.isInfinite(v)) {
            return v > 0 ? "Infinity" : "-Infinity";
        }
        return String.format(java.util.Locale.ROOT, "%.6f", v);
    }

    static COSArray floats(float... vals) {
        COSArray a = new COSArray();
        for (float v : vals) {
            a.add(new COSFloat(v));
        }
        return a;
    }

    static COSStream t4(String ps, float[] domain, float[] range) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 4);
        s.setItem(COSName.DOMAIN, floats(domain));
        s.setItem(COSName.RANGE, floats(range));
        java.io.OutputStream os = s.createOutputStream();
        os.write(ps.getBytes("US-ASCII"));
        os.close();
        return s;
    }

    static void emit(String name, String ps, float[] dom, float[] rng, float[] in) throws Exception {
        StringBuilder sb = new StringBuilder("FUNC ").append(name).append(' ');
        for (int i = 0; i < in.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(Double.toString((double) in[i]));
        }
        sb.append(" ->");
        try {
            float[] o = PDFunction.create(t4(ps, dom, rng)).eval(in);
            for (float v : o) {
                sb.append(' ').append(fmt(v));
            }
        } catch (Throwable e) {
            // ERR alone == "pypdfbox must also raise"; the differential test only
            // asserts that both sides raise, not the exact exception class.
            sb.append(" ERR");
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        float[] d = {0, 1};
        float[] r = {-1000, 1000};

        // ---- div / ln / log / exp: IEEE special then /Range clip (NOT an error)
        emit("div0", "{ pop 1 0 div }", d, r, new float[] {0});
        emit("div0neg", "{ pop -1 0 div }", d, r, new float[] {0});
        emit("div00", "{ pop 0 0 div }", d, r, new float[] {0});
        emit("ln0", "{ pop 0 ln }", d, r, new float[] {0});
        emit("lnneg", "{ pop -5 ln }", d, r, new float[] {0});
        emit("log0", "{ pop 0 log }", d, r, new float[] {0});
        emit("logneg", "{ pop -5 log }", d, r, new float[] {0});
        emit("exp_negbase", "{ pop -2 0.5 exp }", d, r, new float[] {0});
        emit("exp_00", "{ pop 0 0 exp }", d, r, new float[] {0});

        // ---- legitimately raise
        emit("idiv0", "{ pop 1 0 idiv }", d, r, new float[] {0});
        emit("mod0", "{ pop 1 0 mod }", d, r, new float[] {0});
        emit("sqrt_neg", "{ pop -1 sqrt }", d, r, new float[] {0});
        emit("add_bool", "{ pop true 1 add }", d, r, new float[] {0});
        emit("if_nonbool", "{ pop 1 { 5 } if }", d, r, new float[] {0});
        emit("undersupply", "{ pop }", d, r, new float[] {0});
        emit("exch_under", "{ pop exch }", d, r, new float[] {0});

        // ---- sign-semantics: mod follows dividend, idiv truncates toward zero
        emit("mod_neg", "{ pop -7 3 mod }", d, r, new float[] {0});
        emit("mod_neg2", "{ pop 7 -3 mod }", d, r, new float[] {0});
        emit("idiv_neg", "{ pop -7 2 idiv }", d, r, new float[] {0});
        emit("idiv_neg2", "{ pop 7 -2 idiv }", d, r, new float[] {0});

        // ---- round ties toward +inf, cvi truncates toward zero
        emit("round_pos", "{ pop 2.5 round }", d, r, new float[] {0});
        emit("round_neg", "{ pop -2.5 round }", d, r, new float[] {0});
        emit("round_neg15", "{ pop -1.5 round }", d, r, new float[] {0});
        emit("cvi_neg", "{ pop -3.9 cvi }", d, r, new float[] {0});

        // ---- atan four quadrants, degrees in [0, 360)
        emit("atan_q1", "{ pop 1 1 atan }", d, r, new float[] {0});
        emit("atan_q2", "{ pop 1 -1 atan }", d, r, new float[] {0});
        emit("atan_q3", "{ pop -1 -1 atan }", d, r, new float[] {0});
        emit("atan_q4", "{ pop -1 1 atan }", d, r, new float[] {0});
        emit("atan_00", "{ pop 0 0 atan }", d, r, new float[] {0});

        // ---- bitshift left/right, negative value
        emit("shift_left", "{ pop 3 8 bitshift }", new float[] {0, 1},
             new float[] {0, 100000}, new float[] {0});
        emit("shift_right", "{ pop 256 -2 bitshift }", new float[] {0, 1},
             new float[] {0, 100000}, new float[] {0});
        emit("shift_neg_val", "{ pop -8 1 bitshift }", d, r, new float[] {0});

        // ---- index/copy/roll accept a Float count (lenient Number.intValue())
        emit("index_float", "{ pop 10 20 30 2.0 0 mul 1 add index }", d, r, new float[] {0});
    }
}
