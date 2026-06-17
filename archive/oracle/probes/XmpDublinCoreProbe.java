import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Calendar;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.apache.xmpbox.XMPMetadata;
import org.apache.xmpbox.schema.DublinCoreSchema;
import org.apache.xmpbox.type.AbstractField;
import org.apache.xmpbox.type.ArrayProperty;
import org.apache.xmpbox.type.TextType;
import org.apache.xmpbox.xml.DomXmpParser;
import org.apache.xmpbox.xml.XmpSerializer;

/**
 * Live oracle probe focused on the Dublin Core schema round-trip.
 *
 * Usage: java -cp ... XmpDublinCoreProbe packet.xmp [roundtrip]
 *
 * Parses an XMP packet with Apache xmpbox 3.0.7's {@link DomXmpParser},
 * extracts the Dublin Core fields exercised by this parity surface, and
 * emits a canonical JSON object:
 *   - title:   {lang -> value}        (LangAlt)
 *   - creator: [name, ...]            (ordered Seq)
 *   - subject: [keyword, ...]         (Bag, source order as parsed)
 *   - date:    ["<epochMillis>@<offsetMinutes>", ...]  (Seq of dates)
 *
 * When the optional "roundtrip" arg is given, the parsed metadata is first
 * re-serialized through xmpbox's {@link XmpSerializer} and then re-parsed,
 * so the emitted values reflect a full xmpbox parse -> serialize -> parse
 * cycle. This lets the Python side assert pypdfbox matches xmpbox both on a
 * direct parse and after xmpbox's own serializer touches the packet.
 */
public final class XmpDublinCoreProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] bytes = Files.readAllBytes(Paths.get(args[0]));
        boolean roundtrip = args.length > 1 && "roundtrip".equals(args[1]);

        DomXmpParser parser = new DomXmpParser();
        XMPMetadata meta = parser.parse(bytes);

        if (roundtrip) {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            new XmpSerializer().serialize(meta, baos, true);
            meta = new DomXmpParser().parse(baos.toByteArray());
        }

        TreeMap<String, Object> root = new TreeMap<>();
        DublinCoreSchema dc = meta.getDublinCoreSchema();
        if (dc != null) {
            putLangAlt(root, "title", dc.getTitleProperty());
            putList(root, "creator", dc.getCreators());
            putList(root, "subject", dc.getSubjects());
            List<Calendar> dates = dc.getDates();
            if (dates != null && !dates.isEmpty()) {
                java.util.ArrayList<String> ds = new java.util.ArrayList<>();
                for (Calendar c : dates) {
                    ds.add(fmtCalendar(c));
                }
                root.put("date", ds);
            }
        }

        out.print(jsonify(root));
    }

    private static void putList(Map<String, Object> map, String key, List<String> values) {
        if (values != null && !values.isEmpty()) {
            map.put(key, values);
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

    private static String fmtCalendar(Calendar cal) {
        long epochMillis = cal.getTimeInMillis();
        int offsetMinutes =
                (cal.get(Calendar.ZONE_OFFSET) + cal.get(Calendar.DST_OFFSET)) / 60000;
        return epochMillis + "@" + offsetMinutes;
    }

    // --- minimal JSON emitter (TreeMap / List / String only) ---

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
