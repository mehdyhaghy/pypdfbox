import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Live oracle probe focused on the 32-bit /BitsPerSample signed-cast quirk:
 * upstream reads each sample with {@code (int) mciis.readBits(32)}, so a 32-bit
 * code with the high bit set is truncated to a NEGATIVE int before the /Decode
 * mapping + /Range clamp. This probe enumerates representative 32-bit codes so
 * the Python differential test can pin the exact upstream numerics.
 *
 * Line grammar: FUNC <name> <in,..> -> <out> ...
 */
public final class FunctionType0Bit32Probe {

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

    // Pack 32-bit codes MSB-first. Each code given as a long but only low 32
    // bits used.
    static byte[] pack32(long[] values) {
        byte[] b = new byte[values.length * 4];
        for (int i = 0; i < values.length; i++) {
            long v = values[i] & 0xFFFFFFFFL;
            b[i * 4] = (byte) ((v >>> 24) & 0xFF);
            b[i * 4 + 1] = (byte) ((v >>> 16) & 0xFF);
            b[i * 4 + 2] = (byte) ((v >>> 8) & 0xFF);
            b[i * 4 + 3] = (byte) (v & 0xFF);
        }
        return b;
    }

    static COSStream type0Raw(byte[] body, int[] size, int bps, float[] domain,
                              float[] range, float[] decode) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 0);
        s.setItem(COSName.DOMAIN, floats(domain));
        s.setItem(COSName.RANGE, floats(range));
        s.setItem(COSName.SIZE, ints(size));
        s.setInt(COSName.BITS_PER_SAMPLE, bps);
        if (decode != null) {
            s.setItem(COSName.DECODE, floats(decode));
        }
        java.io.OutputStream os = s.createOutputStream();
        os.write(body);
        os.close();
        return s;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // 2-sample 32-bit: [low, high] where high has top bit set.
        // maxSample = 2^32 - 1 = 4294967295. decode default = range [0,1].
        // (int)readBits(32) for 0x80000000 -> -2147483648; for 0xFFFFFFFF -> -1.
        long[][] cases = {
            {0L, 0x7FFFFFFFL},          // both non-negative as int
            {0L, 0x80000000L},          // high -> Integer.MIN
            {0L, 0xFFFFFFFFL},          // high -> -1
            {0x80000000L, 0xFFFFFFFFL}, // both negative as int
        };
        String[] names = {"T32_maxpos", "T32_min", "T32_neg1", "T32_bothneg"};
        for (int c = 0; c < cases.length; c++) {
            PDFunction fn = PDFunction.create(
                type0Raw(pack32(cases[c]), new int[] {2}, 32,
                         new float[] {0, 1}, new float[] {-2, 2}, null));
            for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
                emit(names[c], fn, new float[] {x});
            }
        }

        // Wider range so the negative sample isn't clamped: range [-5, 5],
        // decode [-5, 5]. sample -1 -> interpolate(-1, 0, 4294967295, -5, 5)
        // ~= -5 + (-1/4294967295)*10 ~= -5.0 (tiny). Pin it.
        PDFunction fn2 = PDFunction.create(
            type0Raw(pack32(new long[] {0L, 0xFFFFFFFFL}), new int[] {2}, 32,
                     new float[] {0, 1}, new float[] {-5, 5}, null));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("T32_wide", fn2, new float[] {x});
        }
    }
}
