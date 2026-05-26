import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Live oracle probe: emit Apache PDFBox's PDFunction.eval() output for a fixed
 * battery of Type 0 / 2 / 3 / 4 functions across a grid of inputs.
 *
 * Focuses on the eval numerics the Python differential test reproduces:
 *  - Type 0 sampled: 1-in/1-out, 1-in/3-out, 2-in/1-out interpolation,
 *    asymmetric 3D /Size, /Encode reversal, /Decode inversion, sub-8-bit
 *    and 16-bit sample widths.
 *  - Type 2 exponential: N != 1, multi-component C0/C1, range clamp.
 *  - Type 3 stitching: 2- and 3-child partitions across bounds, reversed
 *    /Encode in a sub-domain.
 *  - Type 4 PostScript: each operator category exercised with a small
 *    program (arithmetic, transcendental, stack dup/exch/copy/index/roll,
 *    comparison, boolean, bitwise, if/ifelse).
 *
 * Line grammar (must match the Python harness in the differential test):
 *
 *   FUNC <name> <in0,in1,...> -> <out0> <out1> ...
 *
 * Each float is rendered with %.6f so the comparison is locale-independent.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> FunctionEvalProbe
 */
public final class FunctionEvalProbe {

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
            // Render the input at full precision (the float widened to a
            // double) so the Python side reconstructs the exact same value
            // PDFBox evaluated internally — a 6-dp render of e.g. 1f/3f
            // would feed a slightly different number into pypdfbox and
            // produce spurious sub-1e-4 divergences near sample boundaries.
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

    static COSArray ints(int... vals) {
        COSArray a = new COSArray();
        for (int v : vals) {
            a.add(COSInteger.get(v));
        }
        return a;
    }

    // ---------- function builders ----------

    static COSDictionary type2(float[] c0, float[] c1, float n, float[] domain, float[] range) {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 2);
        d.setItem(COSName.DOMAIN, floats(domain));
        if (c0 != null) {
            d.setItem(COSName.C0, floats(c0));
        }
        if (c1 != null) {
            d.setItem(COSName.C1, floats(c1));
        }
        d.setItem(COSName.N, new COSFloat(n));
        if (range != null) {
            d.setItem(COSName.RANGE, floats(range));
        }
        return d;
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

    // Pack MSB-first sample codes (no padding between values) into bytes.
    static byte[] pack(int[] values, int bits) {
        long totalBits = (long) values.length * bits;
        java.math.BigInteger big = java.math.BigInteger.ZERO;
        long mask = (bits >= 64) ? -1L : ((1L << bits) - 1);
        for (int v : values) {
            big = big.shiftLeft(bits).or(java.math.BigInteger.valueOf(v & mask));
        }
        int pad = (int) ((8 - (totalBits % 8)) % 8);
        big = big.shiftLeft(pad);
        int nbytes = (int) ((totalBits + pad) / 8);
        if (nbytes == 0) {
            return new byte[0];
        }
        byte[] raw = big.toByteArray();
        // BigInteger.toByteArray() may include a leading sign byte or be
        // shorter than nbytes (no leading zeros); normalise to nbytes.
        byte[] outb = new byte[nbytes];
        int copy = Math.min(raw.length, nbytes);
        System.arraycopy(raw, raw.length - copy, outb, nbytes - copy, copy);
        return outb;
    }

