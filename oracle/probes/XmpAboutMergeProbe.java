import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.apache.xmpbox.XMPMetadata;
import org.apache.xmpbox.schema.DublinCoreSchema;
import org.apache.xmpbox.xml.DomXmpParser;

/**
 * Live oracle probe for the {@code rdf:about} merge corner: how Apache xmpbox
 * 3.0.7's {@code DomXmpParser} folds <em>several</em> {@code rdf:Description}
 * blocks that share one namespace but declare <em>different</em>
 * {@code rdf:about} values.
 *
 * <p>Reads the packet at {@code args[0]} and prints a canonical JSON projection
 * of the merged Dublin Core schema: the schema count (must collapse to one DC
 * schema), the surviving {@code rdf:about} value (xmpbox keeps the first), and
 * the union of the properties that landed across the split blocks. The pypdfbox
 * test parses the same bytes and asserts an identical projection, pinning that
 * both parsers merge same-namespace Descriptions and keep the first about.
 *
 * Usage: {@code java -cp ... XmpAboutMergeProbe packet.xmp}
 */
public final class XmpAboutMergeProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] bytes = Files.readAllBytes(Paths.get(args[0]));
        XMPMetadata meta = new DomXmpParser().parse(bytes);

        TreeMap<String, Object> root = new TreeMap<>();
        root.put("schema_count", meta.getAllSchemas().size());

        DublinCoreSchema dc = meta.getDublinCoreSchema();
        if (dc != null) {
            root.put("about", dc.getAboutValue());
            TreeMap<String, Object> dcMap = new TreeMap<>();
            if (dc.getFormat() != null) {
                dcMap.put("format", dc.getFormat());
            }
            List<String> creators = dc.getCreators();
            if (creators != null && !creators.isEmpty()) {
                dcMap.put("creator", creators);
            }
            String title = dc.getTitle();
            if (title != null) {
                dcMap.put("title", title);
            }
            root.put("dc", dcMap);
        }

        out.print(jsonify(root));
    }

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
