import java.io.OutputStream;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceN;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceNAttributes;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceNProcess;
import org.apache.pdfbox.pdmodel.graphics.color.PDSeparation;

/**
 * Live oracle probe for the DEEP DeviceN attribute surface (PDF 32000-1
 * &sect;8.6.6.5, NChannel) and a Separation {@code /All} edge case.
 *
 * Builds two colour spaces entirely from in-memory COS objects:
 *
 *   (a) DeviceNAttr — a 3-colorant DeviceN whose {@code /Attributes} dict
 *       carries:
 *         - {@code /Subtype /NChannel},
 *         - a {@code /Process} sub-dict: process colour space DeviceCMYK with a
 *           {@code /Components} name list [Cyan Magenta Yellow Black],
 *         - a {@code /Colorants} attribute dict mapping each spot colorant name
 *           to its OWN Separation colour space (tint -&gt; DeviceCMYK),
 *       and a Type-4 tint transform mapping the 3 tints -&gt; CMYK for the
 *       {@code toRGB} fallback path.
 *
 *   (b) SepAll — a Separation with the {@code /All} colorant (tint -&gt;
 *       DeviceGray) to exercise the {@code /All} colorant-name accessor.
 *
 * Emits canonical lines the Python side reproduces verbatim:
 *
 *   COLORANTS &lt;name0&gt; &lt;name1&gt; ...          (getColorantNames)
 *   NUMCOMPONENTS &lt;n&gt;                       (getNumberOfComponents)
 *   NCHANNEL &lt;true|false&gt;                   (isNChannel)
 *   PROCESS_CS &lt;color-space-name&gt;           (attributes.getProcess.getColorSpace.getName)
 *   PROCESS_COMPONENTS &lt;c0&gt; &lt;c1&gt; ...        (process.getComponents)
 *   COLORANTS_KEYS &lt;k0&gt; &lt;k1&gt; ...            (sorted attributes.getColorants key set)
 *   COLORANT_CS &lt;key&gt; &lt;color-space-name&gt;    (per /Colorants entry colour-space name)
 *   TORGB &lt;c0&gt; &lt;c1&gt; ... -&gt; &lt;r&gt; &lt;g&gt; &lt;b&gt;     (toRGB, 0-255 ints)
 *   SEP_COLORANT &lt;name&gt;                     (separation.getColorantName)
 *   SEP_NUMCOMPONENTS &lt;n&gt;
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; DeviceNAttrProbe
 */
public final class DeviceNAttrProbe {

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

