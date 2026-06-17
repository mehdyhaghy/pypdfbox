import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;

/**
 * Differential fuzz probe for the {@code PDColorSpace.create} FACTORY DISPATCH
 * and {@code PDResources}-backed name resolution, Apache PDFBox 3.0.7
 * (wave 1564, agent E).
 *
 * Complements ColorSpaceFuzzProbe (wave 1512, which fuzzed the malformed
 * array-form constructor leniency) by isolating the *dispatch* surface:
 *   - device names long form (/DeviceGray /DeviceRGB /DeviceCMYK) -> singleton
 *   - device abbreviations (/G /RGB /CMYK) handed to the bare create() factory
 *     vs. resolved through a PDResources entry (abbreviations are only valid in
 *     inline-image context, so the bare factory's treatment of them is the
 *     interesting dispatch corner)
 *   - /Pattern as a NAME vs. an ARRAY [/Pattern base]
 *   - array-form dispatch to the correct subclass for CalGray/CalRGB/Lab/
 *     ICCBased/Indexed/Separation/DeviceN (verify getClass() + nComponents)
 *   - a NAMED colour space resolved from a PDResources /ColorSpace entry
 *   - an UNKNOWN name (error / fallback) with and without resources
 *   - a name that is ALSO a device name but SHADOWED by a resource entry
 *   - empty array / wrong-arity array / array head not a name
 *   - /I indexed abbreviation in array form
 *
 * Two create() call shapes are exercised per case:
 *   create(base, null)        -> "noRes" projection (no resource resolution)
 *   create(base, resources)   -> "withRes" projection (resource dict supplied)
 * where `resources` always carries a /ColorSpace subdictionary with a couple
 * of named entries (see buildResources()).
 *
 * Deterministic and seed-free. The pypdfbox sibling rebuilds the identical COS
 * forms + resources and asserts each CASE line; documented divergences are
 * pinned both-sides there with CHANGES.md citations.
 *
 * Line grammar (one per case):
 *   CASE &lt;name&gt; noRes=&lt;proj&gt; withRes=&lt;proj&gt;
 * where &lt;proj&gt; is one of:
 *   ERR                         create threw
 *   NULL                        create returned null
 *   class=&lt;C&gt;,nc=&lt;n|ERR&gt;     created class simple name + getNumberOfComponents
 */
public final class ColorSpaceCreateFuzzProbe {

    static PrintStream out;

