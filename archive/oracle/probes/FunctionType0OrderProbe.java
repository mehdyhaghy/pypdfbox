import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Live oracle probe: Apache PDFBox PDFunctionType0 (sampled) eval edge cases
 * (wave 1500, agent C — parity audit round 7).
 *
 * Targets the surfaces the existing Bit32 / Degenerate probes do not cover:
 *  - /Order 1 vs 3: upstream PDFunctionType0.eval IGNORES /Order entirely and
 *    always interpolates n-linearly (there is no cubic branch). The two batteries
 *    below must therefore produce byte-identical output — this pins that pypdfbox
 *    does NOT apply a cubic spline for /Order 3.
 *  - /Size 1 degenerate dimension (single sample, no neighbour).
 *  - inverted /Encode [hi lo] and inverted /Decode [hi lo].
 *  - 2-input bilinear interpolation.
 *  - /BitsPerSample 1, 12, 16 packing.
 *  - out-of-domain input clamping.
 *
 * Line grammar:  FUNC <name> <in0,...> -> <out0> <out1> ...  (or "-> ERR").
 */
public final class FunctionType0OrderProbe {

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

    static COSArray ints(int... vals) {
        COSArray a = new COSArray();
        for (int v : vals) {
            a.add(COSInteger.get(v));
        }
        return a;
    }

    static void emit(String name, PDFunction fn, float[] in) throws Exception {
        StringBuilder sb = new StringBuilder("FUNC ").append(name).append(' ');
        for (int i = 0; i < in.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(Double.toString((double) in[i]));
        }
        sb.append(" ->");
        try {
            float[] o = fn.eval(in);
            for (float v : o) {
                sb.append(' ').append(fmt(v));
            }
        } catch (Throwable e) {
            sb.append(" ERR");
        }
        out.println(sb.toString());
    }

    static COSStream t0(int bits, int order, COSArray size, COSArray domain,
                        COSArray range, COSArray encode, COSArray decode,
                        byte[] body) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 0);
        s.setItem(COSName.DOMAIN, domain);
        s.setItem(COSName.RANGE, range);
        s.setItem(COSName.SIZE, size);
        s.setInt(COSName.BITS_PER_SAMPLE, bits);
        if (order != 1) {
            s.setInt(COSName.ORDER, order);
        }
        if (encode != null) {
            s.setItem(COSName.ENCODE, encode);
        }
        if (decode != null) {
            s.setItem(COSName.DECODE, decode);
        }
        java.io.OutputStream os = s.createOutputStream();
        os.write(body);
        os.close();
        return s;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // 1D, 8-bit, 4 samples [0,64,192,255], /Order 1 vs 3 — identical output.
        byte[] b4 = new byte[] {0, 64, (byte) 192, (byte) 255};
        for (int order : new int[] {1, 3}) {
            PDFunction fn = PDFunction.create(
                t0(8, order, ints(4), floats(0, 1), floats(0, 1), null, null, b4));
            for (float x : new float[] {0f, 0.1f, 0.25f, 0.333f, 0.5f, 0.666f, 0.75f, 0.9f, 1f}) {
                emit("ord" + order, fn, new float[] {x});
            }
        }

        // /Size 1 degenerate dimension, single 8-bit sample 128.
        PDFunction fdeg = PDFunction.create(
            t0(8, 1, ints(1), floats(0, 1), floats(0, 1), null, null, new byte[] {(byte) 128}));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("size1", fdeg, new float[] {x});
        }

        // inverted /Encode [3 0] on 4 samples.
        PDFunction finv = PDFunction.create(
            t0(8, 1, ints(4), floats(0, 1), floats(0, 1), floats(3, 0), null, b4));
        for (float x : new float[] {0f, 0.25f, 0.5f, 1f}) {
            emit("invenc", finv, new float[] {x});
        }

        // inverted /Decode [1 0].
        PDFunction fdec = PDFunction.create(
            t0(8, 1, ints(4), floats(0, 1), floats(0, 1), null, floats(1, 0), b4));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("invdec", fdec, new float[] {x});
        }

        // 2D bilinear, 2x2, 8-bit: (0,0)=0 (1,0)=100 (0,1)=200 (1,1)=255.
        byte[] b22 = new byte[] {0, 100, (byte) 200, (byte) 255};
        PDFunction f2d = PDFunction.create(
            t0(8, 1, ints(2, 2), floats(0, 1, 0, 1), floats(0, 255), null, floats(0, 255), b22));
        for (float[] in : new float[][] {{0, 0}, {1, 0}, {0, 1}, {1, 1}, {0.5f, 0.5f}, {0.25f, 0.75f}}) {
            emit("bilin", f2d, in);
        }

        // 1-bit, 4 samples packed 1,0,1,1 => 0xB0.
        PDFunction f1 = PDFunction.create(
            t0(1, 1, ints(4), floats(0, 1), floats(0, 1), null, null, new byte[] {(byte) 0xB0}));
        for (float x : new float[] {0f, 0.333f, 0.666f, 1f}) {
            emit("bit1", f1, new float[] {x});
        }

        // 16-bit, 2 samples 0x0000 0xFFFF.
        PDFunction f16 = PDFunction.create(
            t0(16, 1, ints(2), floats(0, 1), floats(0, 1), null, null,
               new byte[] {0, 0, (byte) 0xFF, (byte) 0xFF}));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("bit16", f16, new float[] {x});
        }

        // 12-bit, 2 samples 0x000 0xFFF packed 00 0F FF.
        PDFunction f12 = PDFunction.create(
            t0(12, 1, ints(2), floats(0, 1), floats(0, 1), null, null,
               new byte[] {0x00, 0x0F, (byte) 0xFF}));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("bit12", f12, new float[] {x});
        }

        // out-of-domain clamp: domain [0.2, 0.8], input 0 and 1.
        PDFunction fclamp = PDFunction.create(
            t0(8, 1, ints(4), floats(0.2f, 0.8f), floats(0, 1), null, null, b4));
        for (float x : new float[] {0f, 0.2f, 0.8f, 1f}) {
            emit("domclamp", fclamp, new float[] {x});
        }
    }
}
