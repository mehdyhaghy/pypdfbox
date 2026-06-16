import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;

/**
 * Malformed-input oracle for PDAppearanceDictionary / PDAppearanceEntry
 * state RESOLUTION on PDFBox 3.0.7.
 *
 * Complements AppearanceDictionaryFuzzProbe (wave 1520, /AP value-type
 * matrix) and AppearanceEntryFuzzProbe (wave 1531, per-entry value +
 * stream numeric accessors) by drilling into angles neither covers:
 *
 *  - /R, /D absent -> getRolloverAppearance / getDownAppearance fall
 *    back to /N; assert the fallback entry wraps the SAME COS object as
 *    /N (object identity of the resolved stream), and that an explicit
 *    /R or /D shadows the /N fallback.
 *  - getSubDictionary returned-map VALUES: resolve each state stream's
 *    /BBox (existing probes only project the key names), simulating the
 *    widget /AS state pick (sub.get(asName)).
 *  - the full getNormalAppearance().getAppearanceStream() chain BBox/
 *    resources of a direct /N stream.
 *  - double-indirect (COSObject -> COSObject -> stream/dict) /N values.
 *  - a /N sub-dictionary whose state value is itself an indirect stream
 *    with its own /BBox -> getSubDictionary resolves through the COSObject
 *    AND exposes the resolved bbox.
 *  - PDAppearanceStream wrapping a state stream shared by the sub-dict
 *    (object identity of getCOSObject()).
 */
public final class AppearanceDictResolveFuzzProbe {

    private static COSObject indirect(COSBase value) {
        return new COSObject(value);
    }

    private static String num(float value) {
        return value == Math.rint(value) ? Long.toString((long) value) : Float.toString(value);
    }

    private static String bbox(PDAppearanceStream stream) {
        PDRectangle rect = stream.getBBox();
        if (rect == null) {
            return "none";
        }
        return num(rect.getLowerLeftX()) + "," + num(rect.getLowerLeftY())
                + "," + num(rect.getUpperRightX()) + "," + num(rect.getUpperRightY());
    }

    private static COSArray nums(float... values) {
        COSArray array = new COSArray();
        for (float value : values) {
            array.add(new COSFloat(value));
        }
        return array;
    }

    private static COSStream streamWithBBox(float... values) {
        COSStream stream = new COSStream();
        stream.setItem(COSName.BBOX, nums(values));
        return stream;
    }

    // ---- /R, /D fallback to /N ----

    private static void emitFallbackCases() {
        // /R, /D absent -> both fall back to /N; the resolved appearance
        // stream must be the very same COS object as /N's.
        COSStream normal = streamWithBBox(0, 0, 11, 22);
        COSDictionary onlyN = new COSDictionary();
        onlyN.setItem(COSName.N, normal);
        PDAppearanceDictionary ap = new PDAppearanceDictionary(onlyN);

        PDAppearanceEntry n = ap.getNormalAppearance();
        PDAppearanceEntry r = ap.getRolloverAppearance();
        PDAppearanceEntry d = ap.getDownAppearance();
        boolean rSame = r.getAppearanceStream().getCOSObject() == normal;
        boolean dSame = d.getAppearanceStream().getCOSObject() == normal;
        boolean nSame = n.getAppearanceStream().getCOSObject() == normal;
        System.out.println("FALLBACK absent r_notnull=" + (r != null)
                + " d_notnull=" + (d != null)
                + " r_is_n=" + rSame + " d_is_n=" + dSame + " n_is_n=" + nSame
                + " r_bbox=" + bbox(r.getAppearanceStream())
                + " d_bbox=" + bbox(d.getAppearanceStream()));

        // Explicit /R, /D shadow the /N fallback (different bbox).
        COSStream roll = streamWithBBox(0, 0, 33, 44);
        COSStream down = streamWithBBox(0, 0, 55, 66);
        COSDictionary all = new COSDictionary();
        all.setItem(COSName.N, normal);
        all.setItem(COSName.R, roll);
        all.setItem(COSName.D, down);
        PDAppearanceDictionary ap2 = new PDAppearanceDictionary(all);
        boolean rShadow = ap2.getRolloverAppearance().getAppearanceStream().getCOSObject() == roll;
        boolean dShadow = ap2.getDownAppearance().getAppearanceStream().getCOSObject() == down;
        System.out.println("FALLBACK shadow r_is_roll=" + rShadow + " d_is_down=" + dShadow
                + " r_bbox=" + bbox(ap2.getRolloverAppearance().getAppearanceStream())
                + " d_bbox=" + bbox(ap2.getDownAppearance().getAppearanceStream()));

        // /N missing entirely -> getNormalAppearance null, and the
        // fallback getters also null.
        PDAppearanceDictionary empty = new PDAppearanceDictionary(new COSDictionary());
        System.out.println("FALLBACK noN n_null=" + (empty.getNormalAppearance() == null)
                + " r_null=" + (empty.getRolloverAppearance() == null)
                + " d_null=" + (empty.getDownAppearance() == null));
    }

