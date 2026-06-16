import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Differential fuzz probe for the Type 2 (exponential interpolation) and
 * Type 3 (stitching) functions, Apache PDFBox 3.0.7 (wave 1544, agent B).
 *
 * Complements FunctionType2FuzzProbe / FunctionType3FuzzProbe /
 * FunctionType23EdgeProbe with NEW angles those probes do not cover, focused
 * on the interpolation / stitching math and the /C0 /C1 /N (Type2) and
 * /Functions /Bounds /Encode (Type3) array handling:
 *
 *  Type 2:
 *   - /N non-numeric (a name) => getFloat default -1 => x^-1.
 *   - /N huge-negative at x=1 (=> 1), large positive N at x>1.
 *   - non-numeric entry in /C0 or /C1 => toFloatArray cast behaviour.
 *   - multi-component C0/C1 with partial /Range (fewer pairs than components).
 *   - reversed /Domain endpoints WITHOUT input clip (Type2 reads input[0]).
 *   - odd-length /Domain.
 *   - more inputs than dimensions (only input[0] used).
 *   - N=0 with negative C0/C1 (x^0 = 1 multiplier including 0^0).
 *
 *  Type 3:
 *   - four functions, three bounds (correct), each interval probed.
 *   - NaN input (Float.compare last-bound semantics).
 *   - NaN in /Bounds.
 *   - reversed /Encode on the SELECTED multi-function interval.
 *   - /Encode that overshoots into a child whose own /Domain re-clips.
 *   - non-numeric /Encode pair that is NOT reached (lazy access => ok).
 *   - single function with non-numeric /Encode pair 0 => ERR.
 *   - bound == domain.max (zero-width last interval).
 *   - bound == domain.min (zero-width first interval) at x=domain.min.
 *   - subfunction is a Type 4 PostScript child.
 *   - bound is a COSInteger (numeric, not float) => fine.
 *
 * Line grammar (one per case):
 *   CASE &lt;name&gt; create=&lt;ok|ERR&gt; [eval=&lt;ERR | f0 f1 ...&gt;]
 *
 * The pypdfbox sibling
 * (tests/pdmodel/common/function/oracle/test_function_type23_fuzz_wave1544.py)
 * rebuilds the identical COS specs and asserts each line matches.
 */
public final class FunctionType23FuzzProbe {

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

