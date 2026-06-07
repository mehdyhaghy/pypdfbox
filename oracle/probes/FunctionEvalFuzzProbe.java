import java.io.OutputStream;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Differential fuzz probe for PDF function construction + evaluation
 * ({@code PDFunction.create(COSBase)} followed by {@code eval(float[])}),
 * Apache PDFBox 3.0.7 (wave 1509, agent E).
 *
 * Complements the existing eval oracles (FunctionEvalProbe,
 * FunctionType0OrderProbe, FunctionType23EdgeProbe, FunctionType4*Probe)
 * which all assume a well-formed COS spec. This probe targets the
 * construction-leniency contract — what {@code create()} does with a missing
 * /FunctionType, an unknown type, a non-dictionary base, a COSObject-wrapped
 * /Identity, etc. — alongside a representative malformed-spec eval battery
 * (Type0 BitsPerSample sweep + truncated/oversized sample streams + Size
 * mismatches; Type2 N corners + C0/C1 length mismatch; Type3 degenerate
 * Bounds; Type4 operator / division-by-zero / underflow / brace corners).
 *
 * Deterministic and seed-free: the corpus is a fixed list built inline; no
 * Date.now / unseeded random. The pypdfbox sibling
 * (tests/pdmodel/common/function/oracle/test_function_eval_fuzz_wave1509.py)
 * rebuilds the identical COS specs and asserts each line matches.
 *
 * Line grammar (one per case):
 *   CASE &lt;name&gt; create=&lt;ok|ERR&gt; [eval=&lt;ERR | f0 f1 ...&gt;]
 * "create=ERR" means create() threw (pypdfbox must also raise on create).
 * "eval=ERR" means create() succeeded but eval() threw (pypdfbox must raise
 * on eval). A float list means both succeeded; floats are %.6f (or the IEEE
 * tokens NaN / Infinity / -Infinity).
 */
public final class FunctionEvalFuzzProbe {

    static PrintStream out;

    static String fmt(float v) {
        if (Float.isNaN(v)) {
            return "NaN";
        }
        if (Float.isInfinite(v)) {
            return v > 0 ? "Infinity" : "-Infinity";
        }
        return String.format(Locale.ROOT, "%.6f", v);
    }

    static COSArray ints(int... vals) {
        COSArray a = new COSArray();
        for (int v : vals) {
            a.add(COSInteger.get(v));
        }
        return a;
    }

    static COSArray floats(double... vals) {
        COSArray a = new COSArray();
        for (double v : vals) {
            a.add(new COSFloat((float) v));
        }
        return a;
    }

