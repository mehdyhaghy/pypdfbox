import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Calendar;
import java.util.GregorianCalendar;
import java.util.List;
import java.util.Map;
import java.util.TimeZone;
import java.util.TreeMap;
import org.apache.xmpbox.XMPMetadata;
import org.apache.xmpbox.schema.AdobePDFSchema;
import org.apache.xmpbox.schema.DublinCoreSchema;
import org.apache.xmpbox.schema.PDFAIdentificationSchema;
import org.apache.xmpbox.schema.PhotoshopSchema;
import org.apache.xmpbox.schema.XMPBasicSchema;
import org.apache.xmpbox.type.AbstractField;
import org.apache.xmpbox.type.ArrayProperty;
import org.apache.xmpbox.type.TextType;
import org.apache.xmpbox.xml.XmpSerializer;

/**
 * Reverse-direction live oracle probe: <em>Apache xmpbox 3.0.7 writes the
 * packet, pypdfbox reads it</em>. The existing xmpbox oracle probes
 * ({@code XmpRoundTripProbe}, {@code XmpDublinCoreProbe},
 * {@code XmpSchemaProbe}) all ingest a packet that <em>pypdfbox</em> emitted;
 * none exercise the opposite — that pypdfbox's {@code DomXmpParser} reads back
 * a packet produced by xmpbox's own {@code XmpSerializer} identically.
 *
 * <p>This probe builds a fixed multi-schema document, serializes it with
 * {@code XmpSerializer.serialize(meta, os, withXpacket=true)} to the path given
 * as {@code args[0]} (so the pypdfbox side parses the exact bytes xmpbox
 * wrote), and prints a canonical JSON projection of the same property values to
 * stdout. The Python test parses the file with pypdfbox's {@code DomXmpParser},
 * builds the matching projection, and asserts equality.
 *
 * <p>Date instants render as {@code epochMillis@offsetMinutes} (absolute
 * instant + explicit zone offset), repr-independent of wall-clock formatting.
 * LangAlt blocks render as {@code {lang: value}} maps so rdf:li ordering does
 * not affect equality; the {@code title_order} list captures the emitted lang
 * order separately so the test can pin that xmpbox writes x-default first.
 *
 * Usage: {@code java -cp ... XmpReverseSerializeProbe /path/to/out.xmp}
 */
