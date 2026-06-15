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
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;
import org.apache.pdfbox.util.Matrix;

/**
 * Direct malformed-input oracle for PDAppearanceEntry value resolution
 * (isStream / isSubDictionary / getAppearanceStream / getSubDictionary)
 * and PDAppearanceStream form-XObject accessors (BBox / Matrix /
 * Resources / FormType / StructParents) on PDFBox 3.0.7.
 *
 * Complements AppearanceDictionaryFuzzProbe (wave 1520, /AP dictionary
 * level) by drilling into the per-entry value and the appearance-stream
 * accessor numeric projections (partial / non-numeric BBox, wrong-length
 * Matrix, indirect resolution of state-name -> stream sub-dictionary).
 */
public final class AppearanceEntryFuzzProbe {

    private static COSObject indirect(COSBase value) {
        return new COSObject(value);
    }

    private static String message(Exception exception) {
        String value = exception.getMessage();
        return value == null ? exception.getClass().getSimpleName() : value.replace(' ', '_');
    }

    private static String num(float value) {
        return value == Math.rint(value) ? Long.toString((long) value) : Float.toString(value);
    }

    // ---- PDAppearanceEntry projection ----

    private static String emitEntry(String name, PDAppearanceEntry entry) {
        StringBuilder sb = new StringBuilder("ENTRY " + name);
        sb.append(" isStream=").append(entry.isStream());
        sb.append(" isSub=").append(entry.isSubDictionary());
        sb.append(" as=");
        try {
            sb.append(entry.getAppearanceStream() == null ? "none" : "stream");
        } catch (Exception exception) {
            sb.append("ERR:").append(message(exception));
        }
        sb.append(" sub=");
        try {
            Map<COSName, PDAppearanceStream> states = entry.getSubDictionary();
            List<String> names = new ArrayList<>();
            for (COSName key : states.keySet()) {
                names.add(key.getName());
            }
            Collections.sort(names);
            sb.append(names.isEmpty() ? "empty" : String.join(",", names));
        } catch (Exception exception) {
            sb.append("ERR:").append(message(exception));
        }
        return sb.toString();
    }

    private static void emitEntryCases() {
        // Single appearance stream.
        System.out.println(emitEntry("stream", new PDAppearanceEntry(new COSStream())));

        // Empty sub-dictionary.
        System.out.println(emitEntry("empty_dict", new PDAppearanceEntry(new COSDictionary())));

        // Sub-dictionary of direct streams.
        COSDictionary states = new COSDictionary();
        states.setItem(COSName.getPDFName("On"), new COSStream());
        states.setItem(COSName.getPDFName("Off"), new COSStream());
        System.out.println(emitEntry("two_states", new PDAppearanceEntry(states)));

        // Sub-dictionary mixing stream / indirect-stream / non-stream values.
        COSDictionary mixed = new COSDictionary();
        mixed.setItem(COSName.getPDFName("Direct"), new COSStream());
        mixed.setItem(COSName.getPDFName("Indirect"), indirect(new COSStream()));
        mixed.setItem(COSName.getPDFName("Scalar"), COSInteger.get(7));
        mixed.setItem(COSName.getPDFName("Null"), COSNull.NULL);
        mixed.setItem(COSName.getPDFName("Dict"), new COSDictionary());
        mixed.setItem(COSName.getPDFName("Str"), new COSString("x"));
        mixed.setItem(COSName.getPDFName("IndNull"), indirect(COSNull.NULL));
        System.out.println(emitEntry("mixed", new PDAppearanceEntry(mixed)));

        // Sub-dictionary whose only value is /null (PDFBOX-1599 shape).
        COSDictionary onlyNull = new COSDictionary();
        onlyNull.setItem(COSName.getPDFName("D"), COSNull.NULL);
        System.out.println(emitEntry("only_null", new PDAppearanceEntry(onlyNull)));

        // Sub-dictionary key edge cases (empty name, space, slash-in-name).
        COSDictionary names = new COSDictionary();
        names.setItem(COSName.getPDFName("A B"), new COSStream());
        names.setItem(COSName.getPDFName("A/B"), new COSStream());
        System.out.println(emitEntry("odd_names", new PDAppearanceEntry(names)));
    }

    // ---- PDAppearanceStream accessor projection ----

    private static String bbox(PDAppearanceStream stream) {
        PDRectangle rect = stream.getBBox();
        if (rect == null) {
            return "none";
        }
        return num(rect.getLowerLeftX()) + "," + num(rect.getLowerLeftY())
                + "," + num(rect.getUpperRightX()) + "," + num(rect.getUpperRightY());
    }

    private static String matrix(PDAppearanceStream stream) {
        Matrix m = stream.getMatrix();
        float[] values = {
            m.getScaleX(), m.getShearY(), m.getShearX(),
            m.getScaleY(), m.getTranslateX(), m.getTranslateY()
        };
        List<String> parts = new ArrayList<>();
        for (float value : values) {
            parts.add(num(value));
        }
        return String.join(",", parts);
    }

    private static String emitStream(String name, COSStream cos) {
        PDAppearanceStream stream = new PDAppearanceStream(cos);
        return "STREAM " + name
                + " form=" + stream.getFormType()
                + " struct=" + stream.getStructParents()
                + " bbox=" + bbox(stream)
                + " matrix=" + matrix(stream)
                + " resources=" + (stream.getResources() == null ? "none" : "dict");
    }

