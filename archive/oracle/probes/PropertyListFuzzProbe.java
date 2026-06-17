import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.markedcontent.BeginMarkedContentSequenceWithProperties;
import org.apache.pdfbox.contentstream.operator.markedcontent.MarkedContentPointWithProperties;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDPropertyList;

/**
 * Live oracle probe for the PDPropertyList.create dispatch + BDC/DP
 * marked-content property resolution surface (PDF 32000-1 §14.6).
 *
 * The Python side writes one PDF per case into args[0] (each carrying a
 * /Properties resource frame + a content stream exercising BDC/DP) plus a
 * manifest.txt listing the case names in order. This probe loads each file
 * and projects TWO independent facets so a divergence pinpoints which one
 * disagrees:
 *
 *  (1) DISPATCH — for every /Properties resource name, the simple class name
 *      of PDResources.getProperties(name): PDOptionalContentGroup (/Type /OCG),
 *      PDOptionalContentMembershipDictionary (/Type /OCMD), PDPropertyList
 *      (any other or absent /Type), or "null" when the entry is not a dict /
 *      absent. This is PDPropertyList.create's dispatch through the resource
 *      cache.
 *
 *  (2) MARKS — the recorded BDC/DP dispatch sequence from a PDFStreamEngine
 *      whose beginMarkedContentSequence / markedContentPoint overrides record
 *      the tag plus the RESOLVED property dictionary (inline dict as-is, named
 *      ref resolved against /Properties, unresolved name -> the engine's
 *      behaviour). This is the operator-processor resolution path.
 *
 * Line grammar (one per case, manifest order; UTF-8):
 *   CASE <name> dispatch=<k:cls|...> marks=<seq>
 * where dispatch entries are sorted by /Properties key (k=key, cls=simple
 * class name or "null"); marks is "/"-free "|"-joined records of the form
 *   BDC:/<tag>:<props>  DP:/<tag>:<props>
 * and <props> is "null" or a canonical dict { k=v ; ... } (keys sorted).
 * A load failure projects dispatch=ERR:<JavaSimpleName> marks=ERR.
 */
public final class PropertyListFuzzProbe {

    static PrintStream out;

    /** Engine recording every BDC / DP dispatch with the resolved props. */
    static final class RecordingEngine extends PDFStreamEngine {
        final StringBuilder marks = new StringBuilder();
        boolean first = true;

        RecordingEngine() {
            addOperator(new BeginMarkedContentSequenceWithProperties(this));
            addOperator(new MarkedContentPointWithProperties(this));
        }

        private void sep() {
            if (!first) {
                marks.append('|');
            }
            first = false;
        }

        @Override
        public void beginMarkedContentSequence(COSName tag, COSDictionary properties) {
            sep();
            marks.append("BDC:/").append(tag == null ? "<none>" : tag.getName())
                    .append(':').append(properties == null ? "null" : canonDict(properties));
        }

        @Override
        public void markedContentPoint(COSName tag, COSDictionary properties) {
            sep();
            marks.append("DP:/").append(tag == null ? "<none>" : tag.getName())
                    .append(':').append(properties == null ? "null" : canonDict(properties));
        }
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        try (PDDocument doc = Loader.loadPDF(pdf)) {
            PDPage page = doc.getPage(0);
            PDResources resources = page.getResources();

            // (1) dispatch facet: class of each /Properties entry.
            TreeMap<String, String> dispatch = new TreeMap<>();
            if (resources != null) {
                for (COSName key : resources.getPropertiesNames()) {
                    String cls;
                    try {
                        PDPropertyList pl = resources.getProperties(key);
                        cls = pl == null ? "null" : pl.getClass().getSimpleName();
                    } catch (Exception e) {
                        cls = "ERR:" + e.getClass().getSimpleName();
                    }
                    dispatch.put(key.getName(), cls);
                }
            }
            StringBuilder dsb = new StringBuilder();
            boolean firstd = true;
            for (java.util.Map.Entry<String, String> e : dispatch.entrySet()) {
                if (!firstd) {
                    dsb.append('|');
                }
                firstd = false;
                dsb.append(e.getKey()).append(':').append(e.getValue());
            }
            sb.append("dispatch=").append(dsb.length() == 0 ? "" : dsb).append(' ');

            // (2) marks facet: BDC/DP dispatch over the content stream.
            RecordingEngine engine = new RecordingEngine();
            engine.processPage(page);
            sb.append("marks=").append(engine.marks);
        } catch (Throwable t) {
            sb.append("dispatch=ERR:").append(t.getClass().getSimpleName())
                    .append(" marks=ERR");
        }
        out.println(sb.toString());
    }

    /** Canonical dictionary: { key=value ; ... } with keys sorted. */
    static String canonDict(COSDictionary d) {
        TreeMap<String, COSBase> sorted = new TreeMap<>();
        for (COSName key : d.keySet()) {
            sorted.put(key.getName(), d.getDictionaryObject(key));
        }
        StringBuilder b = new StringBuilder("{ ");
        boolean first = true;
        for (java.util.Map.Entry<String, COSBase> e : sorted.entrySet()) {
            if (!first) {
                b.append(" ; ");
            }
            first = false;
            b.append(e.getKey()).append('=').append(canonValue(e.getValue()));
        }
        b.append(" }");
        return b.toString();
    }

    static String canonValue(COSBase b) {
        if (b instanceof COSInteger) {
            return "INT:" + ((COSInteger) b).longValue();
        }
        if (b instanceof COSFloat) {
            return "REAL:" + canonFloat(((COSNumber) b).floatValue());
        }
        if (b instanceof COSName) {
            return "NAME:/" + ((COSName) b).getName();
        }
        if (b instanceof COSString) {
            return "STR:" + hex(((COSString) b).getBytes());
        }
        if (b instanceof COSBoolean) {
            return "BOOL:" + (((COSBoolean) b).getValue() ? "true" : "false");
        }
        if (b instanceof COSNull) {
            return "NULL";
        }
        if (b instanceof COSArray) {
            COSArray arr = (COSArray) b;
            StringBuilder s = new StringBuilder("[");
            for (int i = 0; i < arr.size(); i++) {
                if (i > 0) {
                    s.append(',');
                }
                s.append(canonValue(arr.get(i)));
            }
            return s.append(']').toString();
        }
        if (b instanceof COSDictionary) {
            return canonDict((COSDictionary) b);
        }
        if (b == null) {
            return "NULL";
        }
        return "COS:" + b.getClass().getSimpleName();
    }

    static String canonFloat(float f) {
        if (Float.isNaN(f)) {
            return "nan";
        }
        if (Float.isInfinite(f)) {
            return f > 0 ? "inf" : "-inf";
        }
        java.math.BigDecimal bd = new java.math.BigDecimal(Float.toString(f))
                .setScale(5, java.math.RoundingMode.HALF_EVEN)
                .stripTrailingZeros();
        String s = bd.toPlainString();
        if (s.equals("-0")) {
            s = "0";
        }
        return s;
    }

    private static String hex(byte[] data) {
        StringBuilder s = new StringBuilder(data.length * 2);
        for (byte v : data) {
            s.append(Character.forDigit((v >> 4) & 0xF, 16));
            s.append(Character.forDigit(v & 0xF, 16));
        }
        return s.toString();
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        Arrays.stream(names)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(name -> runCase(dir, name));
    }

    private PropertyListFuzzProbe() {
    }
}
