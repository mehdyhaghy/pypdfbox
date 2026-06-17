import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Calendar;
import java.util.List;
import org.apache.xmpbox.XMPMetadata;
import org.apache.xmpbox.schema.AdobePDFSchema;
import org.apache.xmpbox.schema.DublinCoreSchema;
import org.apache.xmpbox.schema.PDFAIdentificationSchema;
import org.apache.xmpbox.schema.XMPBasicSchema;
import org.apache.xmpbox.xml.DomXmpParser;

/**
 * Live oracle probe: emit Apache xmpbox's typed schema property values for a
 * raw XMP packet read from a file.
 *
 * Usage: java -cp <xmpbox.jar>:<build> XmpSchemaProbe packet.xmp
 *
 * Output: canonical "schema.prop = value" lines, UTF-8, to stdout. One line per
 * present property. A schema or property that is absent is OMITTED entirely
 * (the pypdfbox side mirrors this — absent => the line is not emitted). Multi-
 * valued Seq/Bag properties join their items with a US (0x1f) separator so the
 * payload itself can contain commas. Calendar dates are rendered with a fixed
 * canonical formatter (see fmtCalendar) so Java's Calendar and pypdfbox's
 * datetime compare repr-independently.
 */
public final class XmpSchemaProbe {
    // ASCII unit separator — unlikely inside XMP text values, used to join lists.
    private static final char US = (char) 0x1f;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] bytes = Files.readAllBytes(Paths.get(args[0]));
        DomXmpParser parser = new DomXmpParser();
        // Optional second arg "lenient" toggles off strict parsing so a packet
        // carrying an undefined-namespace property still yields the typed
        // values for the schemas xmpbox does recognise. Default = strict (the
        // upstream DomXmpParser default), which throws on undefined namespaces.
        if (args.length > 1 && "lenient".equals(args[1])) {
            parser.setStrictParsing(false);
        }
        XMPMetadata meta = parser.parse(bytes);

        DublinCoreSchema dc = meta.getDublinCoreSchema();
        if (dc != null) {
            emit(out, "dc.title", dc.getTitle());
            emit(out, "dc.description", dc.getDescription());
            emitList(out, "dc.creators", dc.getCreators());
            emitCalendars(out, "dc.dates", dc.getDates());
            emitList(out, "dc.subjects", dc.getSubjects());
        }

        XMPBasicSchema xb = meta.getXMPBasicSchema();
        if (xb != null) {
            emit(out, "xmp.creatorTool", xb.getCreatorTool());
            emitCalendar(out, "xmp.createDate", xb.getCreateDate());
            emitCalendar(out, "xmp.modifyDate", xb.getModifyDate());
        }

        AdobePDFSchema ap = meta.getAdobePDFSchema();
        if (ap != null) {
            emit(out, "pdf.producer", ap.getProducer());
            emit(out, "pdf.keywords", ap.getKeywords());
            emit(out, "pdf.pdfVersion", ap.getPDFVersion());
        }

        PDFAIdentificationSchema pa = meta.getPDFAIdentificationSchema();
        if (pa != null) {
            Integer part = pa.getPart();
            if (part != null) {
                out.print("pdfaid.part = " + part + "\n");
            }
            emit(out, "pdfaid.conformance", pa.getConformance());
        }
    }

    private static void emit(PrintStream out, String key, String value) {
        if (value != null) {
            out.print(key + " = " + value + "\n");
        }
    }

    private static void emitList(PrintStream out, String key, List<String> values) {
        if (values != null) {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < values.size(); i++) {
                if (i > 0) {
                    sb.append(US);
                }
                sb.append(values.get(i));
            }
            out.print(key + " = " + sb + "\n");
        }
    }

    private static void emitCalendar(PrintStream out, String key, Calendar cal) {
        if (cal != null) {
            out.print(key + " = " + fmtCalendar(cal) + "\n");
        }
    }

    private static void emitCalendars(PrintStream out, String key, List<Calendar> cals) {
        if (cals != null) {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < cals.size(); i++) {
                if (i > 0) {
                    sb.append(US);
                }
                sb.append(fmtCalendar(cals.get(i)));
            }
            out.print(key + " = " + sb + "\n");
        }
    }

    /**
     * Canonical instant rendering: absolute epoch milliseconds plus the zone
     * offset in minutes, e.g. "1621968572000@120". Comparing the epoch instant
     * is repr-independent (no dependence on how each side formats the local
     * wall-clock string) while the explicit offset still distinguishes two
     * values that denote the same instant in different zones.
     */
    private static String fmtCalendar(Calendar cal) {
        long epochMillis = cal.getTimeInMillis();
        int offsetMinutes =
                (cal.get(Calendar.ZONE_OFFSET) + cal.get(Calendar.DST_OFFSET)) / 60000;
        return epochMillis + "@" + offsetMinutes;
    }
}
