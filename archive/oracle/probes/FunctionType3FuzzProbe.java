import java.io.OutputStream;
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
 * Differential fuzz probe for the Type 3 (stitching) function
 * ({@code org.apache.pdfbox.pdmodel.common.function.PDFunctionType3}),
 * Apache PDFBox 3.0.7 (wave 1523, agent A).
 *
 * Complements FunctionEvalFuzzProbe's handful of Type 3 cases with a dedicated
 * malformed-stitching battery: missing/empty/non-array /Functions, single vs
 * multi function dispatch, /Bounds length wrong (not k-1), non-increasing or
 * out-of-Domain /Bounds, /Encode length wrong (not 2k) or missing pairs,
 * non-numeric /Bounds and /Encode entries, input clamping below Domain[0] /
 * above Domain[1], input exactly on an interior bound (which interval is
 * selected), zero-width subdomain, malformed sub-function, and /Domain corners.
 *
 * Upstream eval (decoded from bytecode): clip x to Domain[0]; build the
 * functionsArray via PDFunction.create on every /Functions entry. If exactly
 * one function, dispatch to it and interpolate over the *whole* Domain with
 * /Encode pair 0 (Bounds ignored). Otherwise build
 * partition[0]=Domain.min, partition[last]=Domain.max with Bounds copied in
 * between, then find i in [0, nPartitions) with x >= partition[i] AND
 * (x < partition[i+1] OR (i is last partition AND x == partition[i+1]));
 * interpolate x over [partition[i], partition[i+1]] into /Encode pair i and
 * dispatch to functionsArray[i]. If no partition matched -> IOException.
 * /Encode access goes through PDRange(encode, i).getMin/getMax which casts
 * encode[2i]/encode[2i+1] to COSNumber -> NPE (=> eval ERR) when /Encode is
 * absent or too short.
 *
 * Deterministic and seed-free. The pypdfbox sibling
 * (tests/pdmodel/common/function/oracle/test_function_type3_fuzz_wave1523.py)
 * rebuilds the identical COS specs and asserts each line matches.
 *
 * Line grammar (one per case):
 *   CASE &lt;name&gt; create=&lt;ok|ERR&gt; [eval=&lt;ERR | f0 f1 ...&gt;]
 */
public final class FunctionType3FuzzProbe {

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

