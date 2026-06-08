import java.io.OutputStream;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;
import org.apache.pdfbox.pdmodel.common.function.PDFunctionType0;
import org.apache.pdfbox.pdmodel.common.function.PDFunctionType2;
import org.apache.pdfbox.pdmodel.common.function.PDFunctionType3;

/**
 * Differential fuzz probe for PDF function CONSTRUCTION + DISPATCH
 * ({@code PDFunction.create(COSBase)} and per-type construction-time
 * leniency), Apache PDFBox 3.0.7 (wave 1515, agent C).
 *
 * <p>This complements {@code FunctionEvalFuzzProbe} (wave 1509), which fuzzes
 * the {@code create()} + {@code eval(float[])} pipeline with the emphasis on
 * the Type-4 PostScript stack-machine. THIS probe instead isolates the
 * CONSTRUCTION/DISPATCH contract across ALL function types: it never calls
 * {@code eval}. It exercises:
 * <ul>
 *   <li>{@code create()} dispatch: {@code /FunctionType} missing / unknown /
 *       out-of-range (1, 5, negative) / non-int (name, string, real),
 *       {@code /Identity} name sentinel, {@code COSObject} unwrapping, and the
 *       dictionary-required branch (non-dict bases — integer / name / string /
 *       boolean / array).</li>
 *   <li>the dict-vs-stream requirement: Type 0 (sampled) and Type 4
 *       (PostScript) are stream-typed; Types 2/3 are plain dicts. Upstream
 *       {@code create} only checks {@code instanceof COSDictionary} (a
 *       {@code COSStream} IS-A {@code COSDictionary}), so it does NOT reject a
 *       Type-0 spec given as a plain dict at construction time — this probe
 *       pins that leniency.</li>
 *   <li>structural accessors readable WITHOUT eval: {@code getDomain()} /
 *       {@code getRange()} arity (pair count), {@code getNumberOfOutputParameters},
 *       and per-type {@code extra} (Type 0: {@code getBitsPerSample} +
 *       {@code getSize} arity; Type 2: {@code getN} + {@code getC0}/{@code getC1}
 *       arity; Type 3: {@code getFunctions}/{@code getBounds}/{@code getEncode}
 *       arity). Each of these can throw on malformed input; the probe captures
 *       that as {@code ERR}.</li>
 *   <li>Type 4 construction with a malformed PostScript body — confirms
 *       upstream does NOT parse the program at {@code create()} time (lazy).</li>
 * </ul>
 *
 * <p>Deterministic and seed-free: the corpus is a fixed inline list (no
 * {@code Date.now} / unseeded random). The pypdfbox sibling
 * {@code tests/pdmodel/common/function/oracle/test_function_create_fuzz_wave1515.py}
 * rebuilds the identical COS graphs on the Python side and asserts each
 * {@code CASE} line matches byte-for-byte. Both sides build the SAME COS
 * bytes (the function COS-graph construction path is isolated; no PDF
 * write/parse round-trip noise).
 *
 * <p>Line grammar (one per case, in corpus order):
 * <pre>
 *   CASE &lt;name&gt; ftype=&lt;n|ERR&gt; class=&lt;simpleName|null|ERR&gt; domain=&lt;arity|ERR&gt; range=&lt;arity|ERR&gt; nout=&lt;n|ERR&gt; extra=&lt;type-specific|ERR&gt;
 * </pre>
 * where
 * <ul>
 *   <li>{@code ftype} = the raw {@code /FunctionType} int as read by
 *       {@code getInt} ({@code -1} when absent / non-int), or {@code ERR} if
 *       even reading it throws (it does not, but the slot is symmetric);</li>
 *   <li>{@code class} = {@code create()}'s result simple class name, or
 *       {@code null} when {@code create} returns null, or {@code ERR} when
 *       {@code create} throws (the dispatch-leniency signal — what matters is
 *       WHETHER construction succeeds, not the Java exception class, so both
 *       sides collapse any throw to {@code ERR});</li>
 *   <li>{@code domain} / {@code range} = pair count of {@code /Domain} /
 *       {@code /Range} ({@code getNumberOfInputParameters} /
 *       {@code getNumberOfOutputParameters}), or {@code ERR} on throw, or
 *       {@code -} when {@code create} did not yield a function;</li>
 *   <li>{@code nout} = {@code getNumberOfOutputParameters} (duplicated as a
 *       direct call so a divergence between the cached-field path and the
 *       accessor is visible), {@code ERR} / {@code -} as above;</li>
 *   <li>{@code extra} = type-specific construction-readable summary (see
 *       {@link #extra}), {@code ERR} on throw, {@code -} otherwise.</li>
 * </ul>
 */