    static COSStream type4(float[] domain, float[] range, String ps) throws Exception {
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

    /** A single-colorant Separation array: [/Separation name /DeviceCMYK tint]. */
    static COSArray separationArray(String colorant, float[] c1) {
        COSArray arr = new COSArray();
        arr.add(COSName.SEPARATION);
        arr.add(COSName.getPDFName(colorant));
        arr.add(COSName.DEVICECMYK);
        arr.add(type2(new float[] {0, 0, 0, 0}, c1, 1.0f));
        return arr;
    }

    static void emit(String name, float[] comps, PDColorSpace cs) throws Exception {
        float[] rgb = cs.toRGB(comps);
        StringBuilder sb = new StringBuilder();
        sb.append("TORGB ").append(name);
        for (float c : comps) {
            sb.append(' ').append(fmt(c));
        }
        sb.append(" -> ");
        sb.append(clamp255(rgb[0])).append(' ');
        sb.append(clamp255(rgb[1])).append(' ');
        sb.append(clamp255(rgb[2]));
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ---------- (a) 3-colorant NChannel DeviceN with /Process + /Colorants ----------
        // Spot colorants: Spot1, Spot2, Spot3.
        COSArray dnNames = new COSArray();
        dnNames.add(COSName.getPDFName("Spot1"));
        dnNames.add(COSName.getPDFName("Spot2"));
        dnNames.add(COSName.getPDFName("Spot3"));

        // Tint transform: (a,b,c) -> CMYK (a, b, c, 0).  Type-4 PostScript.
        COSStream tint = type4(
            new float[] {0, 1, 0, 1, 0, 1},
            new float[] {0, 1, 0, 1, 0, 1, 0, 1},
            "{ 0 }");

        // /Process: DeviceCMYK with four named components.
        COSDictionary processDict = new COSDictionary();
        processDict.setItem(COSName.COLORSPACE, COSName.DEVICECMYK);
        COSArray procComponents = new COSArray();
        procComponents.add(COSName.getPDFName("Cyan"));
        procComponents.add(COSName.getPDFName("Magenta"));
        procComponents.add(COSName.getPDFName("Yellow"));
        procComponents.add(COSName.getPDFName("Black"));
        processDict.setItem(COSName.COMPONENTS, procComponents);

        // /Colorants: each spot colorant -> its own Separation colour space.
        COSDictionary colorantsDict = new COSDictionary();
        colorantsDict.setItem(COSName.getPDFName("Spot1"),
            separationArray("Spot1", new float[] {1, 0, 0, 0}));
        colorantsDict.setItem(COSName.getPDFName("Spot2"),
            separationArray("Spot2", new float[] {0, 1, 0, 0}));
        colorantsDict.setItem(COSName.getPDFName("Spot3"),
            separationArray("Spot3", new float[] {0, 0, 1, 0}));

        // /Attributes
        COSDictionary attrsDict = new COSDictionary();
        attrsDict.setName(COSName.SUBTYPE, "NChannel");
        attrsDict.setItem(COSName.PROCESS, processDict);
        attrsDict.setItem(COSName.COLORANTS, colorantsDict);

        COSArray dnArr = new COSArray();
        dnArr.add(COSName.DEVICEN);
        dnArr.add(dnNames);
        dnArr.add(COSName.DEVICECMYK);
        dnArr.add(tint);
        dnArr.add(attrsDict);
        PDDeviceN devicen = new PDDeviceN(dnArr);

        // getColorantNames
        StringBuilder cn = new StringBuilder("COLORANTS");
        for (String n : devicen.getColorantNames()) {
            cn.append(' ').append(n);
        }
        out.println(cn.toString());

        // getNumberOfComponents
        out.println("NUMCOMPONENTS " + devicen.getNumberOfComponents());

        // isNChannel
        out.println("NCHANNEL " + devicen.isNChannel());

        // /Process colour-space name + components
        PDDeviceNAttributes attrs = devicen.getAttributes();
        PDDeviceNProcess process = attrs.getProcess();
        PDColorSpace processCs = process.getColorSpace();
        out.println("PROCESS_CS " + processCs.getName());
        StringBuilder pc = new StringBuilder("PROCESS_COMPONENTS");
        for (String n : process.getComponents()) {
            pc.append(' ').append(n);
        }
        out.println(pc.toString());

        // /Colorants key set (sorted) + per-entry colour-space name
        Map<String, PDSeparation> colorants = attrs.getColorants();
        TreeSet<String> keys = new TreeSet<>(colorants.keySet());
        StringBuilder ck = new StringBuilder("COLORANTS_KEYS");
        for (String k : keys) {
            ck.append(' ').append(k);
        }
        out.println(ck.toString());
        for (String k : keys) {
            out.println("COLORANT_CS " + k + " " + colorants.get(k).getName());
        }

        // toRGB for a few tints (attribute-driven path).
        List<float[]> tints = new ArrayList<>();
        tints.add(new float[] {0.0f, 0.0f, 0.0f});
        tints.add(new float[] {1.0f, 0.0f, 0.0f});
        tints.add(new float[] {0.0f, 1.0f, 0.0f});
        tints.add(new float[] {0.0f, 0.0f, 1.0f});
        tints.add(new float[] {1.0f, 1.0f, 1.0f});
        tints.add(new float[] {0.25f, 0.5f, 0.75f});
        for (float[] t : tints) {
            emit("DeviceNAttr", t, devicen);
        }

        // ---------- (b) Separation /All -> DeviceGray ----------
        COSArray sepArr = new COSArray();
        sepArr.add(COSName.SEPARATION);
        sepArr.add(COSName.getPDFName("All"));
        sepArr.add(COSName.DEVICEGRAY);
        sepArr.add(type4(
            new float[] {0.0f, 1.0f},
            new float[] {0.0f, 1.0f},
            "{ 1 exch sub }"));
        PDSeparation sepAll = new PDSeparation(sepArr);
        out.println("SEP_COLORANT " + sepAll.getColorantName());
        out.println("SEP_NUMCOMPONENTS " + sepAll.getNumberOfComponents());
        emit("SepAll", new float[] {0.0f}, sepAll);
        emit("SepAll", new float[] {0.5f}, sepAll);
        emit("SepAll", new float[] {1.0f}, sepAll);
    }
}