    // ---- a simple Type 2 child: f(x) = c0 + x^1 * (c1 - c0) over Domain [0,1] ----
    static COSDictionary t2(double c0, double c1) {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 2);
        d.setItem(COSName.DOMAIN, floats(0, 1));
        d.setItem(COSName.N, new COSFloat(1.0f));
        d.setItem(COSName.C0, floats(c0));
        d.setItem(COSName.C1, floats(c1));
        return d;
    }

    static COSArray fns(COSDictionary... children) {
        COSArray a = new COSArray();
        for (COSDictionary c : children) {
            a.add(c);
        }
        return a;
    }

    // Build a Type 3 dict; pass null to omit a key. domain may be null.
    static COSDictionary t3(COSArray functions, COSArray bounds, COSArray encode,
                            COSArray domain) {
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

        COSArray dom01 = floats(0, 1);

        // ============ /Functions shape ============
        // missing /Functions -> getFunctions() null -> NPE -> eval ERR
        emit("fns_missing", t3(null, new COSArray(), floats(0, 1), dom01),
             new float[] {0.5f});
        // empty /Functions array -> functionsArray length 0 -> partition not
        // found -> IOException
        emit("fns_empty", t3(new COSArray(), new COSArray(), floats(0, 1), dom01),
             new float[] {0.5f});
        // /Functions not an array (a dict) -> getCOSArray null -> NPE
        COSDictionary notArr = t3(null, new COSArray(), floats(0, 1), dom01);
        notArr.setItem(COSName.FUNCTIONS, t2(0, 1));
        emit("fns_not_array", notArr, new float[] {0.5f});

        // ============ single function (Bounds ignored) ============
        // single fn, empty bounds, encode [0 1]: maps domain->[0,1] then f=x
        emit("single_basic",
             t3(fns(t2(0, 1)), new COSArray(), floats(0, 1), dom01),
             new float[] {0.5f});
        // single fn but a NON-empty bounds present -> upstream single-fn path
        // ignores it entirely (no "too many partitions" error)
        emit("single_with_bound",
             t3(fns(t2(0, 1)), floats(0.5), floats(0, 1), dom01),
             new float[] {0.5f});
        // single fn, encode reversed [1 0] -> input mapped 0.5 -> 0.5 (sym)
        emit("single_rev_encode",
             t3(fns(t2(0, 10)), new COSArray(), floats(1, 0), dom01),
             new float[] {0.25f});
        // single fn, /Encode missing -> getEncodeForParameter -> NPE -> ERR
        emit("single_encode_missing",
             t3(fns(t2(0, 1)), new COSArray(), null, dom01),
             new float[] {0.5f});
        // single fn, /Encode too short (length 1) -> getMax reads encode[1]
        // -> null -> NPE -> ERR
        emit("single_encode_short",
             t3(fns(t2(0, 1)), new COSArray(), floats(0), dom01),
             new float[] {0.5f});

        // ============ two functions, well-formed ============
        COSDictionary two = t3(fns(t2(0, 10), t2(100, 110)), floats(0.5),
                               floats(0, 1, 0, 1), dom01);
        emit("two_low", two, new float[] {0.25f});
        emit("two_high", t3(fns(t2(0, 10), t2(100, 110)), floats(0.5),
             floats(0, 1, 0, 1), dom01), new float[] {0.75f});
        // input exactly on the interior bound -> goes to the UPPER interval
        emit("two_on_bound", t3(fns(t2(0, 10), t2(100, 110)), floats(0.5),
             floats(0, 1, 0, 1), dom01), new float[] {0.5f});
        // input at Domain max (last partition, x == partition[last]) -> upper
        emit("two_at_dom_max", t3(fns(t2(0, 10), t2(100, 110)), floats(0.5),
             floats(0, 1, 0, 1), dom01), new float[] {1.0f});
        // input at Domain min
        emit("two_at_dom_min", t3(fns(t2(0, 10), t2(100, 110)), floats(0.5),
             floats(0, 1, 0, 1), dom01), new float[] {0.0f});

        // ============ input clamping ============
        emit("clamp_over", t3(fns(t2(0, 10), t2(100, 110)), floats(0.5),
             floats(0, 1, 0, 1), dom01), new float[] {5.0f});
        emit("clamp_under", t3(fns(t2(0, 10), t2(100, 110)), floats(0.5),
             floats(0, 1, 0, 1), dom01), new float[] {-5.0f});

        // ============ /Bounds length wrong ============
        // 2 functions but EMPTY bounds (need k-1=1). partition = [0, 1],
        // 1 partition -> always picks fn[0]; encode pair 0 used.
        emit("bounds_too_few",
             t3(fns(t2(0, 10), t2(100, 110)), new COSArray(),
                floats(0, 1, 0, 1), dom01),
             new float[] {0.75f});
        // 2 functions but 2 bounds (need 1). partition = [0, .3, .6, 1] ->
        // 3 partitions but only fns[0],fns[1]; x=0.75 falls in partition 2 ->
        // functionsArray[2] -> null -> NPE -> ERR
        emit("bounds_too_many",
             t3(fns(t2(0, 10), t2(100, 110)), floats(0.3, 0.6),
                floats(0, 1, 0, 1, 0, 1), dom01),
             new float[] {0.75f});
        // 3 functions, 2 bounds (correct), x in the middle interval
        emit("three_mid",
             t3(fns(t2(0, 10), t2(50, 60), t2(100, 110)), floats(0.33, 0.66),
                floats(0, 1, 0, 1, 0, 1), dom01),
             new float[] {0.5f});

        // ============ /Bounds non-increasing / out of Domain ============
        // reversed bounds [0.7, 0.3]: partition = [0, .7, .3, 1]. x=0.5:
        // p0=[0,.7) matches (0.5>=0 && 0.5<.7) -> fn[0]
        emit("bounds_reversed",
             t3(fns(t2(0, 10), t2(50, 60), t2(100, 110)), floats(0.7, 0.3),
                floats(0, 1, 0, 1, 0, 1), dom01),
             new float[] {0.5f});
        // bound below Domain.min: [-0.5] with domain [0,1]. partition=[0,-.5,1]
        // x=0.5: p0=[0,-.5) -> 0.5<-.5 false -> skip; p1=[-.5,1] last,
        // 0.5>=-.5 && 0.5<1 -> fn[1]
        emit("bound_below_domain",
             t3(fns(t2(0, 10), t2(100, 110)), floats(-0.5),
                floats(0, 1, 0, 1), dom01),
             new float[] {0.5f});
        // bound above Domain.max: [1.5] domain [0,1]. partition=[0,1.5,1]
        // x=0.5: p0=[0,1.5) -> 0.5>=0 && 0.5<1.5 -> fn[0]
        emit("bound_above_domain",
             t3(fns(t2(0, 10), t2(100, 110)), floats(1.5),
                floats(0, 1, 0, 1), dom01),
             new float[] {0.5f});

        // ============ zero-width subdomain ============
        // repeated bound 0.5,0.5: partition=[0,.5,.5,1]. middle interval is
        // zero width -> interpolate over [.5,.5] uses PDFBox interpolate which
        // divides by (xmax-xmin)=0 -> NaN; but x=0.5 picks which partition?
        // p0=[0,.5) 0.5<.5 false skip; p1=[.5,.5) 0.5<.5 false, not last skip;
        // p2=[.5,1] last 0.5>=.5 && 0.5<1 -> fn[2]
        emit("zero_width_mid",
             t3(fns(t2(0, 10), t2(50, 60), t2(100, 110)), floats(0.5, 0.5),
                floats(0, 1, 0, 1, 0, 1), dom01),
             new float[] {0.5f});

        // ============ /Encode length wrong / non-numeric ============
        // 2 fns, encode too short (only first pair). x=0.75 -> fn[1] needs
        // encode[2],encode[3] -> null -> NPE -> ERR
        emit("encode_short_multi",
             t3(fns(t2(0, 10), t2(100, 110)), floats(0.5), floats(0, 1), dom01),
             new float[] {0.75f});
        // 2 fns, encode oversized (3 pairs) -> extra pair ignored -> ok
        emit("encode_oversized",
             t3(fns(t2(0, 10), t2(100, 110)), floats(0.5),
                floats(0, 1, 0, 1, 0, 1), dom01),
             new float[] {0.75f});
        // non-numeric /Encode entry (a name) -> PDRange.getMin cast COSNumber
        // -> CCE -> ERR
        COSArray badEnc = floats(0, 1, 0, 1);
        badEnc.set(2, COSName.getPDFName("X"));
        emit("encode_non_numeric",
             t3(fns(t2(0, 10), t2(100, 110)), floats(0.5), badEnc, dom01),
             new float[] {0.75f});

        // ============ non-numeric /Bounds entry ============
        // a name in /Bounds -> toFloatArray maps it to 0.0. With domain [0,1]:
        // bound=0.0 -> partition=[0,0,1]; x=0.5: p0=[0,0) skip; p1=[0,1] last
        // -> fn[1]
        COSArray badB = floats(0.5);
        badB.set(0, new COSString("oops"));
        emit("bounds_non_numeric",
             t3(fns(t2(0, 10), t2(100, 110)), badB,
                floats(0, 1, 0, 1), dom01),
             new float[] {0.5f});

        // ============ malformed sub-function ============
        // a /Functions entry that is itself a bad function (FunctionType 99) ->
        // create() inside eval throws -> eval ERR
        COSDictionary badChild = new COSDictionary();
        badChild.setInt(COSName.FUNCTION_TYPE, 99);
        COSArray withBad = new COSArray();
        withBad.add(t2(0, 10));
        withBad.add(badChild);
        emit("subfn_malformed",
             t3(withBad, floats(0.5), floats(0, 1, 0, 1), dom01),
             new float[] {0.75f});
        // a /Functions entry that is not a dict at all (an integer) ->
        // create(COSInteger) -> not a dictionary -> IOException -> eval ERR
        COSArray withInt = new COSArray();
        withInt.add(t2(0, 10));
        withInt.add(COSInteger.get(7));
        emit("subfn_not_dict",
             t3(withInt, floats(0.5), floats(0, 1, 0, 1), dom01),
             new float[] {0.75f});

        // ============ /Domain malformed ============
        // /Domain missing -> getDomainForInput(0) -> NPE -> eval ERR
        emit("domain_missing",
             t3(fns(t2(0, 10), t2(100, 110)), floats(0.5),
                floats(0, 1, 0, 1), null),
             new float[] {0.5f});
        // /Domain reversed [1, 0]: clipToRange normalises so x clips into [0,1]
        emit("domain_reversed",
             t3(fns(t2(0, 10), t2(100, 110)), floats(0.5),
                floats(0, 1, 0, 1), floats(1, 0)),
             new float[] {0.5f});
        // wide /Domain [-10, 10], bound 0 -> partition=[-10,0,10]; x=5 -> fn[1]
        emit("domain_wide",
             t3(fns(t2(0, 10), t2(100, 110)), floats(0),
                floats(0, 1, 0, 1), floats(-10, 10)),
             new float[] {5.0f});

        // ============ encode interpolation at interval edges ============
        // x exactly at sub_lo of upper interval (the bound): mapped to enc_lo
        // of pair 1
        emit("edge_at_lower",
             t3(fns(t2(0, 10), t2(0, 100)), floats(0.5),
                floats(0, 1, 0, 1), dom01),
             new float[] {0.5f});
        // encode pair maps to a wide range [0, 4]; child Domain [0,1] clips the
        // encoded input back to 1.0 before the child sees it
        emit("edge_encode_overshoot",
             t3(fns(t2(0, 10), t2(0, 100)), floats(0.5),
                floats(0, 1, 0, 4), dom01),
             new float[] {0.75f});
    }
}