    static COSStream stream(int bitsPerSample, COSArray size, COSArray domain,
                            COSArray range, COSArray encode, COSArray decode,
                            byte[] samples) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 0);
        s.setInt(COSName.BITS_PER_SAMPLE, bitsPerSample);
        s.setItem(COSName.SIZE, size);
        s.setItem(COSName.DOMAIN, domain);
        s.setItem(COSName.RANGE, range);
        if (encode != null) {
            s.setItem(COSName.ENCODE, encode);
        }
        if (decode != null) {
            s.setItem(COSName.DECODE, decode);
        }
        OutputStream os = s.createOutputStream();
        os.write(samples);
        os.close();
        return s;
    }

    // pack N samples of the given bit width, MSB-first, into a byte[]
    static byte[] pack(int bitsPerSample, int... samples) {
        long bits = (long) bitsPerSample * samples.length;
        int nbytes = (int) ((bits + 7) / 8);
        byte[] b = new byte[nbytes];
        int bitPos = 0;
        for (int sample : samples) {
            for (int k = bitsPerSample - 1; k >= 0; k--) {
                int bit = (sample >> k) & 1;
                if (bit != 0) {
                    b[bitPos >> 3] |= (byte) (0x80 >> (bitPos & 7));
                }
                bitPos++;
            }
        }
        return b;
    }

    static COSStream t4(String ps) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 4);
        s.setItem(COSName.DOMAIN, floats(0, 1));
        s.setItem(COSName.RANGE, floats(-1000, 1000));
        OutputStream os = s.createOutputStream();
        os.write(ps.getBytes("US-ASCII"));
        os.close();
        return s;
    }

    static void emit(String name, COSBase spec, float[] in) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        PDFunction fn;
        try {
            fn = PDFunction.create(spec);
        } catch (Throwable t) {
            out.println(sb.append("create=ERR").toString());
            return;
        }
        sb.append("create=ok");
        if (in == null) {
            out.println(sb.toString());
            return;
        }
        sb.append(" eval=");
        try {
            float[] o = fn.eval(in);
            StringBuilder vals = new StringBuilder();
            for (int i = 0; i < o.length; i++) {
                if (i > 0) {
                    vals.append(' ');
                }
                vals.append(fmt(o[i]));
            }
            sb.append(vals);
        } catch (Throwable t) {
            sb.append("ERR");
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ============ construction-leniency contract ============
        emit("create_null", null, null);
        emit("create_name_identity", COSName.IDENTITY, new float[] {0.3f, 0.7f});
        // a value-equal Identity name (interned -> same singleton in PDFBox)
        emit("create_name_identity2", COSName.getPDFName("Identity"),
             new float[] {0.5f});
        // COSObject-wrapped Identity: create() checks the *raw* arg against the
        // IDENTITY singleton BEFORE dereference, so a wrapper does NOT match and
        // the dereferenced COSName is not a COSDictionary -> IOException.
        emit("create_obj_identity", new COSObject(COSName.IDENTITY), null);
        // a non-Identity COSName -> not a dictionary -> IOException
        emit("create_name_other", COSName.getPDFName("Foo"), null);
        // a bare COSArray -> not a dictionary -> IOException
        emit("create_array", floats(1, 2, 3), null);
        // a COSInteger -> not a dictionary -> IOException
        emit("create_int", COSInteger.get(5), null);

        COSDictionary noType = new COSDictionary();
        noType.setItem(COSName.DOMAIN, floats(0, 1));
        // missing /FunctionType -> getInt returns -1 -> "Unknown function type -1"
        emit("create_no_functiontype", noType, null);

        COSDictionary type1 = new COSDictionary();
        type1.setInt(COSName.FUNCTION_TYPE, 1);
        // /FunctionType 1 (never existed) -> default branch -> IOException
        emit("create_functiontype1", type1, null);

        COSDictionary type5 = new COSDictionary();
        type5.setInt(COSName.FUNCTION_TYPE, 5);
        emit("create_functiontype5", type5, null);

        COSDictionary typeNeg = new COSDictionary();
        typeNeg.setInt(COSName.FUNCTION_TYPE, -3);
        emit("create_functiontype_neg", typeNeg, null);

        // COSObject wrapping a real Type2 dict -> dereferenced, dispatched
        COSDictionary t2dict = new COSDictionary();
        t2dict.setInt(COSName.FUNCTION_TYPE, 2);
        t2dict.setItem(COSName.DOMAIN, floats(0, 1));
        t2dict.setItem(COSName.N, COSInteger.get(1));
        emit("create_obj_type2", new COSObject(t2dict), new float[] {0.5f});

        // Type 2 (exponential) as a COSStream is unusual but constructs fine
        // (COSStream IS-A COSDictionary in PDFBox).
        // -- covered below in the eval battery --

        // ============ Type 0 — BitsPerSample sweep ============
        // 1-D identity-ish table over /Size [2], one output, Domain/Range [0,1].
        // sample max value = (1<<bps)-1; midpoint input picks last sample here
        // because Size 2 with input 1.0 hits index 1.
        for (int bps : new int[] {1, 2, 4, 8, 12, 16, 24, 32}) {
            int max = (bps >= 31) ? Integer.MAX_VALUE : (1 << bps) - 1;
            byte[] samples = pack(bps, 0, max);
            COSStream s = stream(bps, ints(2), floats(0, 1), floats(0, 1),
                                 null, null, samples);
            emit("t0_bps" + bps + "_at0", s, new float[] {0.0f});
            COSStream s2 = stream(bps, ints(2), floats(0, 1), floats(0, 1),
                                  null, null, pack(bps, 0, max));
            emit("t0_bps" + bps + "_at1", s2, new float[] {1.0f});
            COSStream s3 = stream(bps, ints(2), floats(0, 1), floats(0, 1),
                                  null, null, pack(bps, 0, max));
            emit("t0_bps" + bps + "_mid", s3, new float[] {0.5f});
        }

        // ---- Size mismatch / truncated / oversized sample streams ----
        // /Size [4] declared but only 2 samples present (truncated stream)
        emit("t0_truncated", stream(8, ints(4), floats(0, 1), floats(0, 1),
             null, null, pack(8, 0, 255)), new float[] {1.0f});
        // /Size [2] but 6 samples present (oversized) — extra ignored
        emit("t0_oversized", stream(8, ints(2), floats(0, 1), floats(0, 1),
             null, null, pack(8, 0, 128, 255, 64, 32, 16)), new float[] {1.0f});
        // empty sample stream, /Size [2]
        emit("t0_empty_stream", stream(8, ints(2), floats(0, 1), floats(0, 1),
             null, null, new byte[0]), new float[] {0.0f});
        // /Size [1] degenerate single-sample dimension
        emit("t0_size1", stream(8, ints(1), floats(0, 1), floats(0, 1),
             null, null, pack(8, 200)), new float[] {0.5f});

        // ---- Encode / Decode overrides ----
        // inverted /Encode [1 0] flips the table lookup
        emit("t0_encode_inv", stream(8, ints(2), floats(0, 1), floats(0, 1),
             floats(1, 0), null, pack(8, 0, 255)), new float[] {0.0f});
        // /Decode [0 100] remaps output range
        emit("t0_decode", stream(8, ints(2), floats(0, 1), floats(0, 1),
             null, floats(0, 100), pack(8, 0, 255)), new float[] {1.0f});

        // ---- out-of-Domain input clamping ----
        emit("t0_input_over", stream(8, ints(2), floats(0, 1), floats(0, 1),
             null, null, pack(8, 0, 255)), new float[] {5.0f});
        emit("t0_input_under", stream(8, ints(2), floats(0, 1), floats(0, 1),
             null, null, pack(8, 0, 255)), new float[] {-5.0f});

        // ============ Type 2 — exponential corners ============
        emit("t2_n_missing", t2(null, null, null), new float[] {0.5f});
        emit("t2_n0", t2(0.0, null, null), new float[] {0.5f});
        emit("t2_n_frac", t2(0.5, null, null), new float[] {0.25f});
        emit("t2_n_neg", t2(-1.0, floats(1, 2), floats(3, 4)),
             new float[] {0.5f});
        emit("t2_c0c1", t2(2.0, floats(0, 10), floats(1, 20)),
             new float[] {0.5f});
        // C0/C1 length mismatch — C0 len 1, C1 len 2
        emit("t2_c0c1_mismatch", t2(1.0, floats(0), floats(1, 2)),
             new float[] {0.5f});
        // negative base with fractional N -> NaN -> /Range clip
        emit("t2_negbase_frac", t2neg(), new float[] {0.5f});
        // input outside [0,1] but inside Domain [-2,2]
        emit("t2_oob_input", t2dom(), new float[] {1.5f});

        // ============ Type 3 — stitching degenerate Bounds ============
        emit("t3_single", t3Single(), new float[] {0.5f});
        emit("t3_at_bound", t3Two(), new float[] {0.5f});
        emit("t3_reversed_encode", t3RevEncode(), new float[] {0.5f});
        emit("t3_zero_width", t3ZeroWidth(), new float[] {0.5f});
        emit("t3_input_at_domain_max", t3Two(), new float[] {1.0f});

        // ============ Type 4 — operator / error corners ============
        emit("t4_add", t4("{ 2 add }"), new float[] {0.25f});
        emit("t4_div0", t4("{ pop 1 0 div }"), new float[] {0.0f});
        emit("t4_idiv0", t4("{ pop 1 0 idiv }"), new float[] {0.0f});
        emit("t4_mod0", t4("{ pop 1 0 mod }"), new float[] {0.0f});
        emit("t4_underflow", t4("{ pop add }"), new float[] {0.0f});
        emit("t4_type_idiv_real", t4("{ pop 7.5 2 idiv }"), new float[] {0.0f});
        emit("t4_unknown_op", t4("{ pop 1 frobnicate }"), new float[] {0.0f});
        emit("t4_unbalanced", t4("{ pop 1 2 add"), new float[] {0.0f});
        emit("t4_nested_if", t4("{ pop 1 { 2 { 3 } if } if }"),
             new float[] {0.0f});
        emit("t4_ifelse", t4("{ pop true { 10 } { 20 } ifelse }"),
             new float[] {0.0f});
        emit("t4_deep_nest", t4("{ pop { { { 5 } if } if } pop 5 }"),
             new float[] {0.0f});
        emit("t4_sqrt_neg", t4("{ pop -1 sqrt }"), new float[] {0.0f});
        emit("t4_empty_prog", t4("{ }"), new float[] {0.5f});
    }

    // ---- Type 2 builders ----
    static COSDictionary t2(Double n, COSArray c0, COSArray c1) {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 2);
        d.setItem(COSName.DOMAIN, floats(0, 1));
        if (n != null) {
            d.setItem(COSName.N, new COSFloat(n.floatValue()));
        }
        if (c0 != null) {
            d.setItem(COSName.C0, c0);
        }
        if (c1 != null) {
            d.setItem(COSName.C1, c1);
        }
        return d;
    }

    static COSDictionary t2neg() {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 2);
        d.setItem(COSName.DOMAIN, floats(-1, 1));
        d.setItem(COSName.N, new COSFloat(0.5f));
        d.setItem(COSName.C0, floats(-1));
        d.setItem(COSName.C1, floats(-2));
        return d;
    }

    static COSDictionary t2dom() {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 2);
        d.setItem(COSName.DOMAIN, floats(-2, 2));
        d.setItem(COSName.N, new COSFloat(2.0f));
        return d;
    }

    // ---- Type 3 builders ----
    static COSDictionary t3Single() {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 3);
        d.setItem(COSName.DOMAIN, floats(0, 1));
        COSArray fns = new COSArray();
        fns.add(t2(1.0, floats(0), floats(1)));
        d.setItem(COSName.FUNCTIONS, fns);
        d.setItem(COSName.BOUNDS, new COSArray());
        d.setItem(COSName.ENCODE, floats(0, 1));
        return d;
    }

    static COSDictionary t3Two() {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 3);
        d.setItem(COSName.DOMAIN, floats(0, 1));
        COSArray fns = new COSArray();
        fns.add(t2(1.0, floats(0), floats(10)));
        fns.add(t2(1.0, floats(10), floats(20)));
        d.setItem(COSName.FUNCTIONS, fns);
        d.setItem(COSName.BOUNDS, floats(0.5));
        d.setItem(COSName.ENCODE, floats(0, 1, 0, 1));
        return d;
    }

    static COSDictionary t3RevEncode() {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 3);
        d.setItem(COSName.DOMAIN, floats(0, 1));
        COSArray fns = new COSArray();
        fns.add(t2(1.0, floats(0), floats(10)));
        fns.add(t2(1.0, floats(0), floats(10)));
        d.setItem(COSName.FUNCTIONS, fns);
        d.setItem(COSName.BOUNDS, floats(0.5));
        d.setItem(COSName.ENCODE, floats(1, 0, 1, 0));
        return d;
    }

    static COSDictionary t3ZeroWidth() {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 3);
        d.setItem(COSName.DOMAIN, floats(0, 1));
        COSArray fns = new COSArray();
        fns.add(t2(1.0, floats(0), floats(10)));
        fns.add(t2(1.0, floats(10), floats(20)));
        fns.add(t2(1.0, floats(20), floats(30)));
        d.setItem(COSName.FUNCTIONS, fns);
        // repeated bound -> a zero-width middle subdomain
        d.setItem(COSName.BOUNDS, floats(0.5, 0.5));
        d.setItem(COSName.ENCODE, floats(0, 1, 0, 1, 0, 1));
        return d;
    }
}
