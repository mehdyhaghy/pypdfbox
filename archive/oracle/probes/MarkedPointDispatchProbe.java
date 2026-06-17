import java.io.File;
import java.io.IOException;
import java.io.PrintStream;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.markedcontent.MarkedContentPoint;
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
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe: the MARKED-POINT facet (MP / DP) at the engine-dispatch
 * level. Builds a one-page PDF whose content stream carries MP and DP operators
 * (bare tag, inline property dict, named /Properties resource reference,
 * unresolvable named reference), saves it to args[0], then re-loads it and runs
 * a PDFStreamEngine subclass that overrides markedContentPoint(tag, properties)
 * to record every dispatched mark point. The recorded callback sequence — tag
 * plus the *resolved* property list (named refs resolved against the page's
 * /Properties resource frame) — is emitted line-for-line so pypdfbox can drive
 * its own PDFStreamEngine over the identical saved bytes and compare.
 *
 * This complements MarkedContentProbe (which tokenizes MP/DP at the parser
 * level and never resolves a named /Properties reference) by exercising the
 * operator processors' process() dispatch AND the named-property resolution.
 *
 * Usage:
 *   java -cp ... MarkedPointDispatchProbe out.pdf
 *
 * Canonical line grammar (one mark point per line, UTF-8):
 *   MP /<tag>
 *   DP /<tag> <propsValue>
 * where <propsValue> is:
 *   <none>             properties resolved to null
 *   { k=<v> ; ... }    a resolved property dictionary, keys sorted
 * value grammar shared with TokenizeProbe / MarkedContentProbe:
 *   INT:<n> REAL:<canon> NAME:/<n> STR:<hex> BOOL:.. NULL [..] {..}
 */
public final class MarkedPointDispatchProbe {

    /** Engine that records every markedContentPoint dispatch. */
    static final class RecordingEngine extends PDFStreamEngine {
        final StringBuilder sb = new StringBuilder();

        RecordingEngine() {
            addOperator(new MarkedContentPoint(this));
            addOperator(new MarkedContentPointWithProperties(this));
        }

        @Override
        public void markedContentPoint(COSName tag, COSDictionary properties) {
            if (properties == null) {
                sb.append("MP /").append(tag == null ? "<none>" : tag.getName())
                        .append('\n');
            } else {
                sb.append("DP /").append(tag == null ? "<none>" : tag.getName())
                        .append(' ').append(canonDict(properties)).append('\n');
            }
        }
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File outFile = new File(args[0]);
        buildPdf(outFile);

        try (PDDocument doc = Loader.loadPDF(outFile)) {
            PDPage page = doc.getPage(0);
            RecordingEngine engine = new RecordingEngine();
            engine.processPage(page);
            out.print(engine.sb);
        }
    }

    /**
     * Build a one-page PDF with a /Properties resource and a content stream
     * exercising every MP / DP shape. Written at the COS level so the bytes
     * are deterministic and identical for the pypdfbox reproduction.
     */
    static void buildPdf(File outFile) throws IOException {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(new PDRectangle(0, 0, 200, 200));
            doc.addPage(page);

            // /Properties resource: /MC0 → a property dict with mixed value
            // types so the resolution + canonical rendering is well exercised.
            PDResources resources = new PDResources();
            COSDictionary mc0 = new COSDictionary();
            mc0.setItem(COSName.getPDFName("MCID"), COSInteger.get(7));
            mc0.setName("Type", "Pagination");
            mc0.setString("Title", "named-prop");
            COSArray bbox = new COSArray();
            bbox.add(COSFloat.get("1.5"));
            bbox.add(COSInteger.get(0));
            bbox.add(COSFloat.get("99.25"));
            bbox.add(COSInteger.get(-3));
            mc0.setItem(COSName.getPDFName("BBox"), bbox);
            resources.getCOSObject().setItem(COSName.PROPERTIES, properties(mc0));
            page.setResources(resources);

            byte[] content = ("/Pt1 MP\n"
                    + "/Pt2 << /MCID 1 /Title (inline) /Flag true >> DP\n"
                    + "/Pt3 /MC0 DP\n"
                    + "/Pt4 /Missing DP\n"
                    + "/Pt5 MP\n").getBytes("ISO-8859-1");
            COSStream stream = doc.getDocument().createCOSStream();
            try (java.io.OutputStream os = stream.createOutputStream()) {
                os.write(content);
            }
            page.setContents(new org.apache.pdfbox.pdmodel.common.PDStream(stream));
            doc.save(outFile);
        }
    }

    private static COSDictionary properties(COSDictionary mc0) {
        COSDictionary props = new COSDictionary();
        props.setItem(COSName.getPDFName("MC0"), mc0);
        return props;
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

    /** Locale-independent canonical float rendering (== TokenizeProbe). */
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

    private MarkedPointDispatchProbe() {
    }
}
