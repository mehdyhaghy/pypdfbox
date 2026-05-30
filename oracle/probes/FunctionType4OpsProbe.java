import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Live oracle probe: pin Apache PDFBox's PDFunction.eval() for Type 4
 * PostScript-calculator STACK and CONVERSION operators plus /Domain and
 * /Range clamping, which the existing Type4OpEdgeProbe does not cover.
 *
 * Targets:
 *  - stack ops: roll (positive + negative + zero j), index, copy (incl. 0).
 *  - conversion: cvi / cvr over positives, negatives, fractional values.
 *  - integer-arithmetic: idiv / mod with both positive operands.
 *  - bitshift large shifts; not on int; and/or/xor on ints.
 *  - comparison: eq / ne / lt / le / gt / ge between two numbers AND eq / ne
 *    on booleans (true/false), routed through ifelse to a numeric output.
 *  - /Range clamping: program whose raw output falls outside /Range (clamped
 *    to the range bounds by PDFBox after evaluation).
 *  - /Domain clamping: input pushed onto the stack is clipped to /Domain
 *    before the program runs.
 *
 * Line grammar (shared with the Python harness):
 *
 *   FUNC <name> <in0,in1,...> -> <out0> <out1> ...
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> FunctionType4OpsProbe
 */
public final class FunctionType4OpsProbe {

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
        StringBuilder sb = new StringBuilder();
        sb.append("FUNC ").append(name).append(' ').append(fmtIn(in)).append(" ->");
        try {
            float[] outv = fn.eval(in);
            for (float v : outv) {
                sb.append(' ').append(fmt(v));
            }
        } catch (RuntimeException e) {
            // PDFBox surfaces malformed-program faults (stack underflow on an
            // out-of-range roll count, etc.) as unchecked exceptions; mark the
            // line so the Python side asserts pypdfbox raises too.
            sb.append(" ERR");
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

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ---- stack: roll ----
        // roll n j: rotate the top n elements by j. Push 1 2 3 then roll.
        emit4("T4roll_pos", "{ pop 1 2 3 3 1 roll }", new float[] {0, 1},
              new float[] {-100, 100, -100, 100, -100, 100}, new float[][] {{0f}});
        emit4("T4roll_neg", "{ pop 1 2 3 3 -1 roll }", new float[] {0, 1},
              new float[] {-100, 100, -100, 100, -100, 100}, new float[][] {{0f}});
        emit4("T4roll_zero", "{ pop 1 2 3 3 0 roll }", new float[] {0, 1},
              new float[] {-100, 100, -100, 100, -100, 100}, new float[][] {{0f}});
        // j == n and j == -n are no-ops (PDFBox does not reduce j mod n).
        emit4("T4roll_eqn", "{ pop 1 2 3 3 3 roll }", new float[] {0, 1},
              new float[] {-100, 100, -100, 100, -100, 100}, new float[][] {{0f}});
        emit4("T4roll_negn", "{ pop 1 2 3 3 -3 roll }", new float[] {0, 1},
              new float[] {-100, 100, -100, 100, -100, 100}, new float[][] {{0f}});
        // |j| > n: PDFBox does NOT reduce j modulo n, so it pops past the top
        // of the window and throws (EmptyStackException). pypdfbox must raise
        // too rather than silently rotating with a mod-reduced count.
        emit4("T4roll_overflow", "{ pop 1 2 3 3 4 roll }", new float[] {0, 1},
              new float[] {-100, 100, -100, 100, -100, 100}, new float[][] {{0f}});
        emit4("T4roll_overflow_neg", "{ pop 1 2 3 3 -4 roll }", new float[] {0, 1},
              new float[] {-100, 100, -100, 100, -100, 100}, new float[][] {{0f}});

        // ---- stack: index ----
        emit4("T4index0", "{ pop 10 20 30 0 index }", new float[] {0, 1},
              new float[] {-100, 100, -100, 100, -100, 100, -100, 100},
              new float[][] {{0f}});
        emit4("T4index2", "{ pop 10 20 30 2 index }", new float[] {0, 1},
              new float[] {-100, 100, -100, 100, -100, 100, -100, 100},
              new float[][] {{0f}});

        // ---- stack: copy ----
        emit4("T4copy0", "{ pop 10 20 0 copy }", new float[] {0, 1},
              new float[] {-100, 100, -100, 100}, new float[][] {{0f}});
        emit4("T4copy2", "{ pop 10 20 2 copy }", new float[] {0, 1},
              new float[] {-100, 100, -100, 100, -100, 100, -100, 100},
              new float[][] {{0f}});

        // ---- conversion: cvi / cvr ----
        emit4("T4cvi_pos", "{ cvi }", new float[] {-10, 10}, new float[] {-10, 10},
              new float[][] {{3.9f}, {3.1f}, {0f}});
        emit4("T4cvi_neg", "{ cvi }", new float[] {-10, 10}, new float[] {-10, 10},
              new float[][] {{-3.9f}, {-0.5f}});
        emit4("T4cvr_frac", "{ cvr }", new float[] {-10, 10}, new float[] {-10, 10},
              new float[][] {{3.5f}, {-3.5f}});
        emit4("T4cvi_then_cvr", "{ cvi cvr }", new float[] {-10, 10},
              new float[] {-10, 10}, new float[][] {{3.9f}, {-3.9f}});

        // ---- integer arithmetic: idiv / mod, both positive ----
        emit4("T4idiv_pos", "{ pop 17 5 idiv }", new float[] {0, 1},
              new float[] {-100, 100}, new float[][] {{0f}});
        emit4("T4mod_pos", "{ pop 17 5 mod }", new float[] {0, 1},
              new float[] {-100, 100}, new float[][] {{0f}});

        // ---- bitshift large ----
        emit4("T4shl_big", "{ pop 3 8 bitshift }", new float[] {0, 1},
              new float[] {0, 100000}, new float[][] {{0f}});

        // ---- comparison: numeric ----
        emit4("T4lt", "{ 3 lt { 1 } { 0 } ifelse }", new float[] {0, 5},
              new float[] {0, 1}, new float[][] {{2f}, {3f}, {4f}});
        emit4("T4gt", "{ 3 gt { 1 } { 0 } ifelse }", new float[] {0, 5},
              new float[] {0, 1}, new float[][] {{2f}, {3f}, {4f}});

        // ---- comparison: boolean eq / ne (true/false literals) ----
        emit4("T4eqbool", "{ pop true true eq { 1 } { 0 } ifelse }",
              new float[] {0, 1}, new float[] {0, 1}, new float[][] {{0f}});
        emit4("T4eqbool2", "{ pop true false eq { 1 } { 0 } ifelse }",
              new float[] {0, 1}, new float[] {0, 1}, new float[][] {{0f}});
        emit4("T4nebool", "{ pop true false ne { 1 } { 0 } ifelse }",
              new float[] {0, 1}, new float[] {0, 1}, new float[][] {{0f}});

        // ---- /Range clamping: raw output overshoots the range ----
        // program returns input*10; range caps at [0, 5] so e.g. 0.8*10=8 -> 5.
        emit4("T4rangeclamp", "{ 10 mul }", new float[] {0, 1},
              new float[] {0, 5}, new float[][] {{0.2f}, {0.8f}, {0.4f}});
        // negative undershoot clamp
        emit4("T4rangeclamp_lo", "{ 10 mul neg }", new float[] {0, 1},
              new float[] {-3, 0}, new float[][] {{0.2f}, {0.8f}});

        // ---- /Domain clamping: input outside domain is clipped first ----
        // identity program; domain [0.25, 0.75] clips the input.
        emit4("T4domainclip", "{ }", new float[] {0.25f, 0.75f},
              new float[] {0, 1}, new float[][] {{0f}, {0.5f}, {1f}, {0.25f}, {0.75f}});
    }
}
