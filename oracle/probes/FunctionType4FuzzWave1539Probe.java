import java.io.OutputStream;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Differential fuzz probe for the Type 4 PostScript calculator function,
 * Apache PDFBox 3.0.7 (wave 1539, agent A).
 *
 * This is a DIFFERENT/DEEPER angle than the wave-1522 corpus (which is now
 * frozen in tests/.../test_function_type4_fuzz_wave1522.py). Wave 1522 fuzzed
 * the calculator language itself over a fixed valid /Domain [0,1] and /Range
 * [-1000,1000]. This wave fuzzes:
 *
 *   1. MALFORMED FUNCTION DICTS — missing / short / long / empty / odd-length /
 *      non-numeric / reversed /Domain and /Range. These drive
 *      getNumberOfInputParameters / getNumberOfOutputParameters, clip_input,
 *      clip_output, and the under-supply check, none of which wave 1522
 *      exercised (it always handed valid arrays). The probe projects the
 *      declared input/output parameter counts as an extra observable, so a
 *      divergence in COSArray arity handling surfaces directly.
 *
 *   2. OPERATOR / EXECUTION CORNERS not covered by wave 1522: sin/cos at the
 *      cardinal angles, atan full-quadrant sweep, deeply nested if/ifelse,
 *      very deep brace nesting, mixed int/float arithmetic tag preservation,
 *      roll modular-vs-Java semantics at the boundary, bitshift at exactly 32,
 *      cvi/cvr re-tagging chains, comparison-operator tag handling, and
 *      stack-surplus / under-supply against the declared /Range arity.
 *
 * Deterministic and seed-free: the corpus is a fixed inline list. The pypdfbox
 * sibling (tests/pdmodel/common/function/oracle/
 * test_function_type4_fuzz_wave1539.py) rebuilds the identical specs and
 * asserts each line matches.
 *
 * Line grammar (one per case):
 *   CASE &lt;name&gt; create=&lt;ok|ERR&gt; nin=&lt;i|-&gt; nout=&lt;o|-&gt; eval=&lt;ERR | f0 f1 ...&gt;
 *
 * "create=ERR" means PDFunction.create threw. When create succeeds, nin/nout
 * are getNumberOfInputParameters / getNumberOfOutputParameters (or "-" if that
 * accessor itself threw). "eval=ERR" means eval() threw. A float list means
 * eval succeeded; floats are %.6f (or the IEEE tokens NaN / Infinity /
 * -Infinity).
 */
public final class FunctionType4FuzzWave1539Probe {

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

    static COSArray floats(double... vals) {
        COSArray a = new COSArray();
        for (double v : vals) {
            a.add(new COSFloat((float) v));
        }
        return a;
    }

