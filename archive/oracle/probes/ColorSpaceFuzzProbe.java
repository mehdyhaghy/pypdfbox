import java.io.OutputStream;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;

/**
 * Differential fuzz probe for {@code PDColorSpace.create(COSBase)} construction
 * leniency, Apache PDFBox 3.0.7 (wave 1512, agent C).
 *
 * Complements the existing {@code ColorSpaceProbe} (which pins toRGB() for
 * well-formed colour spaces) by driving the malformed / missing / mistyped
 * construction surface: name-form unknowns, /Indexed with wrong arity, hival
 * corners, lookup-as-string/stream/missing/short, /Separation & /DeviceN arity
 * and tint-transform corners, /ICCBased /N mismatch and garbage profile bytes,
 * /Cal* & /Lab missing/short WhitePoint, /Pattern with/without base, and a
 * battery of non-array / non-name inputs where an array/name is expected.
 *
 * Deterministic and seed-free: the corpus is a fixed inline list. The pypdfbox
 * sibling rebuilds the identical COS forms and asserts each CASE line matches;
 * intentional pypdfbox robustness divergences (and the ICC CMM divergence) are
 * pinned both-sides there with CHANGES.md citations.
 *
 * Line grammar (one per case):
 *   CASE &lt;name&gt; create=&lt;ERR | NULL | ok class=&lt;C&gt; nc=&lt;n|ERR&gt; init=&lt;a,b,..|ERR&gt; rgb=&lt;r;g;b|ERR|NA&gt;&gt;
 *
 * "create=ERR" means create threw; "create=NULL" means it returned null.
 * "class" is the created colour space's simple class name. "nc" is
 * getNumberOfComponents() (or ERR). "init" is the initial colour's components
 * (%.3f, comma-joined; or ERR). "rgb" is toRGB() of a mid-range sample built
 * from the component count (0.5 per component, or the index 0 for Indexed),
 * formatted as 0-255 ints "r;g;b" (or ERR if it threw, or NA when nc<=0 so no
 * sample is meaningful).
 */
public final class ColorSpaceFuzzProbe {

    static PrintStream out;

    static COSName n(String s) {
        return COSName.getPDFName(s);
    }

    static int clamp255(float v) {
        long r = Math.round((double) v * 255.0);
        if (r < 0) {
            return 0;
        }
        if (r > 255) {
            return 255;
        }
        return (int) r;
    }