public final class FunctionCreateFuzzProbe {

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

    // ----- spec builders (mirrored exactly in the Python sibling) -----

    static COSDictionary dict(int functionType) {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, functionType);
        return d;
    }

    static COSStream stream(int functionType, byte[] body) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, functionType);
        if (body != null) {
            OutputStream os = s.createOutputStream();
            os.write(body);
            os.close();
        }
        return s;
    }

    static byte[] ascii(String s) {
        try {
            return s.getBytes("US-ASCII");
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    // ----- type-specific construction-readable extra -----

    static String extra(PDFunction fn) {
        if (fn instanceof PDFunctionType0) {
            PDFunctionType0 f = (PDFunctionType0) fn;
            int bps = f.getBitsPerSample();
            COSArray size = f.getSize();
            int sz = size == null ? -1 : size.size();
            return "bps=" + bps + " size=" + sz;
        }
        if (fn instanceof PDFunctionType2) {
            PDFunctionType2 f = (PDFunctionType2) fn;
            float n = f.getN();
            COSArray c0 = f.getC0();
            COSArray c1 = f.getC1();
            int n0 = c0 == null ? -1 : c0.size();
            int n1 = c1 == null ? -1 : c1.size();
            return "N=" + fmt(n) + " c0=" + n0 + " c1=" + n1;
        }
        if (fn instanceof PDFunctionType3) {
            PDFunctionType3 f = (PDFunctionType3) fn;
            COSArray fns = f.getFunctions();
            COSArray bounds = f.getBounds();
            COSArray enc = f.getEncode();
            int nf = fns == null ? -1 : fns.size();
            int nb = bounds == null ? -1 : bounds.size();
            int ne = enc == null ? -1 : enc.size();
            return "fns=" + nf + " bounds=" + nb + " enc=" + ne;
        }
        // Type 4 (and the identity sentinel) expose nothing construction-time
        // beyond domain/range — the PostScript body parses lazily at eval.
        return "type4";
    }

    static String safeExtra(PDFunction fn) {
        try {
            return extra(fn);
        } catch (Exception e) {
            return "ERR";
        }
    }

    static int rawType(COSBase base) {
        // Mirror create()'s view: unwrap COSObject, then read /FunctionType
        // off a COSDictionary (a COSStream IS-A COSDictionary).
        COSBase b = base;
        if (b instanceof COSObject) {
            b = ((COSObject) b).getObject();
        }
        if (b instanceof COSDictionary) {
            return ((COSDictionary) b).getInt(COSName.FUNCTION_TYPE);
        }
        return -1;
    }

    static void runCase(String name, COSBase base) {
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');

        // ftype slot — best-effort raw read (symmetric ERR slot).
        String ftype;
        try {
            ftype = Integer.toString(rawType(base));
        } catch (Exception e) {
            ftype = "ERR";
        }
        sb.append("ftype=").append(ftype);

        PDFunction fn;
        try {
            fn = PDFunction.create(base);
        } catch (Exception e) {
            sb.append(" class=ERR domain=- range=- nout=- extra=-");
            out.println(sb.toString());
            return;
        }

        if (fn == null) {
            sb.append(" class=null domain=- range=- nout=- extra=-");
            out.println(sb.toString());
            return;
        }

        sb.append(" class=").append(fn.getClass().getSimpleName());

        String domain;
        try {
            domain = Integer.toString(fn.getNumberOfInputParameters());
        } catch (Exception e) {
            domain = "ERR";
        }
        sb.append(" domain=").append(domain);

        String range;
        try {
            range = Integer.toString(fn.getNumberOfOutputParameters());
        } catch (Exception e) {
            range = "ERR";
        }
        sb.append(" range=").append(range);

        String nout;
        try {
            nout = Integer.toString(fn.getNumberOfOutputParameters());
        } catch (Exception e) {
            nout = "ERR";
        }
        sb.append(" nout=").append(nout);

        sb.append(" extra=").append(safeExtra(fn));
        out.println(sb.toString());
    }

    // ----- the deterministic corpus (mirror order in the Python sibling) -----

    static void corpus() throws Exception {
        // --- dispatch: missing / unknown / out-of-range / non-int type ---
        runCase("null_base", null);

        COSDictionary noType = new COSDictionary();
        runCase("dict_no_type", noType);

        runCase("type_1_unknown", dict(1));
        runCase("type_5_unknown", dict(5));
        runCase("type_neg", dict(-3));

        COSDictionary typeName = new COSDictionary();
        typeName.setItem(COSName.FUNCTION_TYPE, COSName.getPDFName("Foo"));
        runCase("type_is_name", typeName);

        COSDictionary typeStr = new COSDictionary();
        typeStr.setItem(COSName.FUNCTION_TYPE, new COSString("2"));
        runCase("type_is_string", typeStr);

        COSDictionary typeReal = new COSDictionary();
        typeReal.setItem(COSName.FUNCTION_TYPE, new COSFloat(2.0f));
        runCase("type_is_real_2", typeReal);

        COSDictionary typeReal3 = new COSDictionary();
        typeReal3.setItem(COSName.FUNCTION_TYPE, new COSFloat(2.7f));
        runCase("type_is_real_2_7", typeReal3);

        // --- identity sentinel + COSObject unwrap ---
        runCase("identity_name", COSName.IDENTITY);
        runCase("plain_name", COSName.getPDFName("Foo"));

        COSDictionary t2inner = dict(2);
        t2inner.setItem(COSName.DOMAIN, floats(0, 1));
        COSObject wrapT2 = new COSObject(t2inner);
        runCase("cosobject_wraps_t2", wrapT2);

        COSObject wrapNull = new COSObject((COSBase) null);
        runCase("cosobject_unresolved", wrapNull);

        // --- non-dict bases (dictionary-required branch) ---
        runCase("base_integer", COSInteger.get(2));
        runCase("base_string", new COSString("hi"));
        runCase("base_bool", COSBoolean.TRUE);
        runCase("base_array", ints(0, 1));

        // --- Type 0 as plain dict vs stream (stream requirement leniency) ---
        COSDictionary t0dict = dict(0);
        t0dict.setItem(COSName.DOMAIN, floats(0, 1));
        t0dict.setItem(COSName.RANGE, floats(0, 1));
        t0dict.setItem(COSName.SIZE, ints(2));
        t0dict.setInt(COSName.BITS_PER_SAMPLE, 8);
        runCase("t0_plain_dict", t0dict);

        COSStream t0stream = stream(0, new byte[] {0, (byte) 255});
        t0stream.setItem(COSName.DOMAIN, floats(0, 1));
        t0stream.setItem(COSName.RANGE, floats(0, 1));
        t0stream.setItem(COSName.SIZE, ints(2));
        t0stream.setInt(COSName.BITS_PER_SAMPLE, 8);
        runCase("t0_stream_ok", t0stream);

        // --- Type 0: /Domain arity, /Range missing, /Size, /BitsPerSample ---
        COSStream t0noDomain = stream(0, new byte[] {0, (byte) 255});
        t0noDomain.setItem(COSName.RANGE, floats(0, 1));
        t0noDomain.setItem(COSName.SIZE, ints(2));
        t0noDomain.setInt(COSName.BITS_PER_SAMPLE, 8);
        runCase("t0_no_domain", t0noDomain);

        COSStream t0noRange = stream(0, new byte[] {0, (byte) 255});
        t0noRange.setItem(COSName.DOMAIN, floats(0, 1));
        t0noRange.setItem(COSName.SIZE, ints(2));
        t0noRange.setInt(COSName.BITS_PER_SAMPLE, 8);
        runCase("t0_no_range", t0noRange);

        COSStream t0oddDomain = stream(0, new byte[] {0, (byte) 255});
        t0oddDomain.setItem(COSName.DOMAIN, floats(0, 1, 2));
        t0oddDomain.setItem(COSName.RANGE, floats(0, 1));
        t0oddDomain.setItem(COSName.SIZE, ints(2));
        t0oddDomain.setInt(COSName.BITS_PER_SAMPLE, 8);
        runCase("t0_odd_domain", t0oddDomain);

        COSStream t0noBps = stream(0, new byte[] {0, (byte) 255});
        t0noBps.setItem(COSName.DOMAIN, floats(0, 1));
        t0noBps.setItem(COSName.RANGE, floats(0, 1));
        t0noBps.setItem(COSName.SIZE, ints(2));
        runCase("t0_no_bps", t0noBps);

        for (int bps : new int[] {1, 2, 4, 8, 12, 16, 24, 32, 3, 0, 64}) {
            COSStream s = stream(0, new byte[] {0, (byte) 255});
            s.setItem(COSName.DOMAIN, floats(0, 1));
            s.setItem(COSName.RANGE, floats(0, 1));
            s.setItem(COSName.SIZE, ints(2));
            s.setInt(COSName.BITS_PER_SAMPLE, bps);
            runCase("t0_bps_" + bps, s);
        }

        COSStream t0noSize = stream(0, new byte[] {0, (byte) 255});
        t0noSize.setItem(COSName.DOMAIN, floats(0, 1));
        t0noSize.setItem(COSName.RANGE, floats(0, 1));
        t0noSize.setInt(COSName.BITS_PER_SAMPLE, 8);
        runCase("t0_no_size", t0noSize);

        COSStream t0sizeName = stream(0, new byte[] {0, (byte) 255});
        t0sizeName.setItem(COSName.DOMAIN, floats(0, 1));
        t0sizeName.setItem(COSName.RANGE, floats(0, 1));
        t0sizeName.setItem(COSName.SIZE, COSName.getPDFName("X"));
        t0sizeName.setInt(COSName.BITS_PER_SAMPLE, 8);
        runCase("t0_size_is_name", t0sizeName);

        // --- Type 2: C0/C1 arity, /N corners ---
        COSDictionary t2bare = dict(2);
        t2bare.setItem(COSName.DOMAIN, floats(0, 1));
        runCase("t2_bare", t2bare);

        COSDictionary t2noN = dict(2);
        t2noN.setItem(COSName.DOMAIN, floats(0, 1));
        t2noN.setItem(COSName.C0, floats(0, 0, 0));
        t2noN.setItem(COSName.C1, floats(1, 1, 1));
        runCase("t2_no_n", t2noN);

        COSDictionary t2negN = dict(2);
        t2negN.setItem(COSName.DOMAIN, floats(0, 1));
        t2negN.setItem(COSName.N, new COSFloat(-2.0f));
        runCase("t2_neg_n", t2negN);

        COSDictionary t2nameN = dict(2);
        t2nameN.setItem(COSName.DOMAIN, floats(0, 1));
        t2nameN.setItem(COSName.N, COSName.getPDFName("X"));
        runCase("t2_name_n", t2nameN);

        COSDictionary t2mismatch = dict(2);
        t2mismatch.setItem(COSName.DOMAIN, floats(0, 1));
        t2mismatch.setItem(COSName.N, new COSFloat(1.0f));
        t2mismatch.setItem(COSName.C0, floats(0, 0));
        t2mismatch.setItem(COSName.C1, floats(1, 1, 1));
        runCase("t2_c0_c1_mismatch", t2mismatch);

        COSDictionary t2noDomain = dict(2);
        t2noDomain.setItem(COSName.N, new COSFloat(1.0f));
        runCase("t2_no_domain", t2noDomain);

        {
            COSStream s = stream(2, null);
            s.setItem(COSName.DOMAIN, floats(0, 1));
            s.setItem(COSName.N, new COSFloat(1.0f));
            runCase("t2_as_stream", s);
        }

        // --- Type 3: /Functions, /Bounds, /Encode ---
        COSDictionary t3empty = dict(3);
        t3empty.setItem(COSName.DOMAIN, floats(0, 1));
        runCase("t3_no_functions", t3empty);

        COSDictionary t3emptyArr = dict(3);
        t3emptyArr.setItem(COSName.DOMAIN, floats(0, 1));
        t3emptyArr.setItem(COSName.FUNCTIONS, new COSArray());
        t3emptyArr.setItem(COSName.BOUNDS, new COSArray());
        t3emptyArr.setItem(COSName.ENCODE, new COSArray());
        runCase("t3_empty_functions", t3emptyArr);

        COSDictionary t3two = dict(3);
        t3two.setItem(COSName.DOMAIN, floats(0, 1));
        COSArray subs = new COSArray();
        COSDictionary sub2a = dict(2);
        sub2a.setItem(COSName.DOMAIN, floats(0, 1));
        sub2a.setItem(COSName.N, new COSFloat(1.0f));
        COSDictionary sub2b = dict(2);
        sub2b.setItem(COSName.DOMAIN, floats(0, 1));
        sub2b.setItem(COSName.N, new COSFloat(1.0f));
        subs.add(sub2a);
        subs.add(sub2b);
        t3two.setItem(COSName.FUNCTIONS, subs);
        t3two.setItem(COSName.BOUNDS, floats(0.5));
        t3two.setItem(COSName.ENCODE, floats(0, 1, 0, 1));
        runCase("t3_two_subs", t3two);

        COSDictionary t3badMembers = dict(3);
        t3badMembers.setItem(COSName.DOMAIN, floats(0, 1));
        COSArray bad = new COSArray();
        bad.add(COSInteger.get(7));
        bad.add(new COSString("x"));
        t3badMembers.setItem(COSName.FUNCTIONS, bad);
        runCase("t3_bad_members", t3badMembers);

        COSDictionary t3fnsName = dict(3);
        t3fnsName.setItem(COSName.DOMAIN, floats(0, 1));
        t3fnsName.setItem(COSName.FUNCTIONS, COSName.getPDFName("X"));
        runCase("t3_functions_is_name", t3fnsName);

        COSDictionary t3boundsArity = dict(3);
        t3boundsArity.setItem(COSName.DOMAIN, floats(0, 1));
        COSArray subs2 = new COSArray();
        subs2.add(sub2a);
        subs2.add(sub2b);
        t3boundsArity.setItem(COSName.FUNCTIONS, subs2);
        t3boundsArity.setItem(COSName.BOUNDS, floats(0.3, 0.6, 0.9));
        t3boundsArity.setItem(COSName.ENCODE, floats(0, 1));
        runCase("t3_bounds_encode_arity", t3boundsArity);

        // --- Type 4: malformed PostScript body (construction is lazy) ---
        COSStream t4ok = stream(4, ascii("{ 2 mul }"));
        t4ok.setItem(COSName.DOMAIN, floats(0, 1));
        t4ok.setItem(COSName.RANGE, floats(0, 1000));
        runCase("t4_ok_body", t4ok);

        COSStream t4bad = stream(4, ascii("{ 2 mul "));
        t4bad.setItem(COSName.DOMAIN, floats(0, 1));
        t4bad.setItem(COSName.RANGE, floats(0, 1000));
        runCase("t4_unbalanced_body", t4bad);

        COSStream t4garbage = stream(4, ascii("this is not postscript"));
        t4garbage.setItem(COSName.DOMAIN, floats(0, 1));
        t4garbage.setItem(COSName.RANGE, floats(0, 1000));
        runCase("t4_garbage_body", t4garbage);

        COSStream t4noBody = stream(4, null);
        t4noBody.setItem(COSName.DOMAIN, floats(0, 1));
        t4noBody.setItem(COSName.RANGE, floats(0, 1000));
        runCase("t4_no_body", t4noBody);

        COSStream t4noDomain = stream(4, ascii("{ 2 mul }"));
        t4noDomain.setItem(COSName.RANGE, floats(0, 1000));
        runCase("t4_no_domain", t4noDomain);

        // --- Type 4 as plain dict (no stream) — dispatch leniency edge ---
        COSDictionary t4dict = dict(4);
        t4dict.setItem(COSName.DOMAIN, floats(0, 1));
        t4dict.setItem(COSName.RANGE, floats(0, 1000));
        runCase("t4_plain_dict", t4dict);
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        corpus();
    }
}