    /** Build a Type 4 stream over an explicit /Domain and /Range COSBase. */
    static COSStream t4(String ps, COSBase domain, COSBase range) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 4);
        if (domain != null) {
            s.setItem(COSName.DOMAIN, domain);
        }
        if (range != null) {
            s.setItem(COSName.RANGE, range);
        }
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
            out.println(sb.append("create=ERR nin=- nout=- eval=-").toString());
            return;
        }
        sb.append("create=ok ");
        String nin;
        try {
            nin = Integer.toString(fn.getNumberOfInputParameters());
        } catch (Throwable t) {
            nin = "-";
        }
        String nout;
        try {
            nout = Integer.toString(fn.getNumberOfOutputParameters());
        } catch (Throwable t) {
            nout = "-";
        }
        sb.append("nin=").append(nin).append(" nout=").append(nout).append(" eval=");
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

    // Valid one-in [0,1] domain, one-out [-1000,1000] range.
    static void e1(String name, String ps, float input) throws Exception {
        emit(name, t4(ps, floats(0, 1), floats(-1000, 1000)), new float[] {input});
    }

    // Two-in [0,1]x[0,1] domain, one-out range.
    static void e2(String name, String ps, float a, float b) throws Exception {
        emit(name, t4(ps, floats(0, 1, 0, 1), floats(-1000, 1000)),
             new float[] {a, b});
    }

    // Arbitrary domain / range bases (may be malformed), single 0.5 input.
    static void edr(String name, String ps, COSBase domain, COSBase range)
            throws Exception {
        emit(name, t4(ps, domain, range), new float[] {0.5f});
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ============ malformed /Range ============
        // /Range absent: getNumberOfOutputParameters == 0; Type 4 eval returns
        // an empty output array (upstream pops nothing). pypdfbox returns the
        // lenient whole-stack instead — pinned as a divergence in the sibling.
        edr("range_missing", "{ pop 5 }", floats(0, 1), null);
        // /Range empty array: size 0 -> nout 0.
        edr("range_empty", "{ pop 5 }", floats(0, 1), new COSArray());
        // /Range odd length (3 entries): size/2 == 1 pair, last entry ignored.
        edr("range_odd_len", "{ pop 5 }", floats(0, 1), floats(-10, 10, 99));
        // /Range single entry: size/2 == 0 -> nout 0.
        edr("range_single", "{ pop 5 }", floats(0, 1), floats(7));
        // /Range two pairs but program leaves one value -> under-supply.
        edr("range_two_pair_under", "{ pop 5 }", floats(0, 1),
            floats(-10, 10, -10, 10));
        // /Range reversed pair (min > max): clip must normalise.
        edr("range_reversed", "{ pop 5000 }", floats(0, 1), floats(10, -10));
        // /Range non-numeric entry: COSArray.toFloatArray hits a non-number.
        COSArray badRange = new COSArray();
        badRange.add(new COSFloat(-10f));
        badRange.add(COSName.getPDFName("bogus"));
        edr("range_non_numeric", "{ pop 5 }", floats(0, 1), badRange);
        // /Range with a COSString entry.
        COSArray strRange = new COSArray();
        strRange.add(new COSFloat(-10f));
        strRange.add(new COSString("x"));
        edr("range_cos_string", "{ pop 5 }", floats(0, 1), strRange);
        // /Range with a boolean entry.
        COSArray boolRange = new COSArray();
        boolRange.add(new COSFloat(-10f));
        boolRange.add(COSBoolean.TRUE);
        edr("range_cos_bool", "{ pop 5 }", floats(0, 1), boolRange);
        // /Range as integers (not floats) — COSInteger entries.
        COSArray intRange = new COSArray();
        intRange.add(COSInteger.get(-10));
        intRange.add(COSInteger.get(10));
        edr("range_cos_int", "{ pop 5000 }", floats(0, 1), intRange);
        // /Range not an array at all (a bare name) — getRangeValues casts.
        edr("range_not_array", "{ pop 5 }", floats(0, 1), COSName.getPDFName("Bad"));

        // ============ malformed /Domain ============
        // /Domain absent: getNumberOfInputParameters == 0; input not clipped.
        edr("domain_missing", "{ 1000 mul }", null, floats(-1000, 1000));
        // /Domain empty: nin 0; input passes through unclipped.
        edr("domain_empty", "{ 1000 mul }", new COSArray(), floats(-1000, 1000));
        // /Domain odd length.
        edr("domain_odd_len", "{ 1000 mul }", floats(0, 1, 9), floats(-1000, 1000));
        // /Domain single entry: nin 0.
        edr("domain_single", "{ 1000 mul }", floats(0), floats(-1000, 1000));
        // /Domain reversed pair: clip normalises, so input 0.5 clips into [0,1].
        edr("domain_reversed", "{ 1000 mul }", floats(1, 0), floats(-1000, 1000));
        // /Domain non-numeric.
        COSArray badDomain = new COSArray();
        badDomain.add(new COSFloat(0f));
        badDomain.add(COSName.getPDFName("bogus"));
        edr("domain_non_numeric", "{ 1000 mul }", badDomain, floats(-1000, 1000));
        // /Domain not an array.
        edr("domain_not_array", "{ 1000 mul }", COSName.getPDFName("Bad"),
            floats(-1000, 1000));
        // Two-pair /Domain but only one input handed to eval.
        edr("domain_two_pair_one_in", "{ 1000 mul }", floats(0, 1, 0, 1),
            floats(-1000, 1000));

        // ============ /Range arity vs program output ============
        // Exactly one output, one /Range pair: clean.
        edr("arity_exact_one", "{ pop 5 }", floats(0, 1), floats(-10, 10));
        // Program leaves surplus; only top N kept.
        edr("arity_surplus_top", "{ 7 8 9 }", floats(0, 1), floats(-100, 100));
        // Program leaves zero outputs but /Range wants one -> under-supply.
        edr("arity_zero_out", "{ pop }", floats(0, 1), floats(-10, 10));
        // Two /Range pairs, program leaves exactly two.
        edr("arity_two_exact", "{ pop 3 4 }", floats(0, 1),
            floats(-10, 10, -10, 10));

        // ============ sin / cos cardinal angles ============
        e1("sin_0", "{ pop 0 sin }", 0.5f);
        e1("sin_30", "{ pop 30 sin }", 0.5f);
        e1("sin_90", "{ pop 90 sin }", 0.5f);
        e1("sin_180", "{ pop 180 sin }", 0.5f);
        e1("sin_270", "{ pop 270 sin }", 0.5f);
        e1("sin_neg90", "{ pop -90 sin }", 0.5f);
        e1("cos_0", "{ pop 0 cos }", 0.5f);
        e1("cos_60", "{ pop 60 cos }", 0.5f);
        e1("cos_90", "{ pop 90 cos }", 0.5f);
        e1("cos_180", "{ pop 180 cos }", 0.5f);
        e1("sin_int_arg", "{ pop 45 sin }", 0.5f);

        // ============ atan full-quadrant sweep ============
        e1("atan_0_1", "{ pop 0 1 atan }", 0.5f);
        e1("atan_1_0", "{ pop 1 0 atan }", 0.5f);
        e1("atan_0_neg1", "{ pop 0 -1 atan }", 0.5f);
        e1("atan_neg1_0", "{ pop -1 0 atan }", 0.5f);
        e1("atan_neg1_1", "{ pop -1 1 atan }", 0.5f);
        e1("atan_real_args", "{ pop 1.0 1.0 atan }", 0.5f);

        // ============ int/float tag preservation through arithmetic ============
        // 3 4 add => Integer 7; then idiv by 2 stays Integer (works).
        e1("tag_add_int_idiv", "{ pop 3 4 add 2 idiv }", 0.5f);
        // 3.0 4 add => Float (mixed) ; idiv then raises.
        e1("tag_mixed_add_idiv", "{ pop 3.0 4 add 2 idiv }", 0.5f);
        // mul stays int when in range.
        e1("tag_mul_int_mod", "{ pop 6 7 mul 5 mod }", 0.5f);
        // sub stays int.
        e1("tag_sub_int_idiv", "{ pop 10 3 sub 2 idiv }", 0.5f);
        // ceiling of int stays int (idiv ok); ceiling of float -> float (idiv err)
        e1("tag_ceil_int", "{ pop 5 ceiling 2 idiv }", 0.5f);
        e1("tag_ceil_float_idiv", "{ pop 5.5 ceiling 2 idiv }", 0.5f);
        // cvr re-tags an int to float, breaking a following idiv.
        e1("tag_cvr_then_idiv", "{ pop 6 cvr 2 idiv }", 0.5f);
        // cvi re-tags a float to int, enabling a following idiv.
        e1("tag_cvi_then_idiv", "{ pop 6.7 cvi 2 idiv }", 0.5f);

        // ============ roll boundary semantics ============
        // j == n: Java pops n entries then rotates by n -> identity.
        e1("roll_j_equals_n", "{ 1 2 3 3 3 roll add add }", 0.5f);
        // j == -n.
        e1("roll_j_neg_n", "{ 1 2 3 3 -3 roll add add }", 0.5f);
        // n == 1, any j -> identity.
        e1("roll_n_one", "{ 5 1 1 roll }", 0.5f);
        // big positive j within |j| <= n.
        e1("roll_4_2", "{ 1 2 3 4 4 2 roll add add add }", 0.5f);

        // ============ bitshift boundary ============
        e1("bitshift_32", "{ pop 1 32 bitshift }", 0.5f);
        e1("bitshift_33", "{ pop 1 33 bitshift }", 0.5f);
        e1("bitshift_31", "{ pop 1 31 bitshift }", 0.5f);
        e1("bitshift_neg31", "{ pop -2147483648 -31 bitshift }", 0.5f);
        e1("bitshift_neg32", "{ pop -2147483648 -32 bitshift }", 0.5f);

        // ============ deep nesting ============
        e1("deep_brace_5", "{ pop { { { { { 5 } } } } } pop 5 }", 0.5f);
        e1("deep_if_chain",
           "{ pop true { true { true { 7 } if } if } if }", 0.5f);
        e1("nested_ifelse",
           "{ pop 0.5 0 gt { 1 0 gt { 11 } { 12 } ifelse } { 13 } ifelse }",
           0.5f);

        // ============ comparison operator tag handling ============
        // int vs float compare via lt/gt (both popReal).
        e1("lt_int_float", "{ pop 3 4.0 lt { 1 } { 0 } ifelse }", 0.5f);
        e1("ge_equal", "{ pop 5 5 ge { 1 } { 0 } ifelse }", 0.5f);
        e1("le_int_float", "{ pop 5 5.0 le { 1 } { 0 } ifelse }", 0.5f);
        // eq of two floats that differ below float32 precision.
        e1("eq_float32_tie", "{ pop 1.0000001 1.0000002 eq { 1 } { 0 } ifelse }",
           0.5f);

        // ============ multi-input programs (two_in domain) ============
        e2("two_in_add", "{ add 100 mul }", 0.3f, 0.7f);
        e2("two_in_sub", "{ sub 100 mul }", 0.7f, 0.2f);
        e2("two_in_clamp_a", "{ pop 1000 mul }", 5.0f, 0.5f);

        // ============ surplus inputs left on stack with /Range ============
        // Two inputs, program consumes none, /Range wants 1 -> only top kept.
        e2("surplus_inputs_top", "{ }", 0.3f, 0.7f);
    }
}
