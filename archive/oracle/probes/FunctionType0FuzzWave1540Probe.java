import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Live oracle probe: Apache PDFBox PDFunctionType0 (sampled) fuzz — wave 1540,
 * agent A.
 *
 * Complements FunctionType0SampledFuzzProbe (wave 1535) by drilling the
 * NON-NORMALISING clip surfaces that the wave-1539 Type 4 audit flagged as a
 * likely shared bug: PDFunctionType0.eval clips its inputs (to /Domain), the
 * encoded coordinate (to [0, Size-1]) and its outputs (to /Range) with the
 * scalar clipToRange(F,F,F) which does NOT swap a reversed (min,max) pair.
 *
 * Cases:
 *  - reversed /Domain, reversed /Range, reversed /Encode, reversed /Decode.
 *  - clamping exactly at and beyond Domain / Range edges.
 *  - empty / short / long / non-numeric /Domain /Range /Encode /Decode.
 *  - /Size zero / negative / huge / wrong-arity / non-numeric.
 *  - /BitsPerSample at 1,2,4,8,12,16,24,32 and invalid 0,3,64.
 *  - sample stream too short / too long.
 *  - nearest vs linear at grid points and between, domain extremes.
 *  - multi-input multi-output sampling.
 *
 * Also emits NPARAMS lines: "<name> NOUT <n>" projecting
 * getNumberOfOutputParameters() (-1 sentinel-safe via Integer.toString).
 *
 * Line grammar:  FUNC <name> <in0,...> -> <out0> <out1> ...  (or "-> ERR").
 * "ERR" is emitted when PDFBox throws (any Throwable) for that input.
 */
public final class FunctionType0FuzzWave1540Probe {

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

