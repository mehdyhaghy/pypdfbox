import java.io.PrintStream;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.interactive.measurement.PDMeasureDictionary;
import org.apache.pdfbox.pdmodel.interactive.measurement.PDViewportDictionary;

/**
 * Live oracle probe for {@code PDViewportDictionary} accessors and — the real
 * behavioural question — whether {@code getMeasure()} returns the concrete
 * {@code PDRectlinearMeasureDictionary} subtype when the embedded measure
 * dictionary carries {@code /Subtype RL}, or always the base
 * {@code PDMeasureDictionary}.
 *
 * No arguments. Output (UTF-8, LF-terminated "key=value" lines).
 */
public final class ViewportMeasureDispatchProbe {

    public static void main(String[] args) {
        PrintStream out = new PrintStream(System.out, true, java.nio.charset.StandardCharsets.UTF_8);

        PDViewportDictionary v = new PDViewportDictionary();
        out.println("empty.type=" + v.getType());
        out.println("empty.bbox=" + (v.getBBox() == null ? "NULL" : "present"));
        out.println("empty.name=" + (v.getName() == null ? "NULL" : v.getName()));
        out.println("empty.measure=" + (v.getMeasure() == null ? "NULL" : "present"));

        v.setName("Imperial");
        v.setBBox(new PDRectangle(0, 0, 100, 200));

        // Embed an RL-subtype measure manually so we test the dispatch path.
        COSDictionary md = new COSDictionary();
        md.setName(COSName.TYPE, "Measure");
        md.setName(COSName.SUBTYPE, "RL");
        v.getCOSObject().setItem(COSName.MEASURE, md);

        PDMeasureDictionary got = v.getMeasure();
        out.println("set.name=" + v.getName());
        out.println("set.bbox.width=" + v.getBBox().getWidth());
        out.println("set.measure.class=" + (got == null ? "NULL" : got.getClass().getSimpleName()));
        out.println("set.measure.subtype=" + (got == null ? "NULL" : got.getSubtype()));

        // Now an absent-subtype measure.
        COSDictionary md2 = new COSDictionary();
        md2.setName(COSName.TYPE, "Measure");
        v.getCOSObject().setItem(COSName.MEASURE, md2);
        PDMeasureDictionary got2 = v.getMeasure();
        out.println("nosub.measure.class=" + (got2 == null ? "NULL" : got2.getClass().getSimpleName()));

        java.util.TreeSet<String> keys = new java.util.TreeSet<>();
        for (COSName k : v.getCOSObject().keySet()) {
            keys.add(k.getName());
        }
        out.println("wire.keys=" + String.join(",", keys));
    }
}
