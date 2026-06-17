import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Live oracle probe: emit Apache PDFBox PDFunctionType0.eval() output for the
 * degenerate / boundary cases the existing FunctionEvalProbe battery does NOT
 * cover:
 *
 *  - /Size[i] == 1 (interpolation collapses to the single sample on that axis)
 *  - empty sample stream (zero-length body — upstream zero-fills new int[][])
 *  - short / truncated sample stream (fewer bytes than the grid needs —
 *    upstream catches the IOException and leaves trailing cells zero)
 *  - input exactly at each domain boundary
 *  - 1-bit / 2-bit packed widths at boundaries
 *
 * Line grammar matches FunctionEvalProbe:
 *   FUNC <name> <in0,in1,...> -> <out0> <out1> ...
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> FunctionType0DegenerateProbe
 */
public final class FunctionType0DegenerateProbe {

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

    static COSArray ints(int... vals) {
        COSArray a = new COSArray();
        for (int v : vals) {
            a.add(COSInteger.get(v));
        }
        return a;
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
        byte[] outb = new byte[nbytes];
        int copy = Math.min(raw.length, nbytes);
        System.arraycopy(raw, raw.length - copy, outb, nbytes - copy, copy);
        return outb;
    }

    // Build a Type 0 with an explicit raw body (so we can truncate it).
    static COSStream type0Raw(byte[] body, int[] size, int bps, float[] domain,
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
        java.io.OutputStream os = s.createOutputStream();
        os.write(body);
        os.close();
        return s;
    }

    static COSStream type0(int[] sampleCodes, int[] size, int bps, float[] domain,
                           float[] range, float[] encode, float[] decode) throws Exception {
        return type0Raw(pack(sampleCodes, bps), size, bps, domain, range, encode, decode);
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ---- /Size[i] == 1 on the single axis: 1-in 1-out, 1 sample ----
        // Encode default = [0 (1-1)] = [0 0]; the only sample is 200.
        PDFunction t0size1 = PDFunction.create(
            type0(new int[] {200}, new int[] {1}, 8,
                  new float[] {0, 1}, new float[] {0, 255}, null, null));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("T0size1", t0size1, new float[] {x});
        }

        // ---- 2-in 1-out where one axis has /Size == 1 (collapses) ----
        // /Size = [1, 3]; grid index = x*1step? layout: first dim fastest.
        // cells: (0,0)=10 (0,1)=20 (0,2)=30. x axis collapses to 0.
        PDFunction t0collapse = PDFunction.create(
            type0(new int[] {10, 20, 30}, new int[] {1, 3}, 8,
                  new float[] {0, 1, 0, 1}, new float[] {0, 255}, null, null));
        for (float[] in : new float[][] {
                {0, 0}, {0.5f, 0}, {0, 0.5f}, {1, 1}, {0.3f, 0.5f}}) {
            emit("T0collapse", t0collapse, in);
        }

        // ---- empty sample stream (zero-length body) ----
        PDFunction t0empty = PDFunction.create(
            type0Raw(new byte[0], new int[] {3}, 8,
                     new float[] {0, 1}, new float[] {0, 255}, null, null));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("T0empty", t0empty, new float[] {x});
        }

        // ---- short / truncated body: grid needs 3 bytes, supply 1 ----
        // sample 0 = 100, rest should be zero-filled by upstream.
        byte[] shortBody = new byte[] {(byte) 100};
        PDFunction t0short = PDFunction.create(
            type0Raw(shortBody, new int[] {3}, 8,
                     new float[] {0, 1}, new float[] {0, 255}, null, null));
        for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emit("T0short", t0short, new float[] {x});
        }

        // ---- input exactly at domain boundaries (non-[0,1] domain) ----
        // domain [-2, 6], 5 samples evenly: 0,40,80,120,160.
        PDFunction t0dom = PDFunction.create(
            type0(new int[] {0, 40, 80, 120, 160}, new int[] {5}, 8,
                  new float[] {-2, 6}, new float[] {0, 255}, null, null));
        for (float x : new float[] {-2f, 6f, 2f, -3f, 7f}) {
            emit("T0dom", t0dom, new float[] {x});
        }

        // ---- 1-bit width: 4 samples [0,1,1,0] over [0,1] ----
        PDFunction t01bit = PDFunction.create(
            type0(new int[] {0, 1, 1, 0}, new int[] {4}, 1,
                  new float[] {0, 1}, new float[] {0, 1}, null, null));
        for (float x : new float[] {0f, 1f / 3f, 0.5f, 2f / 3f, 1f}) {
            emit("T01bit", t01bit, new float[] {x});
        }

        // ---- 2-bit width: 4 samples [0,1,2,3] over [0,1] ----
        PDFunction t02bit = PDFunction.create(
            type0(new int[] {0, 1, 2, 3}, new int[] {4}, 2,
                  new float[] {0, 1}, new float[] {0, 3}, null, null));
        for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emit("T02bit", t02bit, new float[] {x});
        }

        // ---- 24-bit width: 2 samples [0, 16777215] ----
        PDFunction t024bit = PDFunction.create(
            type0(new int[] {0, 16777215}, new int[] {2}, 24,
                  new float[] {0, 1}, new float[] {0, 1}, null, null));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("T024bit", t024bit, new float[] {x});
        }

        // ---- 32-bit width: 2 samples [0, 4294967295] ----
        // Note upstream casts readBits(32) to int -> may be negative.
        long[] s32 = {0L, 4294967295L};
        int[] s32i = new int[] {(int) s32[0], (int) s32[1]};
        PDFunction t032bit = PDFunction.create(
            type0(s32i, new int[] {2}, 32,
                  new float[] {0, 1}, new float[] {0, 1}, null, null));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("T032bit", t032bit, new float[] {x});
        }
    }
}