    static PDFunction make(int bits, COSArray size, COSArray domain,
                           COSArray range, COSArray encode, COSArray decode,
                           byte[] body) {
        try {
            COSStream s = new COSStream();
            s.setInt(COSName.FUNCTION_TYPE, 0);
            if (domain != null) {
                s.setItem(COSName.DOMAIN, domain);
            }
            if (range != null) {
                s.setItem(COSName.RANGE, range);
            }
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

    static void nout(String name, PDFunction fn) {
        String v;
        if (fn == null) {
            v = "ERR";
        } else {
            try {
                v = Integer.toString(fn.getNumberOfOutputParameters());
            } catch (Throwable e) {
                v = "ERR";
            }
        }
        out.println("NOUT " + name + " " + v);
    }

    static void battery(String name, PDFunction fn, float[][] inputs) {
        nout(name, fn);
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

        // 1-D, 8-bit, 4 samples [0,64,192,255].
        byte[] b4 = new byte[] {0, 64, (byte) 192, (byte) 255};
        float[][] x1 = {{-1f}, {0f}, {0.25f}, {0.5f}, {0.75f}, {1f}, {2f}};

        // ---------- reversed clip pairs (the wave-1540 focus) ----------

        // 1) reversed /Domain [1,0]. clipToRange(x,1,0): x<1 -> 1, x>0 -> 0,
        //    else x. So any x>0 -> 0, any x<1 (and not >0) impossible; x in (0,1)
        //    is >0 so -> 0; x==0 -> not<1? 0<1 true -> 1; wait: scalar order is
        //    min-first then max. Pin whatever Java does, do not predict.
        battery("dom_rev",
            make(8, ints(4), floats(1, 0), floats(0, 1), null, null, b4), x1);

        // 2) reversed /Range [1,0] — output clip collapses.
        battery("range_rev",
            make(8, ints(4), floats(0, 1), floats(1, 0), null, floats(0, 1), b4), x1);

        // 3) reversed /Encode [3,0] — encode maps then clamps to [0,Size-1].
        battery("enc_rev",
            make(8, ints(4), floats(0, 1), floats(0, 1), floats(3, 0), null, b4), x1);

        // 4) reversed /Decode [1,0].
        battery("dec_rev",
            make(8, ints(4), floats(0, 1), floats(0, 1), null, floats(1, 0), b4), x1);

        // 5) reversed /Domain AND reversed /Range together.
        battery("dom_range_rev",
            make(8, ints(4), floats(0.8f, 0.2f), floats(1, 0), null, floats(0, 1), b4), x1);

        // ---------- edge clamping at/beyond Domain and Range ----------

        // 6) narrow Domain [0.2,0.8], probe outside both edges.
        battery("dom_clamp",
            make(8, ints(4), floats(0.2f, 0.8f), floats(0, 1), null, null, b4),
            new float[][] {{-5f}, {0.2f}, {0.5f}, {0.8f}, {5f}});

        // 7) narrow Range [0.25,0.75], wide /Decode forces clamp.
        battery("range_clamp",
            make(8, ints(4), floats(0, 1), floats(0.25f, 0.75f), null, floats(0, 1), b4),
            x1);

        // ---------- empty / short / long / non-numeric arrays ----------

        // 8) empty /Domain (num_in=0).
        battery("dom_empty",
            make(8, ints(4), floats(), floats(0, 1), null, null, b4),
            new float[][] {{0f}, {0.5f}});

        // 9) /Domain odd length (3 entries -> 1 pair, last ignored).
        battery("dom_odd",
            make(8, ints(4), floats(0, 1, 2), floats(0, 1), null, null, b4), x1);

        // 10) empty /Range (num_out=0).
        battery("range_empty",
            make(8, ints(4), floats(0, 1), floats(), null, null, b4), x1);

        // 11) /Range odd length (3 entries).
        battery("range_odd",
            make(8, ints(4), floats(0, 1), floats(0, 1, 2), null, null, b4), x1);

        // 12) /Domain non-numeric entry.
        COSArray domBad = new COSArray();
        domBad.add(COSName.getPDFName("X"));
        domBad.add(new COSFloat(1));
        battery("dom_nonnum",
            make(8, ints(4), domBad, floats(0, 1), null, null, b4), x1);

        // 13) /Range non-numeric entry.
        COSArray rangeBad = new COSArray();
        rangeBad.add(new COSFloat(0));
        rangeBad.add(COSName.getPDFName("Y"));
        battery("range_nonnum",
            make(8, ints(4), floats(0, 1), rangeBad, null, null, b4), x1);

        // 14) /Encode non-numeric entry.
        COSArray encBad = new COSArray();
        encBad.add(COSName.getPDFName("E"));
        encBad.add(new COSFloat(3));
        battery("enc_nonnum",
            make(8, ints(4), floats(0, 1), floats(0, 1), encBad, null, b4), x1);

        // 15) /Decode non-numeric entry.
        COSArray decBad = new COSArray();
        decBad.add(new COSFloat(0));
        decBad.add(COSName.getPDFName("D"));
        battery("dec_nonnum",
            make(8, ints(4), floats(0, 1), floats(0, 1), null, decBad, b4), x1);

        // 16) /Encode too long (4 entries for 1-D — extra ignored).
        battery("enc_long",
            make(8, ints(4), floats(0, 1), floats(0, 1), floats(0, 3, 9, 9), null, b4), x1);

        // ---------- /Size variants ----------

        // 17) /Size zero.
        battery("size_zero",
            make(8, ints(0), floats(0, 1), floats(0, 1), null, null, b4), x1);

        // 18) /Size negative.
        battery("size_neg",
            make(8, ints(-4), floats(0, 1), floats(0, 1), null, null, b4), x1);

        // 19) /Size non-numeric.
        COSArray sizeBad = new COSArray();
        sizeBad.add(COSName.getPDFName("S"));
        battery("size_nonnum",
            make(8, sizeBad, floats(0, 1), floats(0, 1), null, null, b4), x1);

        // 20) /Size wrong arity (2 for 1-D).
        battery("size_arity",
            make(8, ints(4, 4), floats(0, 1), floats(0, 1), null, null, b4), x1);

        // ---------- /BitsPerSample sweep ----------

        // 21) bits=1, 8 samples packed in one byte 0b10110010.
        byte[] b1 = new byte[] {(byte) 0b10110010};
        battery("bits1",
            make(1, ints(8), floats(0, 1), floats(0, 1), null, null, b1),
            new float[][] {{0f}, {0.142857f}, {0.5f}, {0.857143f}, {1f}});

        // 22) bits=2, 4 samples in one byte 0b00_01_10_11 = 0x1B.
        byte[] b2 = new byte[] {(byte) 0x1B};
        battery("bits2",
            make(2, ints(4), floats(0, 1), floats(0, 1), null, null, b2),
            new float[][] {{0f}, {0.3333333f}, {0.6666667f}, {1f}});

        // 23) bits=4, 4 samples 0x0F 0xA5 -> 0,15,10,5.
        byte[] b4w = new byte[] {0x0F, (byte) 0xA5};
        battery("bits4",
            make(4, ints(4), floats(0, 1), floats(0, 1), null, null, b4w),
            new float[][] {{0f}, {0.3333333f}, {0.6666667f}, {1f}});

        // 24) bits=12, 2 samples 0x000 0xFFF in 3 bytes.
        byte[] b12 = new byte[] {0x00, 0x0F, (byte) 0xFF};
        battery("bits12",
            make(12, ints(2), floats(0, 1), floats(0, 1), null, null, b12),
            new float[][] {{0f}, {0.5f}, {1f}});

        // 25) bits=16, 2 samples 0x0000 0xFFFF.
        byte[] b16 = new byte[] {0x00, 0x00, (byte) 0xFF, (byte) 0xFF};
        battery("bits16",
            make(16, ints(2), floats(0, 1), floats(0, 1), null, null, b16),
            new float[][] {{0f}, {0.5f}, {1f}});

        // 26) bits=24, 2 samples.
        byte[] b24 = new byte[] {0, 0, 0, (byte) 0xFF, (byte) 0xFF, (byte) 0xFF};
        battery("bits24",
            make(24, ints(2), floats(0, 1), floats(0, 1), null, null, b24),
            new float[][] {{0f}, {0.5f}, {1f}});

        // 27) bits=32, 2 samples 0 and 0xFFFFFFFF (top bit set -> signed quirk).
        byte[] b32 = new byte[] {0, 0, 0, 0,
            (byte) 0xFF, (byte) 0xFF, (byte) 0xFF, (byte) 0xFF};
        battery("bits32",
            make(32, ints(2), floats(0, 1), floats(0, 1), null, null, b32),
            new float[][] {{0f}, {0.5f}, {1f}});

        // 28) bits=0 (off-spec but readable).
        battery("bits0",
            make(0, ints(4), floats(0, 1), floats(0, 1), null, null, b4), x1);

        // 29) bits=3 (off-spec).
        battery("bits3",
            make(3, ints(4), floats(0, 1), floats(0, 1), null, null, b4), x1);

        // 30) bits=64 (invalid).
        battery("bits64",
            make(64, ints(4), floats(0, 1), floats(0, 1), null, null, b4), x1);

        // ---------- sample stream length ----------

        // 31) body too short (4 samples declared, 2 bytes).
        battery("body_short",
            make(8, ints(4), floats(0, 1), floats(0, 1), null, null, new byte[] {0, 64}),
            x1);

        // 32) body too long (4 samples declared, 8 bytes — extra ignored).
        battery("body_long",
            make(8, ints(4), floats(0, 1), floats(0, 1), null, null,
                new byte[] {0, 64, (byte) 192, (byte) 255, 1, 2, 3, 4}),
            x1);

        // ---------- nearest vs linear at grid points ----------

        // 33) grid8 — exactly on grid points and between.
        byte[] b8 = new byte[] {0, 32, 64, 96, (byte) 128, (byte) 160, (byte) 192, (byte) 255};
        battery("grid8",
            make(8, ints(8), floats(0, 1), floats(0, 1), null, null, b8),
            new float[][] {{0f}, {0.142857f}, {0.214286f}, {0.5f}, {0.857143f}, {1f}});

        // ---------- multi-input multi-output ----------

        // 34) 2-in 2-out: 2x2 grid, each cell 2 outputs -> 8 bytes.
        byte[] mio = new byte[] {0, (byte) 255, 64, (byte) 192,
            (byte) 128, 32, (byte) 200, 16};
        battery("mio_2x2",
            make(8, ints(2, 2), floats(0, 1, 0, 1), floats(0, 1, 0, 1),
                null, floats(0, 255, 0, 255), mio),
            new float[][] {{0, 0}, {1, 0}, {0, 1}, {1, 1}, {0.5f, 0.5f}});

        // 35) 2-in 1-out reversed Domain on second axis.
        battery("mio_dom_rev",
            make(8, ints(2, 2), floats(0, 1, 1, 0), floats(0, 1),
                null, floats(0, 1), new byte[] {0, 100, (byte) 200, (byte) 255}),
            new float[][] {{0, 0}, {0.5f, 0.5f}, {1, 1}});
    }
}