public final class XmpReverseSerializeProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        XMPMetadata meta = XMPMetadata.createXMPMetadata();

        DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
        dc.addTitle("x-default", "Hello");
        dc.addTitle("en", "Hello");
        dc.addTitle("fr", "Bonjour");
        dc.addTitle("ja", "こんにちは");
        dc.setDescription("A reverse-direction sample.");
        dc.addCreator("Alice");
        dc.addCreator("Bob");
        dc.addSubject("安全");
        dc.addSubject("PDF");
        dc.addSubject("café");
        dc.setFormat("application/pdf");

        XMPBasicSchema xb = meta.createAndAddXMPBasicSchema();
        xb.setCreatorTool("xmpbox");
        xb.setCreateDate(cal(2024, 6, 1, 10, 30, 0, 0));
        xb.setModifyDate(cal(2023, 11, 15, 9, 45, 30, 120));

        AdobePDFSchema ap = meta.createAndAddAdobePDFSchema();
        ap.setProducer("xmpbox/test");
        ap.setKeywords("k1, k2");
        ap.setPDFVersion("1.7");

        PDFAIdentificationSchema pa = meta.createAndAddPDFAIdentificationSchema();
        pa.setPart(3);
        pa.setConformance("B");

        PhotoshopSchema ps = meta.createAndAddPhotoshopSchema();
        ps.setCity("Berlin");
        ps.setAuthorsPosition("Editor");

        XmpSerializer serializer = new XmpSerializer();
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        serializer.serialize(meta, baos, true);
        byte[] packet = baos.toByteArray();
        Files.write(Paths.get(args[0]), packet);

        TreeMap<String, Object> root = new TreeMap<>();
        root.put("schema_count", meta.getAllSchemas().size());

        TreeMap<String, Object> dcMap = new TreeMap<>();
        putLangAlt(dcMap, "title", dc.getTitleProperty());
        root.put("title_order", langOrder(dc.getTitleProperty()));
        putLangAlt(dcMap, "description", dc.getDescriptionProperty());
        putList(dcMap, "creator", dc.getCreators());
        putList(dcMap, "subject", dc.getSubjects());
        putString(dcMap, "format", dc.getFormat());
        root.put("dc", dcMap);

        TreeMap<String, Object> xbMap = new TreeMap<>();
        putString(xbMap, "creatorTool", xb.getCreatorTool());
        putCalendar(xbMap, "createDate", xb.getCreateDate());
        putCalendar(xbMap, "modifyDate", xb.getModifyDate());
        root.put("xmp", xbMap);

        TreeMap<String, Object> apMap = new TreeMap<>();
        putString(apMap, "producer", ap.getProducer());
        putString(apMap, "keywords", ap.getKeywords());
        putString(apMap, "pdfVersion", ap.getPDFVersion());
        root.put("pdf", apMap);

        TreeMap<String, Object> paMap = new TreeMap<>();
        Integer part = pa.getPart();
        if (part != null) {
            paMap.put("part", part);
        }
        putString(paMap, "conformance", pa.getConformance());
        root.put("pdfaid", paMap);

        TreeMap<String, Object> psMap = new TreeMap<>();
        putString(psMap, "city", ps.getCity());
        putString(psMap, "authorsPosition", ps.getAuthorsPosition());
        root.put("photoshop", psMap);

        out.print(jsonify(root));
    }

    private static Calendar cal(
            int y, int mo, int d, int h, int mi, int s, int offsetMinutes) {
        int millis = offsetMinutes * 60000;
        TimeZone tz = new java.util.SimpleTimeZone(millis, "X");
        GregorianCalendar c = new GregorianCalendar(tz);
        c.clear();
        c.set(y, mo - 1, d, h, mi, s);
        return c;
    }

    private static void putString(Map<String, Object> map, String key, String value) {
        if (value != null) {
            map.put(key, value);
        }
    }

    private static void putList(Map<String, Object> map, String key, List<String> values) {
        if (values != null && !values.isEmpty()) {
            map.put(key, values);
        }
    }

    private static void putCalendar(Map<String, Object> map, String key, Calendar cal) {
        if (cal != null) {
            map.put(key, fmtCalendar(cal));
        }
    }

    private static void putLangAlt(Map<String, Object> map, String key, ArrayProperty arr) {
        if (arr == null) {
            return;
        }
        TreeMap<String, String> langs = new TreeMap<>();
        for (AbstractField field : arr.getContainer().getAllProperties()) {
            if (field instanceof TextType tt) {
                String lang = "x-default";
                if (tt.getAttribute("lang") != null) {
                    lang = tt.getAttribute("lang").getValue();
                }
                langs.put(lang, tt.getStringValue());
            }
        }
        if (!langs.isEmpty()) {
            map.put(key, langs);
        }
    }

    private static java.util.ArrayList<String> langOrder(ArrayProperty arr) {
        java.util.ArrayList<String> order = new java.util.ArrayList<>();
        if (arr == null) {
            return order;
        }
        for (AbstractField field : arr.getContainer().getAllProperties()) {
            if (field instanceof TextType tt) {
                String lang = "x-default";
                if (tt.getAttribute("lang") != null) {
                    lang = tt.getAttribute("lang").getValue();
                }
                order.add(lang);
            }
        }
        return order;
    }

    private static String fmtCalendar(Calendar cal) {
        long epochMillis = cal.getTimeInMillis();
        int offsetMinutes =
                (cal.get(Calendar.ZONE_OFFSET) + cal.get(Calendar.DST_OFFSET)) / 60000;
        return epochMillis + "@" + offsetMinutes;
    }

    // --- minimal JSON emitter (TreeMap / List / String / Number) ---

    private static String jsonify(Object value) {
        StringBuilder sb = new StringBuilder();
        emit(sb, value);
        return sb.toString();
    }

    private static void emit(StringBuilder sb, Object value) {
        if (value == null) {
            sb.append("null");
        } else if (value instanceof Map<?, ?> map) {
            sb.append("{");
            boolean first = true;
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                if (!first) {
                    sb.append(",");
                }
                first = false;
                emitString(sb, String.valueOf(entry.getKey()));
                sb.append(":");
                emit(sb, entry.getValue());
            }
            sb.append("}");
        } else if (value instanceof List<?> list) {
            sb.append("[");
            for (int i = 0; i < list.size(); i++) {
                if (i > 0) {
                    sb.append(",");
                }
                emit(sb, list.get(i));
            }
            sb.append("]");
        } else if (value instanceof Number || value instanceof Boolean) {
            sb.append(value.toString());
        } else {
            emitString(sb, value.toString());
        }
    }

    private static void emitString(StringBuilder sb, String s) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\b': sb.append("\\b"); break;
                case '\f': sb.append("\\f"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
    }
}
