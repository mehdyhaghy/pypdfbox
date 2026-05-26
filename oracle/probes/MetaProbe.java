import java.io.File;
import java.io.PrintStream;
import java.security.MessageDigest;
import java.util.Calendar;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;
import org.apache.pdfbox.pdmodel.common.PDMetadata;
import org.apache.pdfbox.pdmodel.common.PDPageLabels;

/**
 * Live oracle probe: emit Apache PDFBox's document-metadata view of a PDF.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> MetaProbe input.pdf
 *
 * Emits canonical, line-oriented output (UTF-8, stdout, no framing):
 *   info Title=<value-or-NULL>            (one line per standard /Info key)
 *   info Author=...
 *   info Subject=...
 *   info Keywords=...
 *   info Creator=...
 *   info Producer=...
 *   info CreationDate=<ISO-8601-or-NULL>  (normalised from the Calendar getter)
 *   info ModDate=<ISO-8601-or-NULL>
 *   label <page-index>=<computed-page-label>   (one per page; absent => omitted)
 *   xmp NONE                                    OR
 *   xmp <byte-length> <sha1-hex>
 *
 * Date normalisation: dates are read via the typed getCreationDate() /
 * getModificationDate() Calendar getters and rendered as
 * "YYYY-MM-DDTHH:MM:SS+HH:MM" (offset in minutes, "Z"-less). The python side
 * mirrors this exact normalisation so the comparison is representation-agnostic
 * while still exercising the real date-parsing getters on both sides.
 */
public final class MetaProbe {

    private static String nz(String v) {
        return v == null ? "NULL" : v;
    }

    private static String isoDate(Calendar c) {
        if (c == null) {
            return "NULL";
        }
        int offMillis = c.get(Calendar.ZONE_OFFSET) + c.get(Calendar.DST_OFFSET);
        int offMin = offMillis / 60000;
        char sign = offMin < 0 ? '-' : '+';
        int absMin = Math.abs(offMin);
        return String.format(
            "%04d-%02d-%02dT%02d:%02d:%02d%c%02d:%02d",
            c.get(Calendar.YEAR),
            c.get(Calendar.MONTH) + 1,
            c.get(Calendar.DAY_OF_MONTH),
            c.get(Calendar.HOUR_OF_DAY),
            c.get(Calendar.MINUTE),
            c.get(Calendar.SECOND),
            sign,
            absMin / 60,
            absMin % 60);
    }

    private static String sha1Hex(byte[] data) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-1");
        byte[] digest = md.digest(data);
        StringBuilder sb = new StringBuilder(digest.length * 2);
        for (byte b : digest) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentInformation info = doc.getDocumentInformation();
            out.println("info Title=" + nz(info.getTitle()));
            out.println("info Author=" + nz(info.getAuthor()));
            out.println("info Subject=" + nz(info.getSubject()));
            out.println("info Keywords=" + nz(info.getKeywords()));
            out.println("info Creator=" + nz(info.getCreator()));
            out.println("info Producer=" + nz(info.getProducer()));
            out.println("info CreationDate=" + isoDate(info.getCreationDate()));
            out.println("info ModDate=" + isoDate(info.getModificationDate()));

            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDPageLabels labels = catalog.getPageLabels();
            if (labels != null) {
                String[] byIndex = labels.getLabelsByPageIndices();
                for (int i = 0; i < byIndex.length; i++) {
                    out.println("label " + i + "=" + nz(byIndex[i]));
                }
            }

            PDMetadata metadata = catalog.getMetadata();
            if (metadata == null) {
                out.println("xmp NONE");
            } else {
                byte[] packet = metadata.exportXMPMetadata().readAllBytes();
                out.println("xmp " + packet.length + " " + sha1Hex(packet));
            }
        }
    }
}
