import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.apache.xmpbox.XMPMetadata;
import org.apache.xmpbox.schema.DublinCoreSchema;
import org.apache.xmpbox.type.AbstractField;
import org.apache.xmpbox.type.ArrayProperty;
import org.apache.xmpbox.type.TextType;
import org.apache.xmpbox.xml.DomXmpParser;

/**
 * Live oracle probe: emit the RDF <em>container kind</em> and ordered item
 * payload of Apache xmpbox's typed Dublin Core array properties, parsed from a
 * raw XMP packet read from a file.
 *
 * Usage: java -cp &lt;xmpbox.jar&gt;:&lt;build&gt; XmpArrayContainerProbe packet.xmp
 *
 * This is the array <strong>container-semantics</strong> surface — distinct
 * from the existing flattened-scalar probes (XmpSchemaProbe reads the first/
 * x-default value of each property; XmpRoundTripProbe compares serialized
 * round-trips). Here we reach through {@code getXxxProperty()} to the typed
 * {@link ArrayProperty} and emit:
 *
 * <ul>
 *   <li>the container kind via {@code getArrayType().name()} — distinguishing
 *       {@code Seq} (ordered: creator, dates) from {@code Bag} (unordered:
 *       subject, contributor, publisher, language, relation) from {@code Alt}
 *       (lang-alt: title, description, rights);</li>
 *   <li>the ordered item values via {@code getElementsAsString()} so a Seq vs
 *       Bag mis-classification or a reordering bug surfaces;</li>
 *   <li>for the {@code Alt} (lang-alt) properties, each {@code rdf:li}'s
 *       {@code xml:lang} qualifier paired with its value, in document order, so
 *       the qualifier round-trips and the x-default-first reorganisation is
 *       checked.</li>
 * </ul>
 *
 * Output: a single canonical JSON object. Each present array property maps to
 * either {"type": "Seq|Bag", "items": [...]} (plain arrays) or
 * {"type": "Alt", "langs": [["lang","value"], ...]} (lang-alt). Absent
 * properties are omitted entirely; the Python side mirrors these emit rules.
 */
public final class XmpArrayContainerProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] bytes = Files.readAllBytes(Paths.get(args[0]));
        DomXmpParser parser = new DomXmpParser();
        XMPMetadata meta = parser.parse(bytes);

        TreeMap<String, Object> root = new TreeMap<>();

        DublinCoreSchema dc = meta.getDublinCoreSchema();
        if (dc != null) {
            // Ordered (Seq) and unordered (Bag) plain-text arrays.
            putArray(root, "creator", dc.getCreatorsProperty());
            putArray(root, "subject", dc.getSubjectsProperty());
            putArray(root, "contributor", dc.getContributorsProperty());
            putArray(root, "publisher", dc.getPublishersProperty());
            putArray(root, "language", dc.getLanguagesProperty());
            putArray(root, "relation", dc.getRelationsProperty());
            putArray(root, "date", dc.getDatesProperty());
            // Lang-alt (Alt) arrays with per-item xml:lang qualifiers.
            putLangAlt(root, "title", dc.getTitleProperty());
            putLangAlt(root, "description", dc.getDescriptionProperty());
            putLangAlt(root, "rights", dc.getRightsProperty());
        }

        out.print(jsonify(root));
    }

    private static void putArray(Map<String, Object> map, String key, ArrayProperty arr) {
        if (arr == null) {
            return;
        }
        TreeMap<String, Object> entry = new TreeMap<>();
        entry.put("type", arr.getArrayType().name());
        entry.put("items", new ArrayList<String>(arr.getElementsAsString()));
        map.put(key, entry);
    }

    private static void putLangAlt(Map<String, Object> map, String key, ArrayProperty arr) {
        if (arr == null) {
            return;
        }
        // Preserve document order of the rdf:li children and pair each with its
        // xml:lang qualifier (absent => "x-default"), so a reordering bug or a
        // dropped qualifier shows up.
        List<Object> langs = new ArrayList<>();
        for (AbstractField field : arr.getContainer().getAllProperties()) {
            if (field instanceof TextType tt) {
                String lang = "x-default";
                if (tt.getAttribute("lang") != null) {
                    lang = tt.getAttribute("lang").getValue();
                }
                List<String> pair = new ArrayList<>();
                pair.add(lang);
                pair.add(tt.getStringValue());
                langs.add(pair);
            }
        }
        TreeMap<String, Object> entry = new TreeMap<>();
        entry.put("type", arr.getArrayType().name());
        entry.put("langs", langs);
        map.put(key, entry);
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