    static COSArray arr(COSBase... items) {
        COSArray a = new COSArray();
        for (COSBase b : items) {
            a.add(b);
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

    // A Type-2 exponential tint transform: domain [0 1], C0 / C1 of arbitrary
    // arity, exponent n.
    static COSDictionary type2(float[] c0, float[] c1, float nExp) {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 2);
        d.setItem(COSName.DOMAIN, floats(0, 1));
        COSArray a0 = new COSArray();
        for (float v : c0) {
            a0.add(new COSFloat(v));
        }
        d.setItem(COSName.C0, a0);
        COSArray a1 = new COSArray();
        for (float v : c1) {
            a1.add(new COSFloat(v));
        }
        d.setItem(COSName.C1, a1);
        d.setItem(COSName.N, new COSFloat(nExp));
        return d;
    }

    // A Type-4 PostScript tint with m inputs and the given output arity, body
    // pushes `outArity` copies of the first input (clamped) — enough to be a
    // valid n-out function for arity checks.
    static COSStream type4(int domainPairs, int rangePairs, String body)
            throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 4);
        COSArray dom = new COSArray();
        for (int i = 0; i < domainPairs; i++) {
            dom.add(new COSFloat(0));
            dom.add(new COSFloat(1));
        }
        s.setItem(COSName.DOMAIN, dom);
        COSArray rng = new COSArray();
        for (int i = 0; i < rangePairs; i++) {
            rng.add(new COSFloat(0));
            rng.add(new COSFloat(1));
        }
        s.setItem(COSName.RANGE, rng);
        OutputStream os = s.createOutputStream();
        os.write(body.getBytes("US-ASCII"));
        os.close();
        return s;
    }

    static COSStream iccStream(int nVal, byte[] profileBytes) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.N, nVal);
        OutputStream os = s.createOutputStream();
        if (profileBytes != null) {
            os.write(profileBytes);
        }
        os.close();
        return s;
    }

    static void emit(String name, COSBase base) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        PDColorSpace cs;
        try {
            cs = PDColorSpace.create(base, null);
        } catch (Throwable t) {
            out.println(sb.append("create=ERR").toString());
            return;
        }
        if (cs == null) {
            out.println(sb.append("create=NULL").toString());
            return;
        }
        sb.append("create=ok class=").append(cs.getClass().getSimpleName());
        int nc;
        try {
            nc = cs.getNumberOfComponents();
            sb.append(" nc=").append(nc);
        } catch (Throwable t) {
            out.println(sb.append(" nc=ERR").toString());
            return;
        }
        try {
            float[] init = cs.getInitialColor().getComponents();
            sb.append(" init=");
            for (int i = 0; i < init.length; i++) {
                if (i > 0) {
                    sb.append(',');
                }
                sb.append(String.format(Locale.ROOT, "%.3f", init[i]));
            }
        } catch (Throwable t) {
            sb.append(" init=ERR");
        }
        if (nc <= 0) {
            out.println(sb.append(" rgb=NA").toString());
            return;
        }
        try {
            float[] sample = new float[nc];
            // Indexed wants an integer index; sample index 0 stays in range.
            for (int i = 0; i < nc; i++) {
                sample[i] = 0.5f;
            }
            if (cs instanceof org.apache.pdfbox.pdmodel.graphics.color.PDIndexed) {
                sample[0] = 0.0f;
            }
            float[] rgb = cs.toRGB(sample);
            sb.append(" rgb=").append(clamp255(rgb[0])).append(';')
              .append(clamp255(rgb[1])).append(';').append(clamp255(rgb[2]));
        } catch (Throwable t) {
            sb.append(" rgb=ERR");
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ===== name-form =====
        emit("name_devicegray", COSName.DEVICEGRAY);
        emit("name_devicergb", COSName.DEVICERGB);
        emit("name_devicecmyk", COSName.DEVICECMYK);
        emit("name_short_g", n("G"));
        emit("name_short_rgb", n("RGB"));
        emit("name_short_cmyk", n("CMYK"));
        emit("name_pattern", COSName.PATTERN);
        emit("name_unknown", n("FooBar"));
        emit("name_indexed_bare", COSName.INDEXED);
        emit("name_iccbased_bare", n("ICCBased"));
        emit("name_separation_bare", COSName.SEPARATION);

        // ===== non-array / non-name inputs =====
        emit("null_input", null);
        emit("integer_input", COSInteger.get(7));
        emit("string_input", new COSString("DeviceRGB"));
        emit("float_input", new COSFloat(1.5f));
        emit("cosnull_input", COSNull.NULL);
        emit("empty_array", new COSArray());
        emit("array_head_not_name", arr(COSInteger.get(1), COSName.DEVICERGB));
        emit("array_head_null", arr(COSNull.NULL, COSName.DEVICERGB));
        emit("array_one_name_rgb", arr(COSName.DEVICERGB));
        emit("array_one_name_unknown", arr(n("FooBar")));
        emit("array_unknown_head", arr(n("FooBar"), COSName.DEVICERGB));

        // ===== /Indexed corners =====
        byte[] pal = new byte[] {0, 0, 0, (byte) 255, 0, 0};
        emit("indexed_wellformed",
                arr(COSName.INDEXED, COSName.DEVICERGB, COSInteger.get(1),
                        new COSString(pal)));
        emit("indexed_two_elements",
                arr(COSName.INDEXED, COSName.DEVICERGB));
        emit("indexed_three_elements",
                arr(COSName.INDEXED, COSName.DEVICERGB, COSInteger.get(1)));
        emit("indexed_five_elements",
                arr(COSName.INDEXED, COSName.DEVICERGB, COSInteger.get(1),
                        new COSString(pal), COSInteger.get(99)));
        emit("indexed_hival_negative",
                arr(COSName.INDEXED, COSName.DEVICERGB, COSInteger.get(-5),
                        new COSString(pal)));
        emit("indexed_hival_huge",
                arr(COSName.INDEXED, COSName.DEVICERGB, COSInteger.get(100000),
                        new COSString(pal)));
        emit("indexed_hival_real",
                arr(COSName.INDEXED, COSName.DEVICERGB, new COSFloat(3.7f),
                        new COSString(pal)));
        emit("indexed_hival_string",
                arr(COSName.INDEXED, COSName.DEVICERGB, new COSString("3"),
                        new COSString(pal)));
        emit("indexed_lookup_missing",
                arr(COSName.INDEXED, COSName.DEVICERGB, COSInteger.get(1),
                        COSNull.NULL));
        emit("indexed_lookup_short",
                arr(COSName.INDEXED, COSName.DEVICERGB, COSInteger.get(10),
                        new COSString(pal)));
        emit("indexed_lookup_as_name",
                arr(COSName.INDEXED, COSName.DEVICERGB, COSInteger.get(1),
                        n("notalookup")));
        emit("indexed_base_unknown",
                arr(COSName.INDEXED, n("FooBar"), COSInteger.get(1),
                        new COSString(pal)));
        emit("indexed_base_devicegray",
                arr(COSName.INDEXED, COSName.DEVICEGRAY, COSInteger.get(1),
                        new COSString(new byte[] {0, (byte) 255})));
        // /Indexed with a nested /Indexed base (illegal but lenient).
        COSArray innerIdx = arr(COSName.INDEXED, COSName.DEVICERGB,
                COSInteger.get(1), new COSString(pal));
        emit("indexed_base_nested_indexed",
                arr(COSName.INDEXED, innerIdx, COSInteger.get(1),
                        new COSString(new byte[] {0, 1})));
        byte[] lookupStream = new byte[] {0, 0, 0, 10, 20, 30};
        COSStream lkStream = new COSStream();
        OutputStream lkos = lkStream.createOutputStream();
        lkos.write(lookupStream);
        lkos.close();
        emit("indexed_lookup_as_stream",
                arr(COSName.INDEXED, COSName.DEVICERGB, COSInteger.get(1),
                        lkStream));

        // ===== /Separation corners =====
        emit("separation_wellformed",
                arr(COSName.SEPARATION, n("Spot"), COSName.DEVICECMYK,
                        type2(new float[] {0, 0, 0, 0},
                              new float[] {0, 1, 1, 0}, 1)));
        emit("separation_three_elements",
                arr(COSName.SEPARATION, n("Spot"), COSName.DEVICECMYK));
        emit("separation_two_elements",
                arr(COSName.SEPARATION, n("Spot")));
        emit("separation_alt_unknown",
                arr(COSName.SEPARATION, n("Spot"), n("FooBar"),
                        type2(new float[] {0}, new float[] {1}, 1)));
        emit("separation_tint_missing",
                arr(COSName.SEPARATION, n("Spot"), COSName.DEVICECMYK,
                        COSNull.NULL));
        emit("separation_tint_not_function",
                arr(COSName.SEPARATION, n("Spot"), COSName.DEVICECMYK,
                        n("notafunction")));
        emit("separation_name_all",
                arr(COSName.SEPARATION, n("All"), COSName.DEVICECMYK,
                        type2(new float[] {0, 0, 0, 0},
                              new float[] {1, 1, 1, 1}, 1)));

        // ===== /DeviceN corners =====
        emit("devicen_wellformed",
                arr(COSName.DEVICEN, arr(n("S1"), n("S2")), COSName.DEVICECMYK,
                        type4(2, 4, "{ 0 0 }")));
        emit("devicen_names_empty",
                arr(COSName.DEVICEN, new COSArray(), COSName.DEVICECMYK,
                        type4(0, 4, "{ 0 0 0 0 }")));
        emit("devicen_names_nonnames",
                arr(COSName.DEVICEN, arr(COSInteger.get(1), COSInteger.get(2)),
                        COSName.DEVICECMYK, type4(2, 4, "{ 0 0 }")));
        emit("devicen_names_not_array",
                arr(COSName.DEVICEN, n("S1"), COSName.DEVICECMYK,
                        type4(1, 4, "{ 0 0 0 }")));
        emit("devicen_three_elements",
                arr(COSName.DEVICEN, arr(n("S1"), n("S2")),
                        COSName.DEVICECMYK));
        emit("devicen_alt_unknown",
                arr(COSName.DEVICEN, arr(n("S1")), n("FooBar"),
                        type4(1, 1, "{ }")));
        emit("devicen_tint_missing",
                arr(COSName.DEVICEN, arr(n("S1"), n("S2")), COSName.DEVICECMYK,
                        COSNull.NULL));

        // ===== /ICCBased corners =====
        emit("iccbased_n3_no_profile",
                arr(n("ICCBased"), iccStream(3, null)));
        emit("iccbased_n1",
                arr(n("ICCBased"), iccStream(1, null)));
        emit("iccbased_n4",
                arr(n("ICCBased"), iccStream(4, null)));
        emit("iccbased_n0",
                arr(n("ICCBased"), iccStream(0, null)));
        emit("iccbased_n2",
                arr(n("ICCBased"), iccStream(2, null)));
        emit("iccbased_n5",
                arr(n("ICCBased"), iccStream(5, null)));
        // /N absent entirely (stream with no /N): getN -> 0.
        COSStream iccNoN = new COSStream();
        OutputStream nn = iccNoN.createOutputStream();
        nn.close();
        emit("iccbased_no_n", arr(n("ICCBased"), iccNoN));
        emit("iccbased_garbage_profile",
                arr(n("ICCBased"),
                        iccStream(3, "this is not an icc profile".getBytes("US-ASCII"))));
        emit("iccbased_one_element", arr(n("ICCBased")));
        emit("iccbased_second_not_stream",
                arr(n("ICCBased"), COSName.DEVICERGB));
        // /N mismatched with profile that would imply different arity: probe
        // only structure (no embedded profile), so N drives nc.
        emit("iccbased_n3_with_alternate",
                arr(n("ICCBased"),
                        (COSBase) iccWithAlternate(3, COSName.DEVICERGB)));

        // ===== /CalGray /CalRGB /Lab corners =====
        emit("calgray_wellformed",
                arr(COSName.CALGRAY, calDict(floats(0.95, 1, 1.09), null, 2.2f)));
        emit("calgray_missing_whitepoint",
                arr(COSName.CALGRAY, new COSDictionary()));
        emit("calgray_whitepoint_wrong_len",
                arr(COSName.CALGRAY, calDict(floats(1, 1), null, 1)));
        emit("calgray_whitepoint_zeros",
                arr(COSName.CALGRAY, calDict(floats(0, 0, 0), null, 1)));
        emit("calgray_no_dict", arr(COSName.CALGRAY));

        emit("calrgb_wellformed",
                arr(COSName.CALRGB, calDict(floats(1, 1, 1), floats(1, 1, 1), 0)));
        emit("calrgb_missing_whitepoint",
                arr(COSName.CALRGB, new COSDictionary()));
        emit("calrgb_whitepoint_negative",
                arr(COSName.CALRGB, calDict(floats(-1, -1, -1), null, 0)));
        emit("calrgb_no_dict", arr(COSName.CALRGB));

        emit("lab_wellformed",
                arr(COSName.LAB, labDict(floats(0.9642, 1, 0.8249),
                        floats(-128, 127, -128, 127))));
        emit("lab_missing_whitepoint",
                arr(COSName.LAB, labDict(null, floats(-128, 127, -128, 127))));
        emit("lab_range_wrong_len",
                arr(COSName.LAB, labDict(floats(0.9642, 1, 0.8249),
                        floats(-128, 127))));
        emit("lab_no_range",
                arr(COSName.LAB, labDict(floats(0.9642, 1, 0.8249), null)));
        emit("lab_no_dict", arr(COSName.LAB));

        // ===== /Pattern corners =====
        emit("pattern_name", COSName.PATTERN);
        emit("pattern_array_bare", arr(COSName.PATTERN));
        emit("pattern_array_with_base",
                arr(COSName.PATTERN, COSName.DEVICERGB));
        emit("pattern_array_base_unknown",
                arr(COSName.PATTERN, n("FooBar")));
        emit("pattern_array_base_cmyk",
                arr(COSName.PATTERN, COSName.DEVICECMYK));

        // ===== deeply nested / array-of-array =====
        emit("deeply_nested_array",
                arr(arr(COSName.DEVICERGB)));
        emit("array_device_named",
                arr(COSName.DEVICERGB));
    }

    static COSDictionary calDict(COSArray whitePoint, COSArray gamma, float singleGamma) {
        COSDictionary d = new COSDictionary();
        if (whitePoint != null) {
            d.setItem(COSName.WHITE_POINT, whitePoint);
        }
        if (gamma != null) {
            d.setItem(COSName.GAMMA, gamma);
        } else if (singleGamma != 0) {
            d.setItem(COSName.GAMMA, new COSFloat(singleGamma));
        }
        return d;
    }

    static COSDictionary labDict(COSArray whitePoint, COSArray range) {
        COSDictionary d = new COSDictionary();
        if (whitePoint != null) {
            d.setItem(COSName.WHITE_POINT, whitePoint);
        }
        if (range != null) {
            d.setItem(COSName.RANGE, range);
        }
        return d;
    }

    static COSStream iccWithAlternate(int nVal, COSName alt) throws Exception {
        COSStream s = iccStream(nVal, null);
        s.setItem(COSName.ALTERNATE, alt);
        return s;
    }
}