    // ---- Type 2 builder (pass null to omit a key) ----
    static COSDictionary t2(COSArray c0, COSArray c1, Float n, COSArray domain, COSArray range) {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 2);
        if (domain != null) {
            d.setItem(COSName.DOMAIN, domain);
        }
        if (c0 != null) {
            d.setItem(COSName.C0, c0);
        }
        if (c1 != null) {
            d.setItem(COSName.C1, c1);
        }
        if (n != null) {
            d.setItem(COSName.N, new COSFloat(n));
        }
        if (range != null) {
            d.setItem(COSName.RANGE, range);
        }
        return d;
    }

    // ---- simple Type 2 child f(x)=c0 + x*(c1-c0) over [0,1] ----
    static COSDictionary child(double c0, double c1) {
        return t2(floats(c0), floats(c1), 1.0f, floats(0, 1), null);
    }

    static COSArray fns(COSDictionary... children) {
        COSArray a = new COSArray();
        for (COSDictionary c : children) {
            a.add(c);
        }
        return a;
    }

    static COSDictionary t3(COSArray functions, COSArray bounds, COSArray encode, COSArray domain) {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 3);
        if (domain != null) {
            d.setItem(COSName.DOMAIN, domain);
        }
        if (functions != null) {
            d.setItem(COSName.FUNCTIONS, functions);
        }
        if (bounds != null) {
            d.setItem(COSName.BOUNDS, bounds);
        }
        if (encode != null) {
            d.setItem(COSName.ENCODE, encode);
        }
        return d;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ================= Type 2 =================

        // /N non-numeric (a name) => getFloat default -1 => x^-1
        COSDictionary nNonNum = t2(floats(0), floats(1), null, floats(0, 1), null);
        nNonNum.setItem(COSName.N, COSName.getPDFName("bogus"));
        for (float x : new float[] {0.25f, 0.5f, 1f}) {
            emit("t2_n_non_numeric", nNonNum, new float[] {x});
        }

        // /N huge negative at x=1 (1^anything = 1); at x=0.5 underflows to 0
        emit("t2_n_huge_neg_x1", t2(floats(0), floats(1), -1000f, floats(0, 1), null),
             new float[] {1f});
        emit("t2_n_huge_neg_xhalf", t2(floats(0), floats(1), -1000f, floats(0, 1), null),
             new float[] {0.5f});

        // large positive N at x>1 (input not clipped to [0,1] in Type2)
        emit("t2_big_n_x2", t2(floats(0), floats(1), 10f, floats(0, 4), null),
             new float[] {2f});

        // non-numeric entry in /C0 (a name) => upstream toFloatArray cast
        COSArray c0bad = floats(0, 0);
        c0bad.set(1, COSName.getPDFName("X"));
        emit("t2_c0_non_numeric", t2(c0bad, floats(1, 1), 1f, floats(0, 1), null),
             new float[] {0.5f});

        // non-numeric entry in /C1
        COSArray c1bad = floats(1, 1);
        c1bad.set(0, new COSString("oops"));
        emit("t2_c1_non_numeric", t2(floats(0, 0), c1bad, 1f, floats(0, 1), null),
             new float[] {0.5f});

        // multi-component C0/C1 with PARTIAL /Range (1 pair, 2 components)
        emit("t2_partial_range",
             t2(floats(0, 0), floats(100, -100), 1f, floats(0, 1), floats(0, 10)),
             new float[] {0.5f});

        // reversed /Domain endpoints; Type2 eval reads input[0] directly (no clip)
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("t2_rev_domain", t2(floats(0), floats(8), 1f, floats(1, 0), null),
                 new float[] {x});
        }

        // odd-length /Domain [0,1,2] => getRangesForInputs truncates; Type2 still
        // reads input[0] regardless
        emit("t2_odd_domain", t2(floats(0), floats(5), 1f, floats(0, 1, 2), null),
             new float[] {0.4f});

        // more inputs than dimensions (only input[0] used)
        emit("t2_extra_inputs", t2(floats(0), floats(10), 1f, floats(0, 1), null),
             new float[] {0.3f, 0.9f, 0.1f});

        // N=0 with negative C0/C1: x^0 = 1 => y = c0 + 1*(c1-c0) = c1 (incl 0^0)
        for (float x : new float[] {0f, 0.5f}) {
            emit("t2_n0_neg", t2(floats(-5), floats(-2), 0f, floats(0, 1), null),
                 new float[] {x});
        }

        // ================= Type 3 =================

        COSArray dom01 = floats(0, 1);

        // four functions, three bounds (well-formed), probe each interval
        COSArray four = fns(child(0, 10), child(20, 30), child(40, 50), child(60, 70));
        COSArray b3 = floats(0.25, 0.5, 0.75);
        COSArray enc4 = floats(0, 1, 0, 1, 0, 1, 0, 1);
        for (float x : new float[] {0.1f, 0.3f, 0.6f, 0.9f}) {
            emit("t3_four_fns", t3(four, b3, enc4, dom01), new float[] {x});
        }

        // NaN input: clipToRange leaves NaN; partition select uses x<partition[i]
        // (false for NaN) and Float.compare on last bound (NaN > everything)
        emit("t3_nan_input",
             t3(fns(child(0, 10), child(100, 110)), floats(0.5), floats(0, 1, 0, 1), dom01),
             new float[] {Float.NaN});

        // NaN in /Bounds: partition=[0,NaN,1]; x=0.5: p0 0.5<NaN? false in Java
        // (NaN comparisons false) so 0.5>=0 && 0.5<NaN(false) -> not p0; p1 last
        // 0.5>=NaN? false -> skip => partition not found => ERR
        COSArray bnan = floats(0.5);
        bnan.set(0, new COSFloat(Float.NaN));
        emit("t3_nan_bound",
             t3(fns(child(0, 10), child(100, 110)), bnan, floats(0, 1, 0, 1), dom01),
             new float[] {0.5f});

        // reversed /Encode on the SELECTED interval (upper), x=0.75 -> maps
        // [0.5,1] into [1,0] reversed
        emit("t3_rev_encode_selected",
             t3(fns(child(0, 10), child(0, 100)), floats(0.5), floats(0, 1, 1, 0), dom01),
             new float[] {0.75f});

        // /Encode overshoot into child whose own /Domain [0,1] re-clips:
        // pair1 maps [0.5,1]->[0,4]; x=0.9 -> encoded 3.2 -> child clips to 1.0
        emit("t3_encode_overshoot_childclip",
             t3(fns(child(0, 10), child(0, 100)), floats(0.5), floats(0, 1, 0, 4), dom01),
             new float[] {0.9f});

        // non-numeric /Encode pair NOT reached: x in lower interval, bad pair is
        // for the upper subfunction => never accessed => ok
        COSArray encBadUpper = floats(0, 1, 0, 1);
        encBadUpper.set(2, COSName.getPDFName("Q"));
        emit("t3_bad_encode_unreached",
             t3(fns(child(0, 10), child(100, 110)), floats(0.5), encBadUpper, dom01),
             new float[] {0.25f});

        // single function with non-numeric /Encode pair 0 => ERR (pair 0 used)
        COSArray encBad0 = floats(0, 1);
        encBad0.set(0, COSName.getPDFName("Z"));
        emit("t3_single_bad_encode0",
             t3(fns(child(0, 10)), new COSArray(), encBad0, dom01),
             new float[] {0.5f});

        // bound == domain.max => zero-width last interval; x=1 (==domain.max)
        // partition=[0,1,1]; p0=[0,1) 1<1 false skip; p1=[1,1] last, 1>=1 &&
        // Float.compare(1,1)==0 -> fn[1], interpolate over [1,1] -> enc_lo
        emit("t3_bound_eq_dom_max",
             t3(fns(child(0, 10), child(100, 110)), floats(1.0), floats(0, 1, 0, 1), dom01),
             new float[] {1f});

        // bound == domain.min => zero-width first interval; x=0 (==domain.min)
        // partition=[0,0,1]; p0=[0,0) 0<0 false skip; p1=[0,1] last 0>=0 &&
        // 0<1 -> fn[1]
        emit("t3_bound_eq_dom_min",
             t3(fns(child(3, 7), child(0, 1)), floats(0.0), floats(0, 1, 0, 1), dom01),
             new float[] {0f});

        // subfunction is a Type 4 PostScript child {2 mul}
        COSDictionary t4 = new COSDictionary();
        // build via stream
        org.apache.pdfbox.cos.COSStream t4stream =
            new org.apache.pdfbox.cos.COSStream();
        t4stream.setInt(COSName.FUNCTION_TYPE, 4);
        t4stream.setItem(COSName.DOMAIN, floats(0, 1));
        t4stream.setItem(COSName.RANGE, floats(0, 100));
        byte[] ps = "{ 2 mul 10 mul }".getBytes("US-ASCII");
        java.io.OutputStream os = t4stream.createOutputStream();
        os.write(ps);
        os.close();
        COSArray withT4 = new COSArray();
        withT4.add(child(0, 5));
        withT4.add(t4stream);
        emit("t3_type4_child",
             t3(withT4, floats(0.5), floats(0, 1, 0, 1), dom01),
             new float[] {0.75f});

        // bound supplied as a COSInteger (numeric, not COSFloat) => fine
        COSArray bint = new COSArray();
        bint.add(COSInteger.get(0));  // bound 0 with wide domain
        emit("t3_int_bound",
             t3(fns(child(0, 10), child(100, 110)), bint, floats(0, 1, 0, 1), floats(-1, 1)),
             new float[] {0.5f});

        // single function: extra bounds AND extra encode pairs ignored; only
        // encode pair 0 used over whole domain
        emit("t3_single_extra_keys",
             t3(fns(child(0, 20)), floats(0.3, 0.6), floats(0, 1, 0, 1, 0, 1), dom01),
             new float[] {0.5f});
    }
}
