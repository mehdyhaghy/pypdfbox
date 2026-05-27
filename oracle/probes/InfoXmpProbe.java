import java.io.File;
import java.io.PrintStream;
import java.util.Calendar;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;
import org.apache.pdfbox.pdmodel.common.PDMetadata;
import org.apache.xmpbox.XMPMetadata;
import org.apache.xmpbox.schema.AdobePDFSchema;
import org.apache.xmpbox.schema.DublinCoreSchema;
import org.apache.xmpbox.schema.XMPBasicSchema;
import org.apache.xmpbox.xml.DomXmpParser;

/**
 * Live oracle probe: emit Apache PDFBox's view of BOTH the trailer /Info
 * document-information dictionary AND the catalog /Metadata XMP packet for the
 * same PDF, so a test can confirm each accessor reads its own source (PDFBox
 * does NOT auto-sync the two).
 *
 * Usage: java -cp <pdfbox-app.jar>:<xmpbox.jar>:<build> InfoXmpProbe input.pdf
 *
 * Canonical, line-oriented output (UTF-8, stdout, no framing):
 *   info Title=<value-or-NULL>          (the eight standard /Info getters)
 *   info Author=...
 *   info Subject=...
 *   info Keywords=...
 *   info Creator=...
 *   info Producer=...
 *   info CreationDate=<epoch-millis@offset-min-or-NULL>   (typed Calendar getter)
 *   info ModDate=<epoch-millis@offset-min-or-NULL>
 *   info custom.<key>=<value-or-NULL>   (a custom /Info key read via getCustomMetadataValue)
 *   info keys=<sorted-key-list joined by US 0x1f>  (getMetadataKeys, sorted)
 *   xmp dc.title=<value-or-NULL>        (parsed via DomXmpParser -> DublinCoreSchema)
 *   xmp dc.creator=<seq joined by US-or-NULL>
 *   xmp xmp.createDate=<epoch-millis@offset-min-or-NULL>  (XMPBasicSchema)
 *   xmp pdf.producer=<value-or-NULL>    (AdobePDFSchema)
 *
 * Date normalisation: /Info dates come from the typed getCreationDate() /
 * getModificationDate() Calendar getters; XMP dates from the typed
 * getCreateDate() Calendar getter. Both render as "<epoch-millis>@<offset-min>"
 * (absolute instant + zone offset in minutes) so Java's Calendar and pypdfbox's
 * datetime compare repr-independently. The python side mirrors this exactly.
 */
public final class InfoXmpProbe {

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

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            // ---- /Info document-information dictionary ----
            PDDocumentInformation info = doc.getDocumentInformation();
            out.println("info Title=" + nz(info.getTitle()));
            out.println("info Author=" + nz(info.getAuthor()));
            out.println("info Subject=" + nz(info.getSubject()));
            out.println("info Keywords=" + nz(info.getKeywords()));
            out.println("info Creator=" + nz(info.getCreator()));
            out.println("info Producer=" + nz(info.getProducer()));
            out.println("info CreationDate=" + fmtCalendar(info.getCreationDate()));
            out.println("info ModDate=" + fmtCalendar(info.getModificationDate()));
            out.println("info custom.AppBuild=" + nz(info.getCustomMetadataValue("AppBuild")));

            // getMetadataKeys returns a Set<String>; sort for a canonical line.
            String[] keys = info.getMetadataKeys().toArray(new String[0]);
            java.util.Arrays.sort(keys);
            StringBuilder kb = new StringBuilder();
            for (int i = 0; i < keys.length; i++) {
                if (i > 0) {
                    kb.append(US);
                }
                kb.append(keys[i]);
            }
            out.println("info keys=" + kb);

            // ---- catalog /Metadata XMP packet ----
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDMetadata metadata = catalog.getMetadata();
            if (metadata == null) {
                out.println("xmp NONE");
            } else {
                byte[] packet = metadata.exportXMPMetadata().readAllBytes();
                DomXmpParser parser = new DomXmpParser();
                XMPMetadata meta = parser.parse(packet);

                String dcTitle = null;
                String dcCreator = null;
                DublinCoreSchema dc = meta.getDublinCoreSchema();
                if (dc != null) {
                    dcTitle = dc.getTitle();
                    List<String> creators = dc.getCreators();
                    if (creators != null) {
                        StringBuilder cb = new StringBuilder();
                        for (int i = 0; i < creators.size(); i++) {
                            if (i > 0) {
                                cb.append(US);
                            }
                            cb.append(creators.get(i));
                        }
                        dcCreator = cb.toString();
                    }
                }
                out.println("xmp dc.title=" + nz(dcTitle));
                out.println("xmp dc.creator=" + nz(dcCreator));

                Calendar createDate = null;
                XMPBasicSchema xb = meta.getXMPBasicSchema();
                if (xb != null) {
                    createDate = xb.getCreateDate();
                }
                out.println("xmp xmp.createDate=" + fmtCalendar(createDate));

                String pdfProducer = null;
                AdobePDFSchema ap = meta.getAdobePDFSchema();
                if (ap != null) {
                    pdfProducer = ap.getProducer();
                }
                out.println("xmp pdf.producer=" + nz(pdfProducer));
            }
        }
    }
}
