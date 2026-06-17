import java.io.OutputStream;
import java.io.PrintStream;
import java.util.Map;
import java.util.TreeSet;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceN;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceNAttributes;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceNProcess;
import org.apache.pdfbox.pdmodel.graphics.color.PDSeparation;

/**
 * Live oracle DIFFERENTIAL-FUZZ probe for the {@link PDSeparation} and
 * {@link PDDeviceN} (and {@link PDDeviceNAttributes} / {@link PDDeviceNProcess})
 * surfaces (PDF 32000-1 &sect;8.6.6.4 Separation, &sect;8.6.6.5 DeviceN /
 * NChannel). Constructs ~35 malformed / edge-case colour-space arrays from
 * in-memory COS objects and projects every accessor the Python port mirrors,
 * so the Python test can pin BOTH sides against PDFBox 3.0.7 behaviour.
 *
 * Fuzz angles (intentionally NOT covered by the sibling probes
 * SeparationAllNoneProbe / SeparationTintCacheProbe / SeparationDecodeImageProbe
 * / DeviceNAttrProbe / DeviceNAttrToStringProbe / DeviceNHexachromeProbe):
 *
 *   - Separation colorant name as name / string / missing (short array).
 *   - alternate colour space valid / missing / wrong-type (a name that is not
 *     a colour space).
 *   - tint transform as function dict / function stream / missing / wrong-arity
 *     (Range too short for the alternate's component count).
 *   - DeviceN colorant-names array empty / single / many / containing non-name
 *     entries.
 *   - /Attributes missing / non-dict, /Colorants sub-dict, /Process with
 *     /ColorSpace + /Components, mismatched component counts.
 *
 * Every projection is wrapped so an exception surfaces as a stable {@code ERR}
 * token instead of crashing the whole probe — this lets the Python side pin
 * "PDFBox raises here" as honest divergence where pypdfbox is lenient.
 *
 * Line grammar (Python reproduces / classifies verbatim):
 *
 *   SEP &lt;tag&gt; colorant=&lt;v&gt; ncomp=&lt;n&gt; initial=&lt;c0,..&gt; hasalt=&lt;b&gt; hastint=&lt;b&gt;
 *   SEP_TORGB &lt;tag&gt; &lt;t&gt; -&gt; &lt;r&gt; &lt;g&gt; &lt;b&gt;        (or "-&gt; NONE" / "-&gt; ERR")
 *   DN &lt;tag&gt; colorants=&lt;c0,c1,..&gt; ncomp=&lt;n&gt; initial=&lt;..&gt; hasalt=&lt;b&gt; hastint=&lt;b&gt;
 *      hasattr=&lt;b&gt; nchannel=&lt;b&gt; subtype=&lt;s&gt;
 *   DN_PROCESS &lt;tag&gt; cs=&lt;name|NONE&gt; comps=&lt;c0,..&gt;
 *   DN_COLORANTS &lt;tag&gt; keys=&lt;k0,..&gt;
 *   DN_TORGB &lt;tag&gt; &lt;c0&gt;,&lt;c1&gt;,.. -&gt; &lt;r&gt; &lt;g&gt; &lt;b&gt;   (or "-&gt; NONE" / "-&gt; ERR")
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; SeparationDeviceNFuzzProbe
 */
public final class SeparationDeviceNFuzzProbe {

    static PrintStream out;

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

