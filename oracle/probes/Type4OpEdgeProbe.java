import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Live oracle probe: pin Apache PDFBox's PDFunction.eval() for Type 4
 * PostScript-calculator operator EDGE CASES the broader FunctionEvalProbe
 * battery does not exercise.
 *
 * Targets behaviour that is easy to get subtly wrong and where PDFBox's
 * concrete choice (not the PostScript Reference text) is the parity contract:
 *  - bitwise/boolean: not on an int (PDFBox negates, NOT bit-inverts),
 *    or / xor / and on ints, bitshift left and right (incl. negative shift).
 *  - sign semantics: idiv / mod with negative operands (truncate-toward-zero
 *    quotient; remainder sign follows dividend).
 *  - rounding family: round ties (toward +inf), ceiling/floor/truncate on
 *    negatives, cvi (truncate toward zero), cvr.
 *  - transcendental: cos, log, neg, abs, atan over the [0,360) wrap.
 *  - relational: eq / ne / le / ge mapped through ifelse.
 *  - Type 2 input outside /Domain (domain-clip before exponentiation).
 *
 * Line grammar (shared with the Python harness):
 *
 *   FUNC <name> <in0,in1,...> -> <out0> <out1> ...
 *
 * Each float is rendered %.6f; each input rendered at full double precision
 * so the Python side reconstructs the exact value PDFBox evaluated.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Type4OpEdgeProbe
 */
public final class Type4OpEdgeProbe {

    static PrintStream out;

    static String fmt(float v) {
        return String.format(java.util.Locale.ROOT, "%.6f", v);
    }

