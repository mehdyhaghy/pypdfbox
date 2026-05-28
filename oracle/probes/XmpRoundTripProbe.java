import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Calendar;
import java.util.List;
import java.util.Map;
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
import org.apache.xmpbox.xml.DomXmpParser;

/**
 * Live oracle probe: write XMP via pypdfbox and verify Apache xmpbox 3.0.7's
 * <code>DomXmpParser</code> can read every schema property back identically.
 *
 * Usage: java -cp ... XmpRoundTripProbe packet.xmp [lenient]
 *
 * Output: a single JSON object summarising every schema's parsed values in a
 * canonical, repr-independent form. Absent fields are omitted entirely; the
 * Python side mirrors the same emit rules so the test compares apples to
 * apples.
 *
 * Dates are rendered as <code>epochMillis@offsetMinutes</code> so the
 * representation captures the absolute instant plus the explicit timezone
 * offset, while remaining independent of how either side formats the
 * wall-clock string. The "lenient" flag turns off strict parsing so
 * properties whose namespace lacks a registered xmpbox type (e.g.
 * <code>pdf:Trapped</code>) are surfaced through the generic Description
 * children rather than rejected.
 */
public final class XmpRoundTripProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] bytes = Files.readAllBytes(Paths.get(args[0]));
        DomXmpParser parser = new DomXmpParser();
        if (args.length > 1 && "lenient".equals(args[1])) {
            parser.setStrictParsing(false);
        }
        XMPMetadata meta = parser.parse(bytes);

        TreeMap<String, Object> root = new TreeMap<>();
        root.put("schema_count", meta.getAllSchemas().size());

        DublinCoreSchema dc = meta.getDublinCoreSchema();
        if (dc != null) {
            TreeMap<String, Object> dcMap = new TreeMap<>();
            putLangAlt(dcMap, "title", dc.getTitleProperty());
            putLangAlt(dcMap, "description", dc.getDescriptionProperty());
            putLangAlt(dcMap, "rights", dc.getRightsProperty());
            putList(dcMap, "creator", dc.getCreators());
            putList(dcMap, "subject", dc.getSubjects());
            putString(dcMap, "format", dc.getFormat());
            if (!dcMap.isEmpty()) {
                root.put("dc", dcMap);
            }
        }

        XMPBasicSchema xb = meta.getXMPBasicSchema();
        if (xb != null) {
            TreeMap<String, Object> xbMap = new TreeMap<>();
            putString(xbMap, "creatorTool", xb.getCreatorTool());
            putCalendar(xbMap, "createDate", xb.getCreateDate());
            putCalendar(xbMap, "modifyDate", xb.getModifyDate());
            putCalendar(xbMap, "metadataDate", xb.getMetadataDate());
            if (!xbMap.isEmpty()) {
                root.put("xmp", xbMap);
            }
        }

        AdobePDFSchema ap = meta.getAdobePDFSchema();
        if (ap != null) {
            TreeMap<String, Object> apMap = new TreeMap<>();
            putString(apMap, "producer", ap.getProducer());
            putString(apMap, "keywords", ap.getKeywords());
            putString(apMap, "pdfVersion", ap.getPDFVersion());
            // Trapped is not a registered typed property on xmpbox's
            // AdobePDFSchema — surface it through the generic property bag
            // when lenient parsing kept it in the tree.
            String trapped = ap.getUnqualifiedTextPropertyValue("Trapped");
            if (trapped != null) {
                apMap.put("trapped", trapped);
            }
            if (!apMap.isEmpty()) {
                root.put("pdf", apMap);
            }
        }

        PDFAIdentificationSchema pa = meta.getPDFAIdentificationSchema();
        if (pa != null) {
            TreeMap<String, Object> paMap = new TreeMap<>();
            Integer part = pa.getPart();
            if (part != null) {
                paMap.put("part", part);
            }
            putString(paMap, "conformance", pa.getConformance());
            if (!paMap.isEmpty()) {
                root.put("pdfaid", paMap);
            }
        }

        PhotoshopSchema ps = meta.getPhotoshopSchema();
        if (ps != null) {
            TreeMap<String, Object> psMap = new TreeMap<>();
            putString(psMap, "city", ps.getCity());
            putString(psMap, "authorsPosition", ps.getAuthorsPosition());
            putString(psMap, "dateCreated", ps.getDateCreated());
            if (!psMap.isEmpty()) {
                root.put("photoshop", psMap);
            }
        }

        out.print(jsonify(root));
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
        // LangAlt entries are TextType children with xml:lang attributes.
        // Emit a TreeMap of lang -> value so the JSON has a stable order.
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

    // --- minimal JSON emitter (TreeMap / List / String / Integer / Long only) ---

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
        } else if (value instanceof Number) {
            sb.append(value.toString());
        } else if (value instanceof Boolean) {
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