    static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Integer.toString((int) v);
        }
        return Float.toString(v);
    }

    static String floats(float[] a) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < a.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(fmt(a[i]));
        }
        return sb.toString();
    }

    // ---------- function builders ----------

    static COSDictionary type2(float[] c0, float[] c1, float n) {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 2);
        COSArray domain = new COSArray();
        domain.add(new COSFloat(0));
        domain.add(new COSFloat(1));
        d.setItem(COSName.DOMAIN, domain);
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
        d.setItem(COSName.N, new COSFloat(n));
        return d;
    }

    static COSStream type4(float[] domain, float[] range, String ps)
            throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 4);
        COSArray dom = new COSArray();
        for (float v : domain) {
            dom.add(new COSFloat(v));
        }
        s.setItem(COSName.DOMAIN, dom);
        COSArray rng = new COSArray();
        for (float v : range) {
            rng.add(new COSFloat(v));
        }
        s.setItem(COSName.RANGE, rng);
        OutputStream os = s.createOutputStream();
        os.write(ps.getBytes("US-ASCII"));
        os.close();
        return s;
    }

    // ---------- Separation projection ----------

    static void describeSep(String tag, COSArray arr) {
        StringBuilder sb = new StringBuilder("SEP ").append(tag);
        try {
            PDSeparation sep = new PDSeparation(arr);
            String colorant;
            try {
                colorant = String.valueOf(sep.getColorantName());
            } catch (Exception e) {
                colorant = "ERR";
            }
            sb.append(" colorant=").append(colorant);
            sb.append(" ncomp=").append(sep.getNumberOfComponents());
            try {
                PDColor init = sep.getInitialColor();
                sb.append(" initial=").append(floats(init.getComponents()));
            } catch (Exception e) {
                sb.append(" initial=ERR");
            }
            boolean hasAlt;
            try {
                hasAlt = sep.getAlternateColorSpace() != null;
            } catch (Exception e) {
                hasAlt = false;
            }
            sb.append(" hasalt=").append(hasAlt);
            // NOTE: PDFBox 3.0.7 PDSeparation exposes NO public
            // getTintTransform() getter (the tint transform is resolved
            // eagerly in the constructor and kept private), so the probe
            // cannot project a "hastint" flag here — the Python side pins
            // has_tint_transform() as a documented pypdfbox enrichment.
        } catch (Exception ctor) {
            sb.append(" CTOR_ERR");
        }
        out.println(sb.toString());
    }

    static void sepToRgb(String tag, COSArray arr, float t) {
        StringBuilder sb = new StringBuilder("SEP_TORGB ").append(tag)
                .append(' ').append(fmt(t)).append(" -> ");
        try {
            PDSeparation sep = new PDSeparation(arr);
            float[] rgb = sep.toRGB(new float[] {t});
            if (rgb == null) {
                sb.append("NONE");
            } else {
                sb.append(clamp255(rgb[0])).append(' ')
                  .append(clamp255(rgb[1])).append(' ')
                  .append(clamp255(rgb[2]));
            }
        } catch (Exception e) {
            sb.append("ERR");
        }
        out.println(sb.toString());
    }

    static COSArray sepArray(COSName colorantName, COSString colorantStr,
            boolean withColorant, Object alternate, Object tint) {
        COSArray arr = new COSArray();
        arr.add(COSName.SEPARATION);
        if (withColorant) {
            if (colorantName != null) {
                arr.add(colorantName);
            } else {
                arr.add(colorantStr);
            }
        }
        if (alternate != null) {
            arr.add((org.apache.pdfbox.cos.COSBase) alternate);
            if (tint != null) {
                arr.add((org.apache.pdfbox.cos.COSBase) tint);
            }
        }
        return arr;
    }

    // ---------- DeviceN projection ----------

    static void describeDn(String tag, COSArray arr) {
        StringBuilder sb = new StringBuilder("DN ").append(tag);
        try {
            PDDeviceN dn = new PDDeviceN(arr);
            String colorants;
            try {
                StringBuilder cb = new StringBuilder();
                java.util.List<String> names = dn.getColorantNames();
                for (int i = 0; i < names.size(); i++) {
                    if (i > 0) {
                        cb.append(',');
                    }
                    cb.append(names.get(i));
                }
                colorants = cb.toString();
            } catch (Exception e) {
                colorants = "ERR";
            }
            sb.append(" colorants=").append(colorants);
            try {
                sb.append(" ncomp=").append(dn.getNumberOfComponents());
            } catch (Exception e) {
                sb.append(" ncomp=ERR");
            }
            try {
                sb.append(" initial=")
                  .append(floats(dn.getInitialColor().getComponents()));
            } catch (Exception e) {
                sb.append(" initial=ERR");
            }
            boolean hasAlt;
            try {
                hasAlt = dn.getAlternateColorSpace() != null;
            } catch (Exception e) {
                hasAlt = false;
            }
            sb.append(" hasalt=").append(hasAlt);
            boolean hasTint;
            try {
                hasTint = dn.getTintTransform() != null;
            } catch (Exception e) {
                hasTint = false;
            }
            sb.append(" hastint=").append(hasTint);
            boolean hasAttr;
            try {
                hasAttr = dn.getAttributes() != null;
            } catch (Exception e) {
                hasAttr = false;
            }
            sb.append(" hasattr=").append(hasAttr);
            boolean nchannel;
            try {
                nchannel = dn.isNChannel();
            } catch (Exception e) {
                nchannel = false;
            }
            sb.append(" nchannel=").append(nchannel);
        } catch (Exception ctor) {
            sb.append(" CTOR_ERR");
        }
        out.println(sb.toString());
    }

    static void describeDnProcess(String tag, COSArray arr) {
        StringBuilder sb = new StringBuilder("DN_PROCESS ").append(tag);
        try {
            PDDeviceN dn = new PDDeviceN(arr);
            PDDeviceNAttributes attrs = dn.getAttributes();
            if (attrs == null) {
                out.println(sb.append(" cs=NONE comps=").toString());
                return;
            }
            PDDeviceNProcess process = attrs.getProcess();
            if (process == null) {
                out.println(sb.append(" cs=NONE comps=").toString());
                return;
            }
            PDColorSpace cs = process.getColorSpace();
            sb.append(" cs=").append(cs == null ? "NONE" : cs.getName());
            StringBuilder cb = new StringBuilder();
            java.util.List<String> comps = process.getComponents();
            for (int i = 0; i < comps.size(); i++) {
                if (i > 0) {
                    cb.append(',');
                }
                cb.append(comps.get(i));
            }
            sb.append(" comps=").append(cb.toString());
        } catch (Exception e) {
            sb.append(" ERR");
        }
        out.println(sb.toString());
    }

    static void describeDnColorants(String tag, COSArray arr) {
        StringBuilder sb = new StringBuilder("DN_COLORANTS ").append(tag);
        try {
            PDDeviceN dn = new PDDeviceN(arr);
            PDDeviceNAttributes attrs = dn.getAttributes();
            if (attrs == null) {
                out.println(sb.append(" keys=").toString());
                return;
            }
            Map<String, PDSeparation> colorants = attrs.getColorants();
            TreeSet<String> keys = new TreeSet<>(colorants.keySet());
            StringBuilder kb = new StringBuilder();
            boolean first = true;
            for (String k : keys) {
                if (!first) {
                    kb.append(',');
                }
                kb.append(k);
                first = false;
            }
            sb.append(" keys=").append(kb.toString());
        } catch (Exception e) {
            sb.append(" ERR");
        }
        out.println(sb.toString());
    }

    static void dnToRgb(String tag, COSArray arr, float[] comps) {
        StringBuilder sb = new StringBuilder("DN_TORGB ").append(tag)
                .append(' ').append(floats(comps)).append(" -> ");
        try {
            PDDeviceN dn = new PDDeviceN(arr);
            float[] rgb = dn.toRGB(comps);
            if (rgb == null) {
                sb.append("NONE");
            } else {
                sb.append(clamp255(rgb[0])).append(' ')
                  .append(clamp255(rgb[1])).append(' ')
                  .append(clamp255(rgb[2]));
            }
        } catch (Exception e) {
            sb.append("ERR");
        }
        out.println(sb.toString());
    }

    static COSArray namesArray(String... names) {
        COSArray a = new COSArray();
        for (String n : names) {
            a.add(COSName.getPDFName(n));
        }
        return a;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ====================================================================
        // SEPARATION fuzz cases
        // ====================================================================

        // gray tint: t -> 1-t  (exact, no CMM).
        COSStream grayTint = type4(new float[] {0, 1}, new float[] {0, 1},
                "{ 1 exch sub }");
        COSDictionary grayTint2 = type2(new float[] {1}, new float[] {0}, 1.0f);

        // (1) colorant as name, gray alternate, type-4 tint  -> well-formed.
        describeSep("name_gray",
                sepArray(COSName.getPDFName("Spot"), null, true,
                        COSName.DEVICEGRAY, grayTint));
        for (float t : new float[] {0.0f, 0.5f, 1.0f}) {
            sepToRgb("name_gray",
                    sepArray(COSName.getPDFName("Spot"), null, true,
                            COSName.DEVICEGRAY, grayTint), t);
        }

        // (2) colorant as name, gray alternate, type-2 tint dict.
        describeSep("name_gray_t2",
                sepArray(COSName.getPDFName("Spot"), null, true,
                        COSName.DEVICEGRAY, grayTint2));
        for (float t : new float[] {0.0f, 0.5f, 1.0f}) {
            sepToRgb("name_gray_t2",
                    sepArray(COSName.getPDFName("Spot"), null, true,
                            COSName.DEVICEGRAY, grayTint2), t);
        }

        // (3) colorant as STRING (not a name) — getColorantName casts to
        //     COSName and throws in PDFBox.
        describeSep("str_colorant",
                sepArray(null, new COSString("SpotStr"), true,
                        COSName.DEVICEGRAY, grayTint));

        // (4) colorant MISSING (array = [/Separation]).
        describeSep("missing_colorant",
                sepArray(null, null, false, null, null));

        // (5) alternate MISSING (array = [/Separation /Spot]).
        describeSep("missing_alt",
                sepArray(COSName.getPDFName("Spot"), null, true, null, null));
        sepToRgb("missing_alt",
                sepArray(COSName.getPDFName("Spot"), null, true, null, null),
                0.5f);

        // (6) alternate WRONG-TYPE — a bare name that is not a colour space.
        describeSep("wrong_alt",
                sepArray(COSName.getPDFName("Spot"), null, true,
                        COSName.getPDFName("Bogus"), grayTint));
        sepToRgb("wrong_alt",
                sepArray(COSName.getPDFName("Spot"), null, true,
                        COSName.getPDFName("Bogus"), grayTint), 0.5f);

        // (7) tint MISSING ([/Separation /Spot /DeviceGray]).
        describeSep("missing_tint",
                sepArray(COSName.getPDFName("Spot"), null, true,
                        COSName.DEVICEGRAY, null));
        sepToRgb("missing_tint",
                sepArray(COSName.getPDFName("Spot"), null, true,
                        COSName.DEVICEGRAY, null), 0.5f);

        // (8) tint WRONG-ARITY — Range declares 1 output but alternate
        //     DeviceCMYK needs 4. Probe how each side reacts at toRGB.
        COSStream badArity = type4(new float[] {0, 1}, new float[] {0, 1},
                "{ }");
        describeSep("bad_arity",
                sepArray(COSName.getPDFName("Spot"), null, true,
                        COSName.DEVICECMYK, badArity));
        sepToRgb("bad_arity",
                sepArray(COSName.getPDFName("Spot"), null, true,
                        COSName.DEVICECMYK, badArity), 0.5f);

        // (9) /All colorant, gray alternate.
        describeSep("all_gray",
                sepArray(COSName.getPDFName("All"), null, true,
                        COSName.DEVICEGRAY, grayTint));

        // (10) /None colorant, gray alternate.
        describeSep("none_gray",
                sepArray(COSName.getPDFName("None"), null, true,
                        COSName.DEVICEGRAY, grayTint));

        // ====================================================================
        // DEVICEN fuzz cases
        // ====================================================================

        // (11) empty colorant-names array.
        describeDn("empty",
                deviceNArray(namesArray(), COSName.DEVICEGRAY, grayTint, null));

        // (12) single colorant, gray alternate, type-4 tint.
        describeDn("single",
                deviceNArray(namesArray("S1"), COSName.DEVICEGRAY, grayTint,
                        null));
        dnToRgb("single",
                deviceNArray(namesArray("S1"), COSName.DEVICEGRAY, grayTint,
                        null), new float[] {0.0f});
        dnToRgb("single",
                deviceNArray(namesArray("S1"), COSName.DEVICEGRAY, grayTint,
                        null), new float[] {0.5f});
        dnToRgb("single",
                deviceNArray(namesArray("S1"), COSName.DEVICEGRAY, grayTint,
                        null), new float[] {1.0f});

        // (13) two colorants, gray alternate, type-4 tint (a,b)->a (1 output).
        COSStream tint2to1 = type4(new float[] {0, 1, 0, 1},
                new float[] {0, 1}, "{ pop }");
        describeDn("two",
                deviceNArray(namesArray("S1", "S2"), COSName.DEVICEGRAY,
                        tint2to1, null));
        dnToRgb("two",
                deviceNArray(namesArray("S1", "S2"), COSName.DEVICEGRAY,
                        tint2to1, null), new float[] {0.5f, 0.25f});

        // (14) colorant-names array with NON-NAME entries (a string in the
        //      middle) — getColorantNames casts each to COSName in PDFBox.
        COSArray mixedNames = new COSArray();
        mixedNames.add(COSName.getPDFName("A"));
        mixedNames.add(new COSString("B"));
        mixedNames.add(COSName.getPDFName("C"));
        describeDn("mixed_names",
                deviceNArray(mixedNames, COSName.DEVICEGRAY, grayTint, null));

        // (15) /Attributes MISSING (only 4 array entries) — already (12).
        //      /Attributes NON-DICT (a name in the attributes slot).
        COSArray nonDictAttr = deviceNArray(namesArray("S1"),
                COSName.DEVICEGRAY, grayTint, null);
        nonDictAttr.add(COSName.getPDFName("NotADict"));
        describeDn("nondict_attr", nonDictAttr);
        describeDnProcess("nondict_attr", nonDictAttr);

        // (16) /Attributes with /Colorants sub-dict (3 spot Separations) +
        //      /Process DeviceCMYK with named /Components, NChannel.
        COSArray dnNames3 = namesArray("Spot1", "Spot2", "Spot3");
        COSStream tint3to4 = type4(
                new float[] {0, 1, 0, 1, 0, 1},
                new float[] {0, 1, 0, 1, 0, 1, 0, 1},
                "{ 0 }");
        COSDictionary processDict = new COSDictionary();
        processDict.setItem(COSName.COLORSPACE, COSName.DEVICECMYK);
        processDict.setItem(COSName.COMPONENTS,
                namesArray("Cyan", "Magenta", "Yellow", "Black"));
        COSDictionary colorantsDict = new COSDictionary();
        colorantsDict.setItem(COSName.getPDFName("Spot1"),
                sepArrayCmyk("Spot1", new float[] {1, 0, 0, 0}));
        colorantsDict.setItem(COSName.getPDFName("Spot2"),
                sepArrayCmyk("Spot2", new float[] {0, 1, 0, 0}));
        colorantsDict.setItem(COSName.getPDFName("Spot3"),
                sepArrayCmyk("Spot3", new float[] {0, 0, 1, 0}));
        COSDictionary attrsDict = new COSDictionary();
        attrsDict.setName(COSName.SUBTYPE, "NChannel");
        attrsDict.setItem(COSName.PROCESS, processDict);
        attrsDict.setItem(COSName.COLORANTS, colorantsDict);
        COSArray dnFull = deviceNArray(dnNames3, COSName.DEVICECMYK,
                tint3to4, attrsDict);
        describeDn("attr_full", dnFull);
        describeDnProcess("attr_full", dnFull);
        describeDnColorants("attr_full", dnFull);

        // (17) /Process with mismatched /Components count vs /ColorSpace —
        //      DeviceCMYK (4 comp) but only 2 named components.
        COSDictionary processBad = new COSDictionary();
        processBad.setItem(COSName.COLORSPACE, COSName.DEVICECMYK);
        processBad.setItem(COSName.COMPONENTS, namesArray("Cyan", "Magenta"));
        COSDictionary attrsBad = new COSDictionary();
        attrsBad.setItem(COSName.PROCESS, processBad);
        COSArray dnBadProc = deviceNArray(namesArray("S1"),
                COSName.DEVICECMYK,
                type4(new float[] {0, 1}, new float[] {0, 1, 0, 1, 0, 1, 0, 1},
                        "{ 0 0 0 }"),
                attrsBad);
        describeDn("attr_badproc", dnBadProc);
        describeDnProcess("attr_badproc", dnBadProc);

        // (18) /Attributes present but EMPTY dict (no /Subtype, /Process,
        //      /Colorants). getColorants inserts an empty /Colorants in
        //      PDFBox.
        COSArray dnEmptyAttr = deviceNArray(namesArray("S1"),
                COSName.DEVICEGRAY, grayTint, new COSDictionary());
        describeDn("attr_empty", dnEmptyAttr);
        describeDnProcess("attr_empty", dnEmptyAttr);
        describeDnColorants("attr_empty", dnEmptyAttr);

        // (19) DeviceN missing alternate (array = [/DeviceN names]).
        COSArray dnNoAlt = new COSArray();
        dnNoAlt.add(COSName.DEVICEN);
        dnNoAlt.add(namesArray("S1"));
        describeDn("no_alt", dnNoAlt);
        dnToRgb("no_alt", dnNoAlt, new float[] {0.5f});

        // (20) DeviceN missing tint (array = [/DeviceN names alt]).
        COSArray dnNoTint = new COSArray();
        dnNoTint.add(COSName.DEVICEN);
        dnNoTint.add(namesArray("S1"));
        dnNoTint.add(COSName.DEVICEGRAY);
        describeDn("no_tint", dnNoTint);
        dnToRgb("no_tint", dnNoTint, new float[] {0.5f});
    }

    static COSArray deviceNArray(COSArray names, Object alternate,
            Object tint, COSDictionary attrs) {
        COSArray arr = new COSArray();
        arr.add(COSName.DEVICEN);
        arr.add(names);
        arr.add((org.apache.pdfbox.cos.COSBase) alternate);
        arr.add((org.apache.pdfbox.cos.COSBase) tint);
        if (attrs != null) {
            arr.add(attrs);
        }
        return arr;
    }

    static COSArray sepArrayCmyk(String colorant, float[] c1) {
        COSArray arr = new COSArray();
        arr.add(COSName.SEPARATION);
        arr.add(COSName.getPDFName(colorant));
        arr.add(COSName.DEVICECMYK);
        arr.add(type2(new float[] {0, 0, 0, 0}, c1, 1.0f));
        return arr;
    }
}