    static COSStream type0(int[] sampleCodes, int[] size, int bps, float[] domain,
                           float[] range, float[] encode, float[] decode) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 0);
        s.setItem(COSName.DOMAIN, floats(domain));
        s.setItem(COSName.RANGE, floats(range));
        s.setItem(COSName.SIZE, ints(size));
        s.setInt(COSName.BITS_PER_SAMPLE, bps);
        if (encode != null) {
            s.setItem(COSName.ENCODE, floats(encode));
        }
        if (decode != null) {
            s.setItem(COSName.DECODE, floats(decode));
        }
        byte[] body = pack(sampleCodes, bps);
        java.io.OutputStream os = s.createOutputStream();
        os.write(body);
        os.close();
        return s;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ============ Type 2 (exponential) ============
        // N=2 single component over [0,1].
        PDFunction t2quad = PDFunction.create(
            type2(new float[] {0}, new float[] {1}, 2.0f, new float[] {0, 1}, null));
        for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emit("T2quad", t2quad, new float[] {x});
        }
        // N=0.5 two components.
        PDFunction t2sqrt = PDFunction.create(
            type2(new float[] {0, 1}, new float[] {1, 0}, 0.5f, new float[] {0, 1}, null));
        for (float x : new float[] {0.1f, 0.5f, 0.9f}) {
            emit("T2sqrt", t2sqrt, new float[] {x});
        }
        // N=3, 3 components, range clamp [0 1] with C1 overshoot.
        PDFunction t2clamp = PDFunction.create(
            type2(new float[] {0, 0.2f, -0.5f}, new float[] {1, 0.8f, 1.5f}, 3.0f,
                  new float[] {0, 1}, new float[] {0, 1, 0, 1, 0, 1}));
        for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emit("T2clamp", t2clamp, new float[] {x});
        }

        // ============ Type 3 (stitching) ============
        // Two Type 2 children, bound at 0.5, encode [0 1 0 1].
        COSArray funcs = new COSArray();
        funcs.add(type2(new float[] {0}, new float[] {1}, 1.0f, new float[] {0, 1}, null));
        funcs.add(type2(new float[] {1}, new float[] {0}, 1.0f, new float[] {0, 1}, null));
        COSDictionary t3d = new COSDictionary();
        t3d.setInt(COSName.FUNCTION_TYPE, 3);
        t3d.setItem(COSName.DOMAIN, floats(0, 1));
        t3d.setItem(COSName.FUNCTIONS, funcs);
        t3d.setItem(COSName.BOUNDS, floats(0.5f));
        t3d.setItem(COSName.ENCODE, floats(0, 1, 0, 1));
        PDFunction t3 = PDFunction.create(t3d);
        for (float x : new float[] {0f, 0.25f, 0.49f, 0.5f, 0.51f, 0.75f, 1f}) {
            emit("T3stitch", t3, new float[] {x});
        }
        // Three children, bounds [0.3 0.7], reversed encode in the middle child.
        COSArray funcs3 = new COSArray();
        funcs3.add(type2(new float[] {0}, new float[] {1}, 1.0f, new float[] {0, 1}, null));
        funcs3.add(type2(new float[] {0}, new float[] {1}, 1.0f, new float[] {0, 1}, null));
        funcs3.add(type2(new float[] {0}, new float[] {1}, 2.0f, new float[] {0, 1}, null));
        COSDictionary t3b = new COSDictionary();
        t3b.setInt(COSName.FUNCTION_TYPE, 3);
        t3b.setItem(COSName.DOMAIN, floats(0, 1));
        t3b.setItem(COSName.FUNCTIONS, funcs3);
        t3b.setItem(COSName.BOUNDS, floats(0.3f, 0.7f));
        // Middle child encodes (1,0) -> reversed mapping inside its sub-domain.
        t3b.setItem(COSName.ENCODE, floats(0, 1, 1, 0, 0, 1));
        PDFunction t3three = PDFunction.create(t3b);
        for (float x : new float[] {0f, 0.15f, 0.3f, 0.5f, 0.7f, 0.85f, 1f}) {
            emit("T3three", t3three, new float[] {x});
        }

        // ============ Type 0 (sampled) ============
        // 1-in 1-out, 8-bit, 3 samples.
        PDFunction t0lin = PDFunction.create(
            type0(new int[] {0, 128, 255}, new int[] {3}, 8,
                  new float[] {0, 1}, new float[] {0, 1}, null, null));
        for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emit("T0lin", t0lin, new float[] {x});
        }
        // 1-in 3-out, 8-bit, 2 samples red->blue.
        PDFunction t0rgb = PDFunction.create(
            type0(new int[] {255, 0, 0, 0, 0, 255}, new int[] {2}, 8,
                  new float[] {0, 1}, new float[] {0, 1, 0, 1, 0, 1}, null, null));
        for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emit("T0rgb", t0rgb, new float[] {x});
        }
        // 2-in 1-out, 2x2 grid: index = x0 + x1*2.
        PDFunction t0grid = PDFunction.create(
            type0(new int[] {0, 85, 170, 255}, new int[] {2, 2}, 8,
                  new float[] {0, 1, 0, 1}, new float[] {0, 1}, null, null));
        for (float[] in : new float[][] {
                {0, 0}, {1, 0}, {0, 1}, {1, 1}, {0.5f, 0.5f}, {0.25f, 0.75f}}) {
            emit("T0grid", t0grid, in);
        }
        // Asymmetric 3D /Size = [2,3,4]: index = x + 2*y + 6*z. sample[i]=i*10.
        int total3d = 2 * 3 * 4;
        int[] s3d = new int[total3d];
        for (int i = 0; i < total3d; i++) {
            s3d[i] = i * 10;
        }
        PDFunction t03d = PDFunction.create(
            type0(s3d, new int[] {2, 3, 4}, 8,
                  new float[] {0, 1, 0, 1, 0, 1}, new float[] {0, 255}, null, null));
        for (float[] in : new float[][] {
                {0, 0, 0}, {1, 0, 0}, {0, 0.5f, 0}, {0, 0, 1f / 3f},
                {1, 1, 1}, {0.5f, 0.5f, 0.5f}}) {
            emit("T03d", t03d, in);
        }
        // /Encode reversal: encode pair (3,0) reverses the axis.
        PDFunction t0enc = PDFunction.create(
            type0(new int[] {10, 20, 30, 40}, new int[] {4}, 8,
                  new float[] {0, 1}, new float[] {0, 255}, new float[] {3, 0}, null));
        for (float x : new float[] {0f, 1f / 3f, 2f / 3f, 1f}) {
            emit("T0enc", t0enc, new float[] {x});
        }
        // /Decode inversion: decode [1,0] flips sample->output.
        PDFunction t0dec = PDFunction.create(
            type0(new int[] {0, 127, 255}, new int[] {3}, 8,
                  new float[] {0, 1}, new float[] {0, 1}, null, new float[] {1, 0}));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("T0dec", t0dec, new float[] {x});
        }
        // 4-bit width, 4 samples [0,5,10,15].
        PDFunction t0n4 = PDFunction.create(
            type0(new int[] {0, 5, 10, 15}, new int[] {4}, 4,
                  new float[] {0, 1}, new float[] {0, 1}, null, null));
        for (float x : new float[] {0f, 0.33f, 0.66f, 1f}) {
            emit("T0n4", t0n4, new float[] {x});
        }
        // 16-bit width, 2 samples [0, 65535].
        PDFunction t0n16 = PDFunction.create(
            type0(new int[] {0, 65535}, new int[] {2}, 16,
                  new float[] {0, 1}, new float[] {0, 1}, null, null));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("T0n16", t0n16, new float[] {x});
        }

        // ============ Type 4 (PostScript calculator) ============
        // -- arithmetic / transcendental --
        emit4("T4sub", "{ 1 exch sub }", new float[] {0, 1}, new float[] {0, 1},
              new float[][] {{0f}, {0.25f}, {0.5f}, {0.75f}, {1f}});
        emit4("T4tint", "{ dup 0.3 mul exch 0.7 mul }",
              new float[] {0, 1}, new float[] {0, 1, 0, 1},
              new float[][] {{0f}, {0.5f}, {1f}});
        emit4("T4divmod", "{ 7 div }", new float[] {0, 100}, new float[] {0, 100},
              new float[][] {{0f}, {14f}, {50f}});
        // idiv/mod operate on integer literals only — PDFBox's popInt
        // requires an Integer on the stack (a clipped float input would
        // throw ClassCastException), so the program uses literals and
        // ignores the (float) input.
        emit4("T4idivmod", "{ pop 17 5 idiv 17 5 mod add }",
              new float[] {0, 100}, new float[] {0, 100},
              new float[][] {{1f}, {2f}, {3f}});
        emit4("T4math", "{ 360 mul sin abs }",
              new float[] {0, 1}, new float[] {0, 1},
              new float[][] {{0f}, {0.125f}, {0.25f}, {0.5f}, {0.75f}});
        emit4("T4trans", "{ dup sqrt exch 1 add ln add }",
              new float[] {0.01f, 10}, new float[] {0, 100},
              new float[][] {{1f}, {4f}, {9f}});
        emit4("T4atan", "{ 1 atan }", new float[] {-5, 5}, new float[] {0, 360},
              new float[][] {{1f}, {0f}, {-1f}});
        emit4("T4exp", "{ 2 exch exp }", new float[] {0, 8}, new float[] {0, 300},
              new float[][] {{0f}, {3f}, {8f}});
        emit4("T4rounders", "{ 0.5 add floor }", new float[] {0, 10}, new float[] {0, 10},
              new float[][] {{1.2f}, {1.7f}, {2.5f}});
        emit4("T4cvi", "{ cvi }", new float[] {-10, 10}, new float[] {-10, 10},
              new float[][] {{3.9f}, {-3.9f}, {5f}});
        // -- stack ops: copy, index, roll --
        emit4("T4copy", "{ 2 copy add 3 1 roll sub exch }",
              new float[] {0, 100, 0, 100}, new float[] {-200, 200, -200, 200},
              new float[][] {{3f, 5f}, {10f, 4f}});
        emit4("T4index", "{ 0 index add }",
              new float[] {0, 100, 0, 100}, new float[] {0, 200, 0, 200},
              new float[][] {{3f, 5f}, {10f, 20f}});
        emit4("T4roll", "{ 3 1 roll }",
              new float[] {0, 9, 0, 9, 0, 9}, new float[] {0, 9, 0, 9, 0, 9},
              new float[][] {{1f, 2f, 3f}});
        emit4("T4rollneg", "{ 3 -1 roll }",
              new float[] {0, 9, 0, 9, 0, 9}, new float[] {0, 9, 0, 9, 0, 9},
              new float[][] {{1f, 2f, 3f}});
        // -- comparison + conditional --
        emit4("T4cond", "{ 0.5 lt { 0 } { 1 } ifelse }",
              new float[] {0, 1}, new float[] {0, 1},
              new float[][] {{0f}, {0.49f}, {0.5f}, {0.51f}, {1f}});
        emit4("T4if", "{ dup 0.5 gt { 0.25 sub } if }",
              new float[] {0, 1}, new float[] {0, 1},
              new float[][] {{0.2f}, {0.6f}, {0.9f}});
        // -- boolean / bitwise (operands recovered then mapped to a number) --
        emit4("T4bool", "{ 2 copy gt 3 1 roll lt and { 1 } { 0 } ifelse }",
              new float[] {0, 10, 0, 10}, new float[] {0, 1},
              new float[][] {{5f, 3f}, {3f, 5f}});
        // -- a representative 1-in 3-out tint transform --
        emit4("T4rgb", "{ dup 1 exch sub 0.5 }",
              new float[] {0, 1}, new float[] {0, 1, 0, 1, 0, 1},
              new float[][] {{0f}, {0.5f}, {1f}});
    }

    static void emit4(String name, String ps, float[] domain, float[] range,
                      float[][] inputs) throws Exception {
        PDFunction fn = PDFunction.create(type4(ps, domain, range));
        for (float[] in : inputs) {
            emit(name, fn, in);
        }
    }
}