    static String fmtIn(float[] in) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < in.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(Double.toString((double) in[i]));
        }
        return sb.toString();
    }

    static void emit(String name, PDFunction fn, float[] in) throws Exception {
        float[] outv = fn.eval(in);
        StringBuilder sb = new StringBuilder();
        sb.append("FUNC ").append(name).append(' ').append(fmtIn(in)).append(" ->");
        for (float v : outv) {
            sb.append(' ').append(fmt(v));
        }
        out.println(sb.toString());
    }

    static COSArray floats(float... vals) {
        COSArray a = new COSArray();
        for (float v : vals) {
            a.add(new COSFloat(v));
        }
        return a;
    }

    static COSStream type4(String ps, float[] domain, float[] range) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 4);
        s.setItem(COSName.DOMAIN, floats(domain));
        s.setItem(COSName.RANGE, floats(range));
        java.io.OutputStream os = s.createOutputStream();
        os.write(ps.getBytes("US-ASCII"));
        os.close();
        return s;
    }

    static void emit4(String name, String ps, float[] domain, float[] range,
                      float[][] inputs) throws Exception {
        PDFunction fn = PDFunction.create(type4(ps, domain, range));
        for (float[] in : inputs) {
            emit(name, fn, in);
        }
    }

    static COSStream type2(float[] c0, float[] c1, float n, float[] domain,
                           float[] range) {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 2);
        s.setItem(COSName.DOMAIN, floats(domain));
        s.setItem(COSName.C0, floats(c0));
        s.setItem(COSName.C1, floats(c1));
        s.setItem(COSName.N, new COSFloat(n));
        if (range != null) {
            s.setItem(COSName.RANGE, floats(range));
        }
        return s;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ---- bitwise / boolean on integers ----
        // `not` on an integer: PDFBox negates (-int), the PostScript Reference
        // would bit-invert. Pin PDFBox's actual choice.
        emit4("T4notint", "{ pop 5 not }", new float[] {0, 1}, new float[] {-10, 10},
              new float[][] {{0f}});
        emit4("T4notbool", "{ 0.5 gt not { 1 } { 0 } ifelse }",
              new float[] {0, 1}, new float[] {0, 1},
              new float[][] {{0.2f}, {0.8f}});
        // or / xor / and on integer literals.
        emit4("T4orint", "{ pop 12 10 or }", new float[] {0, 1}, new float[] {0, 64},
              new float[][] {{0f}});
        emit4("T4xorint", "{ pop 12 10 xor }", new float[] {0, 1}, new float[] {0, 64},
              new float[][] {{0f}});
        emit4("T4andint", "{ pop 12 10 and }", new float[] {0, 1}, new float[] {0, 64},
              new float[][] {{0f}});
        // bitshift: positive shift = left, negative = right.
        emit4("T4shl", "{ pop 1 4 bitshift }", new float[] {0, 1}, new float[] {0, 256},
              new float[][] {{0f}});
        emit4("T4shr", "{ pop 64 -3 bitshift }", new float[] {0, 1}, new float[] {0, 256},
              new float[][] {{0f}});

        // ---- sign semantics: idiv / mod with negatives ----
        emit4("T4idivneg", "{ pop -17 5 idiv }", new float[] {0, 1},
              new float[] {-100, 100}, new float[][] {{0f}});
        emit4("T4idivnegb", "{ pop 17 -5 idiv }", new float[] {0, 1},
              new float[] {-100, 100}, new float[][] {{0f}});
        emit4("T4modneg", "{ pop -17 5 mod }", new float[] {0, 1},
              new float[] {-100, 100}, new float[][] {{0f}});
        emit4("T4modnegb", "{ pop 17 -5 mod }", new float[] {0, 1},
              new float[] {-100, 100}, new float[][] {{0f}});

        // ---- rounding family on negatives + ties ----
        emit4("T4round", "{ round }", new float[] {-10, 10}, new float[] {-10, 10},
              new float[][] {{2.5f}, {-2.5f}, {2.4f}, {-2.6f}, {0.5f}});
        emit4("T4ceil", "{ ceiling }", new float[] {-10, 10}, new float[] {-10, 10},
              new float[][] {{2.1f}, {-2.1f}, {3f}});
        emit4("T4floorneg", "{ floor }", new float[] {-10, 10}, new float[] {-10, 10},
              new float[][] {{2.9f}, {-2.1f}});
        emit4("T4trunc", "{ truncate }", new float[] {-10, 10}, new float[] {-10, 10},
              new float[][] {{2.9f}, {-2.9f}});
        emit4("T4cvineg", "{ cvi }", new float[] {-10, 10}, new float[] {-10, 10},
              new float[][] {{-3.9f}, {3.9f}});
        emit4("T4cvr", "{ cvi cvr 0.5 add }", new float[] {-10, 10},
              new float[] {-10, 10}, new float[][] {{3.9f}});

        // ---- transcendental ----
        emit4("T4cos", "{ 180 mul cos }", new float[] {0, 2}, new float[] {-1, 1},
              new float[][] {{0f}, {0.5f}, {1f}, {1.5f}, {2f}});
        emit4("T4log", "{ 1000 mul log }", new float[] {0.001f, 1},
              new float[] {0, 3}, new float[][] {{0.001f}, {0.01f}, {1f}});
        emit4("T4neg", "{ neg }", new float[] {-5, 5}, new float[] {-5, 5},
              new float[][] {{3f}, {-3f}, {0f}});
        emit4("T4absneg", "{ abs }", new float[] {-5, 5}, new float[] {0, 5},
              new float[][] {{-4f}, {4f}, {0f}});
        // atan over the wrap: num=sin, den=cos sampled around the circle.
        emit4("T4atanwrap", "{ 90 mul dup sin exch cos atan }",
              new float[] {0, 4}, new float[] {0, 360},
              new float[][] {{0f}, {1f}, {2f}, {3f}});

        // ---- relational: eq / ne / le / ge via ifelse ----
        emit4("T4eq", "{ 2 eq { 1 } { 0 } ifelse }", new float[] {0, 5},
              new float[] {0, 1}, new float[][] {{2f}, {3f}});
        emit4("T4ne", "{ 2 ne { 1 } { 0 } ifelse }", new float[] {0, 5},
              new float[] {0, 1}, new float[][] {{2f}, {3f}});
        emit4("T4le", "{ 2 le { 1 } { 0 } ifelse }", new float[] {0, 5},
              new float[] {0, 1}, new float[][] {{1f}, {2f}, {3f}});
        emit4("T4ge", "{ 2 ge { 1 } { 0 } ifelse }", new float[] {0, 5},
              new float[] {0, 1}, new float[][] {{1f}, {2f}, {3f}});

        // ---- Type 2 input outside /Domain (clip before exponentiation) ----
        PDFunction t2dom = PDFunction.create(
            type2(new float[] {0}, new float[] {1}, 2.0f, new float[] {0.25f, 0.75f},
                  null));
        for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emit("T2dom", t2dom, new float[] {x});
        }
    }
}