    // ---- direct /N stream full chain ----

    private static void emitDirectChainCases() {
        COSStream normal = new COSStream();
        normal.setItem(COSName.BBOX, nums(1, 2, 30, 40));
        normal.setItem(COSName.RESOURCES, new COSDictionary());
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.N, normal);
        PDAppearanceDictionary ap = new PDAppearanceDictionary(d);
        PDAppearanceEntry n = ap.getNormalAppearance();
        PDAppearanceStream s = n.getAppearanceStream();
        System.out.println("CHAIN direct isStream=" + n.isStream()
                + " isSub=" + n.isSubDictionary()
                + " bbox=" + bbox(s)
                + " resources=" + (s.getResources() == null ? "none" : "dict")
                + " identity=" + (s.getCOSObject() == normal));
    }

    // ---- double-indirect /N value ----

    private static void emitDoubleIndirectCases() {
        COSStream inner = streamWithBBox(0, 0, 7, 8);
        COSObject once = indirect(inner);
        COSObject twice = indirect(once);
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.N, twice);
        PDAppearanceDictionary ap = new PDAppearanceDictionary(d);
        PDAppearanceEntry n = ap.getNormalAppearance();
        String result;
        if (n == null) {
            result = "none";
        } else {
            result = "isStream=" + n.isStream() + " bbox=" + bbox(n.getAppearanceStream());
        }
        System.out.println("DOUBLEIND n=" + result);
    }

    // ---- sub-dictionary state resolution (the /AS pick) ----

    private static void emitStateResolveCases() {
        COSStream off = streamWithBBox(0, 0, 1, 1);
        COSStream on = streamWithBBox(0, 0, 2, 2);
        COSStream indState = streamWithBBox(0, 0, 3, 3);
        COSDictionary states = new COSDictionary();
        states.setItem(COSName.getPDFName("Off"), off);
        states.setItem(COSName.getPDFName("On"), on);
        states.setItem(COSName.getPDFName("Half"), indirect(indState));
        states.setItem(COSName.getPDFName("Bad"), COSInteger.get(9));
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.N, states);
        PDAppearanceDictionary ap = new PDAppearanceDictionary(d);
        PDAppearanceEntry n = ap.getNormalAppearance();

        Map<COSName, PDAppearanceStream> sub = n.getSubDictionary();
        // count + each present state's bbox + the dropped non-stream
        List<String> rows = new ArrayList<>();
        for (String key : new String[] {"Off", "On", "Half", "Bad", "Missing"}) {
            PDAppearanceStream s = sub.get(COSName.getPDFName(key));
            rows.add(key + "=" + (s == null ? "none" : bbox(s)));
        }
        Collections.sort(rows);
        boolean halfIdentity = sub.get(COSName.getPDFName("Half")) != null
                && sub.get(COSName.getPDFName("Half")).getCOSObject() == indState;
        // NOTE: sub.size() reflects the underlying COSDictionary entry count
        // (COSDictionaryMap delegates size() to the raw dict -> 4 here,
        // including the non-stream "Bad"), whereas keySet() only contains the
        // stream-valued states. We project keys=keySet().size() because that
        // is the behaviourally meaningful (iteration/get) count; pypdfbox's
        // get_sub_dictionary returns a plain dict whose len() matches keySet.
        System.out.println("STATERESOLVE keys=" + sub.keySet().size()
                + " rawsize=" + sub.size()
                + " " + String.join(" ", rows)
                + " half_identity=" + halfIdentity
                + " isSub=" + n.isSubDictionary());
    }

    public static void main(String[] args) {
        emitFallbackCases();
        emitDirectChainCases();
        emitDoubleIndirectCases();
        emitStateResolveCases();
    }
}
