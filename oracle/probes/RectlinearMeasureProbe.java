import java.io.PrintStream;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.interactive.measurement.PDMeasureDictionary;
import org.apache.pdfbox.pdmodel.interactive.measurement.PDNumberFormatDictionary;
import org.apache.pdfbox.pdmodel.interactive.measurement.PDRectlinearMeasureDictionary;

/**
 * Live oracle probe for {@code PDRectlinearMeasureDictionary} (and its
 * {@code PDMeasureDictionary} base): the measurement package has had NO oracle
 * coverage. Pins:
 *
 *   - the empty-dictionary accessor defaults (whether array getters return null
 *     vs empty array; whether getCYX returns the COSDictionary float default);
 *   - the /Type and /Subtype the constructor stamps;
 *   - the round-trip of a scale ratio, a single-element number-format array,
 *     the coordinate-system origin, and CYX.
 *
 * No arguments. Output (UTF-8, LF-terminated "key=value" lines).
 */
public final class RectlinearMeasureProbe {

    private static String arr(PDNumberFormatDictionary[] a) {
        if (a == null) {
            return "NULL";
        }
        return "len:" + a.length;
    }

    private static String farr(float[] a) {
        if (a == null) {
            return "NULL";
        }
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < a.length; i++) {
            if (i > 0) {
                sb.append(",");
            }
            sb.append(a[i]);
        }
        return sb.append("]").toString();
    }

    public static void main(String[] args) {
        PrintStream out = new PrintStream(System.out, true, java.nio.charset.StandardCharsets.UTF_8);

        PDRectlinearMeasureDictionary m = new PDRectlinearMeasureDictionary();
        out.println("empty.type=" + m.getType());
        out.println("empty.subtype=" + m.getSubtype());
        out.println("empty.scaleRatio=" + (m.getScaleRatio() == null ? "NULL" : m.getScaleRatio()));
        out.println("empty.changeXs=" + arr(m.getChangeXs()));
        out.println("empty.changeYs=" + arr(m.getChangeYs()));
        out.println("empty.distances=" + arr(m.getDistances()));
        out.println("empty.areas=" + arr(m.getAreas()));
        out.println("empty.angles=" + arr(m.getAngles()));
        out.println("empty.lineSloaps=" + arr(m.getLineSloaps()));
        out.println("empty.coordSystemOrigin=" + farr(m.getCoordSystemOrigin()));
        out.println("empty.cyx=" + m.getCYX());

        // base type constant
        out.println("const.measure.type=" + PDMeasureDictionary.TYPE);

        PDRectlinearMeasureDictionary s = new PDRectlinearMeasureDictionary();
        s.setScaleRatio("1in = 1mi");
        PDNumberFormatDictionary nf = new PDNumberFormatDictionary();
        nf.setUnits("mi");
        s.setDistances(new PDNumberFormatDictionary[] {nf});
        s.setCoordSystemOrigin(new float[] {1.5f, -2.0f});
        s.setCYX(0.75f);

        out.println("set.scaleRatio=" + s.getScaleRatio());
        out.println("set.distances=" + arr(s.getDistances()));
        out.println("set.distances0.units="
                + (s.getDistances()[0].getUnits() == null ? "NULL" : s.getDistances()[0].getUnits()));
        out.println("set.coordSystemOrigin=" + farr(s.getCoordSystemOrigin()));
        out.println("set.cyx=" + s.getCYX());

        java.util.TreeSet<String> keys = new java.util.TreeSet<>();
        for (COSName k : s.getCOSObject().keySet()) {
            keys.add(k.getName());
        }
        out.println("wire.keys=" + String.join(",", keys));
    }
}
