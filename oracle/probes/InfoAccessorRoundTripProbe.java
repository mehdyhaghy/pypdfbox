import java.io.File;
import java.io.PrintStream;
import java.util.Calendar;
import java.util.GregorianCalendar;
import java.util.SimpleTimeZone;
import java.util.TimeZone;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;
import org.apache.pdfbox.pdmodel.PDPage;

/**
 * Live oracle probe for the {@code PDDocumentInformation} ACCESSOR /
 * round-trip surface: drive Apache PDFBox to SET every standard /Info field
 * (plus a custom key and a timezone-bearing date via the typed
 * {@code setCreationDate(Calendar)} / {@code setModificationDate(Calendar)}
 * setters), {@code save} the document, reload it, and emit everything PDFBox
 * reads back through its own accessors.
 *
 * This is distinct from MetaProbe / InfoXmpProbe (read-only on fixtures) and
 * from ProducerSaveProbe (the writer's null-stamping save contract): here the
 * setters and the date FORMATTING path are exercised end-to-end and verified
 * through the typed getters after a real serialise → parse cycle.
 *
 * Usage: java -cp ... InfoAccessorRoundTripProbe &lt;outPath&gt;
 *
 * Canonical line-oriented output (UTF-8, stdout, no framing):
 *   Title=&lt;value-or-NULL&gt;
 *   Author=...
 *   Subject=...
 *   Keywords=...
 *   Creator=...
 *   Producer=...
 *   Trapped=&lt;value-or-NULL&gt;            (getTrapped, String)
 *   CreationDate=&lt;epoch-millis@offset-min-or-NULL&gt;   (typed Calendar getter)
 *   ModDate=&lt;epoch-millis@offset-min-or-NULL&gt;
 *   CreationDateRaw=&lt;raw COSString-or-NULL&gt;          (the stored D:... bytes)
 *   ModDateRaw=&lt;raw COSString-or-NULL&gt;
 *   custom.AppBuild=&lt;value-or-NULL&gt;     (getCustomMetadataValue)
 *   custom.Reviewer=&lt;value-or-NULL&gt;
 *   keys=&lt;sorted-key-list joined by US 0x1f&gt;        (getMetadataKeys, sorted)
 *
 * Date normalisation: typed dates render as "&lt;epoch-millis&gt;@&lt;offset-min&gt;"
 * so Java's Calendar and pypdfbox's datetime compare repr-independently. The
 * raw lines additionally pin the exact stored byte form the setter produced,
 * so a divergence in date FORMATTING (e.g. Z vs +00'00') is caught too.
 */
public final class InfoAccessorRoundTripProbe {

    private static final char US = (char) 0x1f;

    private static String nz(String v) {
        return v == null ? "NULL" : v;
    }

    private static String fmtCalendar(Calendar c) {
        if (c == null) {
            return "NULL";
        }
        long epochMillis = c.getTimeInMillis();
        int offsetMinutes =
                (c.get(Calendar.ZONE_OFFSET) + c.get(Calendar.DST_OFFSET)) / 60000;
        return epochMillis + "@" + offsetMinutes;
    }

    private static String rawDate(PDDocumentInformation info, String key) {
        COSBase base = info.getCOSObject().getDictionaryObject(COSName.getPDFName(key));
        if (base instanceof COSString cs) {
            return cs.getString();
        }
        return "NULL";
    }

    private static Calendar at(long epochMillis, int offsetMinutes) {
        TimeZone tz = new SimpleTimeZone(offsetMinutes * 60 * 1000, "FIXED");
        GregorianCalendar cal = new GregorianCalendar(tz);
        cal.setTimeInMillis(epochMillis);
        return cal;
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File outFile = new File(args[0]);

        try (PDDocument doc = new PDDocument()) {
            doc.addPage(new PDPage());
            PDDocumentInformation info = doc.getDocumentInformation();
            info.setTitle("Round-Trip Title éè");
            info.setAuthor("Ada Lovelace");
            info.setSubject("Differential parity");
            info.setKeywords("pdf, info, oracle");
            info.setCreator("InfoAccessorRoundTripProbe");
            info.setProducer("pypdfbox-oracle");
            info.setTrapped("True");
            // A creation date east of UTC and a mod date west of UTC, so the
            // explicit offset is carried both ways through the formatter.
            info.setCreationDate(at(1700000000000L, 120));
            info.setModificationDate(at(1700003600000L, -300));
            info.setCustomMetadataValue("AppBuild", "42.7");
            info.setCustomMetadataValue("Reviewer", "M. Haghy");
            doc.save(outFile);
        }

        try (PDDocument doc = Loader.loadPDF(outFile)) {
            PDDocumentInformation info = doc.getDocumentInformation();
            out.println("Title=" + nz(info.getTitle()));
            out.println("Author=" + nz(info.getAuthor()));
            out.println("Subject=" + nz(info.getSubject()));
            out.println("Keywords=" + nz(info.getKeywords()));
            out.println("Creator=" + nz(info.getCreator()));
            out.println("Producer=" + nz(info.getProducer()));
            out.println("Trapped=" + nz(info.getTrapped()));
            out.println("CreationDate=" + fmtCalendar(info.getCreationDate()));
            out.println("ModDate=" + fmtCalendar(info.getModificationDate()));
            out.println("CreationDateRaw=" + rawDate(info, "CreationDate"));
            out.println("ModDateRaw=" + rawDate(info, "ModDate"));
            out.println("custom.AppBuild=" + nz(info.getCustomMetadataValue("AppBuild")));
            out.println("custom.Reviewer=" + nz(info.getCustomMetadataValue("Reviewer")));

            String[] keys = info.getMetadataKeys().toArray(new String[0]);
            java.util.Arrays.sort(keys);
            StringBuilder kb = new StringBuilder();
            for (int i = 0; i < keys.length; i++) {
                if (i > 0) {
                    kb.append(US);
                }
                kb.append(keys[i]);
            }
            out.println("keys=" + kb);
        }
    }
}
