import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Live oracle probe: Apache PDFBox PDFunctionType0 (sampled) MALFORMED-dict eval
 * (wave 1535, agent D — fuzz audit).
 *
 * Where FunctionType0Bit32 / Degenerate / Order probes cover valid bit-widths,
 * degenerate shapes and the /Order no-op, this probe targets the malformed
 * dictionary surfaces:
 *  - /Size missing / wrong length (!= input count) / zero / negative / huge.
 *  - /BitsPerSample invalid: 0, 3, 64 (not in {1,2,4,8,12,16,24,32}).
 *  - sample stream shorter than Size-product * BitsPerSample (truncated body).
 *  - /Encode missing (default), wrong length (too short), non-numeric entries.
 *  - /Decode missing (defaults to /Range), wrong length (too short).
 *  - input exactly on a sample boundary vs between (interpolation).
 *  - 1-D vs 2-D sampled function shapes.
 *  - clipping at Domain / Range edges.
 *
 * Line grammar:  FUNC <name> <in0,...> -> <out0> <out1> ...  (or "-> ERR").
 * "ERR" is emitted when PDFBox throws (any Throwable) for that input — the
 * pypdfbox side must then also raise (parity on the failure mode).
 */
public final class FunctionType0SampledFuzzProbe {

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

    static void emit(String name, PDFunction fn, float[] in) {
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

    /** Build the stream, but emit ERR for the whole battery if PDFunction.create throws. */
    static PDFunction make(String name, int bits, COSArray size, COSArray domain,
                           COSArray range, COSArray encode, COSArray decode,
                           byte[] body) {
        try {
            COSStream s = new COSStream();
            s.setInt(COSName.FUNCTION_TYPE, 0);
            s.setItem(COSName.DOMAIN, domain);
            s.setItem(COSName.RANGE, range);
            if (size != null) {
                s.setItem(COSName.SIZE, size);
            }
            s.setInt(COSName.BITS_PER_SAMPLE, bits);
            if (encode != null) {
                s.setItem(COSName.ENCODE, encode);
            }
            if (decode != null) {
                s.setItem(COSName.DECODE, decode);
            }
            java.io.OutputStream os = s.createOutputStream();
            os.write(body);
            os.close();
            return PDFunction.create(s);
        } catch (Throwable e) {
            return null;
        }
    }

    static void battery(String name, PDFunction fn, float[][] inputs) {
        for (float[] in : inputs) {
            if (fn == null) {
                StringBuilder sb = new StringBuilder("FUNC ").append(name).append(' ');
                for (int i = 0; i < in.length; i++) {
                    if (i > 0) {
                        sb.append(',');
                    }
                    sb.append(Double.toString((double) in[i]));
                }
                sb.append(" -> ERR");
                out.println(sb.toString());
            } else {
                emit(name, fn, in);
            }
        }
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // valid 1-D, 8-bit, 4 samples [0,64,192,255] — boundary vs between.
        byte[] b4 = new byte[] {0, 64, (byte) 192, (byte) 255};
        float[][] x1 = {{0f}, {0.25f}, {0.3333333f}, {0.5f}, {0.6666667f}, {0.75f}, {1f}};

        // 1) /Size missing.
        battery("size_missing",
            make("size_missing", 8, null, floats(0, 1), floats(0, 1), null, null, b4), x1);

        // 2) /Size wrong length: 2 entries for a 1-input function.
        battery("size_len2",
            make("size_len2", 8, ints(4, 4), floats(0, 1), floats(0, 1), null, null, b4), x1);

        // 3) /Size too short: 1 entry for a 2-input function.
        battery("size_short2d",
            make("size_short2d", 8, ints(2), floats(0, 1, 0, 1), floats(0, 1),
                null, null, b4),
            new float[][] {{0, 0}, {0.5f, 0.5f}, {1, 1}});

        // 4) /Size zero.
        battery("size_zero",
            make("size_zero", 8, ints(0), floats(0, 1), floats(0, 1), null, null, b4), x1);

        // 5) /Size negative.
        battery("size_neg",
            make("size_neg", 8, ints(-4), floats(0, 1), floats(0, 1), null, null, b4), x1);

        // 6) /Size huge (product would overflow / OOM if materialised).
        battery("size_huge",
            make("size_huge", 8, ints(1000000000), floats(0, 1), floats(0, 1), null, null, b4),
            new float[][] {{0f}, {0.5f}});

        // 7) /BitsPerSample = 0.
        battery("bits0",
            make("bits0", 0, ints(4), floats(0, 1), floats(0, 1), null, null, b4), x1);

        // 8) /BitsPerSample = 3 (unsupported).
        battery("bits3",
            make("bits3", 3, ints(4), floats(0, 1), floats(0, 1), null, null, b4), x1);

        // 9) /BitsPerSample = 64 (unsupported).
        battery("bits64",
            make("bits64", 64, ints(4), floats(0, 1), floats(0, 1), null, null, b4), x1);

        // 10) sample stream truncated: 4 samples declared, only 2 bytes given.
        battery("trunc_body",
            make("trunc_body", 8, ints(4), floats(0, 1), floats(0, 1), null, null,
                new byte[] {0, 64}),
            x1);

        // 11) empty sample stream.
        battery("empty_body",
            make("empty_body", 8, ints(4), floats(0, 1), floats(0, 1), null, null,
                new byte[] {}),
            x1);

        // 12) /Encode missing (default [0 Size-1]) — same as valid baseline.
        battery("enc_missing",
            make("enc_missing", 8, ints(4), floats(0, 1), floats(0, 1), null, null, b4), x1);

        // 13) /Encode too short: only one value.
        battery("enc_short",
            make("enc_short", 8, ints(4), floats(0, 1), floats(0, 1), floats(1), null, b4), x1);

        // 14) /Encode wrong length on 2-D: only 2 values for 2 dims (needs 4).
        byte[] b22 = new byte[] {0, 100, (byte) 200, (byte) 255};
        battery("enc_short2d",
            make("enc_short2d", 8, ints(2, 2), floats(0, 1, 0, 1), floats(0, 255),
                floats(0, 1), floats(0, 255), b22),
            new float[][] {{0, 0}, {0.5f, 0.5f}, {1, 1}});

        // 15) /Decode missing (defaults to /Range).
        battery("dec_missing",
            make("dec_missing", 8, ints(4), floats(0, 1), floats(0, 10), null, null, b4), x1);

        // 16) /Decode too short.
        battery("dec_short",
            make("dec_short", 8, ints(4), floats(0, 1), floats(0, 10), null, floats(5), b4), x1);

        // 17) input exactly on sample boundary vs between, finer grid (8 samples).
        byte[] b8 = new byte[] {0, 32, 64, 96, (byte) 128, (byte) 160, (byte) 192, (byte) 255};
        battery("grid8",
            make("grid8", 8, ints(8), floats(0, 1), floats(0, 1), null, null, b8),
            new float[][] {{0f}, {0.142857f}, {0.2f}, {0.5f}, {0.857143f}, {1f}});

        // 18) 2-D bilinear baseline (well-formed) for contrast.
        battery("bilin2d",
            make("bilin2d", 8, ints(2, 2), floats(0, 1, 0, 1), floats(0, 255),
                null, floats(0, 255), b22),
            new float[][] {{0, 0}, {1, 0}, {0, 1}, {1, 1}, {0.5f, 0.5f}, {0.25f, 0.75f}});

        // 19) Domain-edge clipping: domain [0.2,0.8], inputs outside.
        battery("dom_edge",
            make("dom_edge", 8, ints(4), floats(0.2f, 0.8f), floats(0, 1), null, null, b4),
            new float[][] {{-1f}, {0f}, {0.2f}, {0.8f}, {1f}, {5f}});

        // 20) Range-edge clipping: /Decode maps wide but /Range narrow.
        battery("range_clip",
            make("range_clip", 8, ints(4), floats(0, 1), floats(0.25f, 0.75f),
                null, floats(0, 1), b4),
            x1);

        // 21) /Size has a non-numeric entry (a COSName) at index 0.
        COSArray badSize = new COSArray();
        badSize.add(COSName.getPDFName("X"));
        battery("size_nonnum",
            make("size_nonnum", 8, badSize, floats(0, 1), floats(0, 1), null, null, b4), x1);
    }
}