    static COSName n(String s) {
        return COSName.getPDFName(s);
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

    // Type-2 exponential tint transform of arbitrary C0/C1 arity.
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

    static COSStream iccStream(int nVal) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.N, nVal);
        s.createOutputStream().close();
        return s;
    }

    static COSDictionary calDict(COSArray whitePoint, COSArray gamma) {
        COSDictionary d = new COSDictionary();
        if (whitePoint != null) {
            d.setItem(COSName.WHITE_POINT, whitePoint);
        }
        if (gamma != null) {
            d.setItem(COSName.GAMMA, gamma);
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

    // Resources with a /ColorSpace subdictionary that holds:
    //   /MyRGB  -> [/CalRGB <dict>]      (a named, resolvable array CS)
    //   /MyLab  -> [/Lab <dict>]
    //   /DeviceRGB -> [/CalGray <dict>]  (SHADOWS the device name with CalGray)
    //   /Sep    -> [/Separation Spot /DeviceCMYK <fn>]
    static PDResources buildResources() throws Exception {
        COSDictionary cs = new COSDictionary();
        cs.setItem(n("MyRGB"), arr(COSName.CALRGB,
                calDict(floats(1, 1, 1), floats(1, 1, 1))));
        cs.setItem(n("MyLab"), arr(COSName.LAB,
                labDict(floats(0.9642, 1, 0.8249), floats(-128, 127, -128, 127))));
        // Shadow the DeviceRGB device name with a CalGray entry: a resource
        // entry must win over the device-name fast path in getColorSpace.
        cs.setItem(COSName.DEVICERGB, arr(COSName.CALGRAY,
                calDict(floats(0.95, 1, 1.09), null)));
        cs.setItem(n("Sep"), arr(COSName.SEPARATION, n("Spot"),
                COSName.DEVICECMYK,
                type2(new float[] {0, 0, 0, 0}, new float[] {0, 1, 1, 0}, 1)));
        COSDictionary res = new COSDictionary();
        res.setItem(COSName.COLORSPACE, cs);
        return new PDResources(res);
    }

    static String project(COSBase base, PDResources res) {
        PDColorSpace cs;
        try {
            cs = PDColorSpace.create(base, res);
        } catch (Throwable t) {
            return "ERR";
        }
        if (cs == null) {
            return "NULL";
        }
        StringBuilder sb = new StringBuilder("class=");
        sb.append(cs.getClass().getSimpleName()).append(",nc=");
        try {
            sb.append(cs.getNumberOfComponents());
        } catch (Throwable t) {
            sb.append("ERR");
        }
        return sb.toString();
    }

    static void emit(String name, COSBase base, PDResources res) {
        out.println("CASE " + name + " noRes=" + project(base, null)
                + " withRes=" + project(base, res));
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        PDResources res = buildResources();

        // ===== device names, long form =====
        emit("name_devicegray", COSName.DEVICEGRAY, res);
        emit("name_devicergb", COSName.DEVICERGB, res);
        emit("name_devicecmyk", COSName.DEVICECMYK, res);

        // ===== device abbreviations (inline-image only) =====
        emit("name_abbrev_g", n("G"), res);
        emit("name_abbrev_rgb", n("RGB"), res);
        emit("name_abbrev_cmyk", n("CMYK"), res);

        // ===== /Pattern name vs array =====
        emit("name_pattern", COSName.PATTERN, res);
        emit("array_pattern_bare", arr(COSName.PATTERN), res);
        emit("array_pattern_base_rgb", arr(COSName.PATTERN, COSName.DEVICERGB), res);
        emit("array_pattern_base_cmyk", arr(COSName.PATTERN, COSName.DEVICECMYK), res);

        // ===== array-form dispatch -> correct subclass =====
        emit("array_calgray", arr(COSName.CALGRAY,
                calDict(floats(0.95, 1, 1.09), null)), res);
        emit("array_calrgb", arr(COSName.CALRGB,
                calDict(floats(1, 1, 1), floats(1, 1, 1))), res);
        emit("array_lab", arr(COSName.LAB,
                labDict(floats(0.9642, 1, 0.8249), floats(-128, 127, -128, 127))), res);
        emit("array_iccbased_n3", arr(n("ICCBased"), iccStream(3)), res);
        emit("array_iccbased_n1", arr(n("ICCBased"), iccStream(1)), res);
        emit("array_iccbased_n4", arr(n("ICCBased"), iccStream(4)), res);
        byte[] pal = new byte[] {0, 0, 0, (byte) 255, 0, 0};
        emit("array_indexed", arr(COSName.INDEXED, COSName.DEVICERGB,
                COSInteger.get(1), new COSString(pal)), res);
        emit("array_indexed_abbrev_i", arr(n("I"), COSName.DEVICERGB,
                COSInteger.get(1), new COSString(pal)), res);
        emit("array_separation", arr(COSName.SEPARATION, n("Spot"),
                COSName.DEVICECMYK,
                type2(new float[] {0, 0, 0, 0}, new float[] {0, 1, 1, 0}, 1)), res);
        emit("array_devicen", arr(COSName.DEVICEN, arr(n("S1"), n("S2")),
                COSName.DEVICERGB,
                type2(new float[] {0, 0}, new float[] {1, 1}, 1)), res);

        // ===== array head = device names (full + abbrev) =====
        emit("array_devicegray", arr(COSName.DEVICEGRAY), res);
        emit("array_devicergb", arr(COSName.DEVICERGB), res);
        emit("array_abbrev_g", arr(n("G")), res);
        emit("array_abbrev_rgb", arr(n("RGB")), res);
        emit("array_abbrev_cmyk", arr(n("CMYK")), res);

        // ===== named colour space resolved from /Resources/ColorSpace =====
        emit("resource_myrgb", n("MyRGB"), res);
        emit("resource_mylab", n("MyLab"), res);
        emit("resource_sep", n("Sep"), res);

        // ===== unknown name (error / fallback), with + without resources =====
        emit("name_unknown", n("FooBar"), res);
        emit("name_unknown2", n("NotAColorSpace"), res);

        // ===== device name SHADOWED by a resource entry =====
        // /DeviceRGB is overridden in the resource dict by a CalGray entry, so
        // withRes must resolve to CalGray (the resource wins), while noRes
        // keeps the DeviceRGB singleton.
        emit("shadowed_devicergb", COSName.DEVICERGB, res);

        // ===== empty / wrong-arity / mistyped arrays =====
        emit("empty_array", new COSArray(), res);
        emit("array_head_not_name", arr(COSInteger.get(1), COSName.DEVICERGB), res);
        emit("array_head_null", arr(COSNull.NULL), res);
        emit("array_unknown_head", arr(n("FooBar"), COSName.DEVICERGB), res);
        emit("array_indexed_two", arr(COSName.INDEXED, COSName.DEVICERGB), res);

        // ===== non-array / non-name inputs =====
        emit("integer_input", COSInteger.get(7), res);
        emit("string_input", new COSString("DeviceRGB"), res);
        emit("null_input", null, res);
    }
}