    private static COSArray nums(float... values) {
        COSArray array = new COSArray();
        for (float value : values) {
            array.add(new COSFloat(value));
        }
        return array;
    }

    private static void emitStreamCases() {
        System.out.println(emitStream("default", new COSStream()));

        // Well-formed bbox + matrix + resources.
        COSStream good = new COSStream();
        good.setItem(COSName.BBOX, nums(0, 0, 100, 200));
        good.setItem(COSName.MATRIX, nums(2, 0, 0, 3, 5, 7));
        good.setItem(COSName.RESOURCES, new COSDictionary());
        good.setItem(COSName.FORMTYPE, COSInteger.get(1));
        good.setItem(COSName.STRUCT_PARENTS, COSInteger.get(4));
        System.out.println(emitStream("good", good));

        // Partial BBox (3 entries) -> PDRectangle reads missing 4th as 0.
        COSStream partialBbox = new COSStream();
        partialBbox.setItem(COSName.BBOX, nums(1, 2, 3));
        System.out.println(emitStream("bbox3", partialBbox));

        // Over-long BBox (6 entries) -> only first 4 used.
        COSStream longBbox = new COSStream();
        longBbox.setItem(COSName.BBOX, nums(1, 2, 3, 4, 5, 6));
        System.out.println(emitStream("bbox6", longBbox));

        // BBox with a non-numeric entry -> that slot reads as 0.
        COSStream badBbox = new COSStream();
        COSArray bboxMix = new COSArray();
        bboxMix.add(COSInteger.get(1));
        bboxMix.add(COSName.getPDFName("Bad"));
        bboxMix.add(COSInteger.get(3));
        bboxMix.add(COSInteger.get(4));
        badBbox.setItem(COSName.BBOX, bboxMix);
        System.out.println(emitStream("bbox_nan", badBbox));

        // BBox wrong type (name not array) -> getBBox null.
        COSStream nameBbox = new COSStream();
        nameBbox.setItem(COSName.BBOX, COSName.getPDFName("Bad"));
        System.out.println(emitStream("bbox_name", nameBbox));

        // Empty BBox array -> all-zero rectangle.
        COSStream emptyBbox = new COSStream();
        emptyBbox.setItem(COSName.BBOX, new COSArray());
        System.out.println(emitStream("bbox_empty", emptyBbox));

        // Matrix too short (5 entries) -> identity fallback.
        COSStream shortMatrix = new COSStream();
        shortMatrix.setItem(COSName.MATRIX, nums(2, 0, 0, 3, 5));
        System.out.println(emitStream("mtx5", shortMatrix));

        // Matrix over-long (7 entries) -> first 6 used.
        COSStream longMatrix = new COSStream();
        longMatrix.setItem(COSName.MATRIX, nums(2, 0, 0, 3, 5, 7, 9));
        System.out.println(emitStream("mtx7", longMatrix));

        // Matrix with a non-numeric entry -> identity fallback.
        COSStream nanMatrix = new COSStream();
        COSArray matrixMix = new COSArray();
        matrixMix.add(COSInteger.get(2));
        matrixMix.add(COSInteger.get(0));
        matrixMix.add(COSName.getPDFName("Bad"));
        matrixMix.add(COSInteger.get(3));
        matrixMix.add(COSInteger.get(5));
        matrixMix.add(COSInteger.get(7));
        nanMatrix.setItem(COSName.MATRIX, matrixMix);
        System.out.println(emitStream("mtx_nan", nanMatrix));

        // Matrix wrong type (name) -> identity fallback.
        COSStream nameMatrix = new COSStream();
        nameMatrix.setItem(COSName.MATRIX, COSName.getPDFName("Bad"));
        System.out.println(emitStream("mtx_name", nameMatrix));

        // Resources present but not a dictionary (PDFBOX-4372) -> empty dict.
        COSStream scalarResources = new COSStream();
        scalarResources.setItem(COSName.RESOURCES, COSName.getPDFName("Bad"));
        System.out.println(emitStream("res_name", scalarResources));

        // Resources null value -> getResources null.
        COSStream nullResources = new COSStream();
        nullResources.setItem(COSName.RESOURCES, COSNull.NULL);
        System.out.println(emitStream("res_null", nullResources));

        // Indirect bbox / matrix / resources values are resolved.
        COSStream indirectValues = new COSStream();
        indirectValues.setItem(COSName.BBOX, indirect(nums(0, 0, 10, 20)));
        indirectValues.setItem(COSName.MATRIX, indirect(nums(1, 0, 0, 1, 3, 4)));
        indirectValues.setItem(COSName.RESOURCES, indirect(new COSDictionary()));
        System.out.println(emitStream("indirect", indirectValues));

        // FormType / StructParents wrong types -> default fallbacks.
        COSStream badInts = new COSStream();
        badInts.setItem(COSName.FORMTYPE, COSName.getPDFName("Bad"));
        badInts.setItem(COSName.STRUCT_PARENTS, new COSFloat(4.75f));
        System.out.println(emitStream("badints", badInts));
    }

    public static void main(String[] args) {
        emitEntryCases();
        emitStreamCases();
    }
}
