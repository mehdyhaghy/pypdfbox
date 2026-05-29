import java.io.PrintStream;
import java.util.Map;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceNAttributes;
import org.apache.pdfbox.pdmodel.graphics.color.PDSeparation;

/**
 * Live oracle probe for the DeviceN {@code /Attributes} string form
 * ({@code PDDeviceNAttributes.toString()}) and the {@code getColorants()}
 * self-population side effect (PDF 32000-1 &sect;8.6.6.5).
 *
 * The sibling {@code DeviceNAttrProbe} covers every structural accessor
 * (colorant names, NChannel flag, process colour-space name + components,
 * colorants key set, per-entry colour-space name) and the {@code toRGB}
 * path. It never emits {@code PDDeviceNAttributes.toString()} nor exercises
 * the empty-{@code /Colorants} self-population branch — this probe pins both.
 *
 * IMPORTANT: {@code PDDeviceNAttributes.toString()} appends {@code getProcess()}
 * via {@code StringBuilder.append(Object)}, and neither {@code PDDeviceNProcess}
 * nor {@code PDDeviceCMYK} override {@code Object.toString()} with a stable form
 * when a process colour space is present (the process colour-space leg renders
 * a JVM hashcode). So this probe deliberately builds attributes WITHOUT a
 * {@code /Process} dict, making the whole {@code toString()} deterministic:
 *
 *   {@code <Subtype>{Colorants{"<key>": <PDSeparation.toString()> ...}}}
 *
 * Each colorant value renders via {@code PDSeparation.toString()}:
 *   {@code Separation{"<colorant>" <alternate-name> <tint>}}
 *
 * Emitted lines (the Python side reproduces verbatim):
 *
 *   ATTR_TOSTRING_NCHANNEL &lt;PDDeviceNAttributes.toString()&gt;
 *   ATTR_TOSTRING_DEVICEN  &lt;PDDeviceNAttributes.toString()&gt;   (plain /DeviceN subtype)
 *   COLORANTS_AUTOPOPULATE_BEFORE &lt;true|false&gt;   (dict has /Colorants before getColorants)
 *   COLORANTS_AUTOPOPULATE_AFTER  &lt;true|false&gt;   (dict has /Colorants after getColorants on empty attrs)
 *   COLORANTS_AUTOPOPULATE_SIZE   &lt;n&gt;            (size of returned map for empty attrs)
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; DeviceNAttrToStringProbe
 */
public final class DeviceNAttrToStringProbe {

    static PrintStream out;

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

    /** A single-colorant Separation array: [/Separation name /DeviceCMYK tint]. */
    static COSArray separationArray(String colorant, float[] c1) {
        COSArray arr = new COSArray();
        arr.add(COSName.SEPARATION);
        arr.add(COSName.getPDFName(colorant));
        arr.add(COSName.DEVICECMYK);
        arr.add(type2(new float[] {0, 0, 0, 0}, c1, 1.0f));
        return arr;
    }

    /** Build an attributes dict (NO /Process) with two spot colorants. */
    static COSDictionary attrsDict(String subtype) {
        COSDictionary colorantsDict = new COSDictionary();
        colorantsDict.setItem(COSName.getPDFName("Spot1"),
            separationArray("Spot1", new float[] {1, 0, 0, 0}));
        colorantsDict.setItem(COSName.getPDFName("Spot2"),
            separationArray("Spot2", new float[] {0, 1, 0, 0}));
        COSDictionary attrs = new COSDictionary();
        attrs.setName(COSName.SUBTYPE, subtype);
        attrs.setItem(COSName.COLORANTS, colorantsDict);
        return attrs;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ---------- toString(), NChannel subtype, no /Process ----------
        PDDeviceNAttributes nchannel = new PDDeviceNAttributes(attrsDict("NChannel"));
        out.println("ATTR_TOSTRING_NCHANNEL " + nchannel.toString());

        // ---------- toString(), plain DeviceN subtype, no /Process ----------
        PDDeviceNAttributes deviceN = new PDDeviceNAttributes(attrsDict("DeviceN"));
        out.println("ATTR_TOSTRING_DEVICEN " + deviceN.toString());

        // ---------- getColorants() self-population side effect ----------
        // Empty attributes dict (no /Colorants). getColorants() must INSERT an
        // empty /Colorants COSDictionary into the backing dict and return an
        // empty map.
        COSDictionary emptyDict = new COSDictionary();
        PDDeviceNAttributes empty = new PDDeviceNAttributes(emptyDict);
        boolean before = emptyDict.getCOSDictionary(COSName.COLORANTS) != null;
        Map<String, PDSeparation> map = empty.getColorants();
        boolean after = emptyDict.getCOSDictionary(COSName.COLORANTS) != null;
        out.println("COLORANTS_AUTOPOPULATE_BEFORE " + before);
        out.println("COLORANTS_AUTOPOPULATE_AFTER " + after);
        out.println("COLORANTS_AUTOPOPULATE_SIZE " + map.size());
    }
}
