import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.TreeMap;
import javax.xml.parsers.DocumentBuilderFactory;
import org.apache.xmpbox.XMPMetadata;
import org.apache.xmpbox.schema.XMPMediaManagementSchema;
import org.apache.xmpbox.type.AbstractField;
import org.apache.xmpbox.type.ResourceRefType;
import org.apache.xmpbox.xml.DomXmpParser;
import org.apache.xmpbox.xml.XmpSerializer;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;

/**
 * Live oracle probe for the xmpbox 3.0.7 {@code parseType="Resource"}
 * structured-type surface, exercised through {@code ResourceRefType}
 * ({@code xmpMM:DerivedFrom}).
 *
 * <p>Two modes:
 *
 * <ul>
 *   <li>{@code parse <packet.xmp> [lenient]} — parse a hand-crafted XMP packet
 *       containing an {@code xmpMM:DerivedFrom rdf:parseType="Resource"}
 *       property and emit a canonical JSON dump of the parsed
 *       {@code ResourceRefType}'s child fields (name -> value, sorted), plus
 *       its structure kind.</li>
 *   <li>{@code serialize} — construct a {@code ResourceRefType} via the public
 *       API (property name set BEFORE {@code addProperty} to dodge the
 *       {@code normalizeAttributes} NPE), serialize the metadata, then re-parse
 *       the serialized DOM and emit the same canonical structure JSON as the
 *       parse mode would. This captures the serialize-direction shape without
 *       depending on attribute ordering.</li>
 * </ul>
 */
public final class XmpResourceRefProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("parse".equals(mode)) {
            byte[] bytes = Files.readAllBytes(Paths.get(args[1]));
            DomXmpParser parser = new DomXmpParser();
            if (args.length > 2 && "lenient".equals(args[2])) {
                parser.setStrictParsing(false);
            }
            XMPMetadata meta = parser.parse(bytes);
            out.print(jsonify(dumpFromMeta(meta)));
        } else if ("serialize".equals(mode)) {
            XMPMetadata meta = XMPMetadata.createXMPMetadata();
            XMPMediaManagementSchema mm = meta.createAndAddXMPMediaManagementSchema();
            ResourceRefType ref = new ResourceRefType(meta);
            // Property name MUST be set before addProperty: the serializer's
            // normalizeAttributes walks getPropertyName() and NPEs on null.
            ref.setPropertyName(XMPMediaManagementSchema.DERIVED_FROM);
            ref.setInstanceID("uuid:inst-123");
            ref.setDocumentID("uuid:doc-456");
            ref.setRenditionClass("default");
            ref.setVersionID("7");
            mm.setDerivedFromProperty(ref);

            XmpSerializer serializer = new XmpSerializer();
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            serializer.serialize(meta, baos, true);
            byte[] packet = baos.toByteArray();

            // Upstream serializes the inner stRef:* fields WITHOUT declaring
            // their xmlns:stRef namespace, so the emitted packet is not
            // re-parseable by xmpbox's own DomXmpParser ("prefix stRef not
            // bound"). Compare the serialized DOM *shape* directly instead of
            // round-tripping it back through the parser.
            TreeMap<String, Object> root = new TreeMap<>();
            root.put("dom", domShape(packet));
            out.print(jsonify(root));
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static TreeMap<String, Object> dumpFromMeta(XMPMetadata meta) {
        TreeMap<String, Object> root = new TreeMap<>();
        XMPMediaManagementSchema mm = meta.getXMPMediaManagementSchema();
        if (mm == null) {
            root.put("derived_from_present", false);
            return root;
        }
        ResourceRefType ref = mm.getDerivedFromProperty();
        if (ref == null) {
            root.put("derived_from_present", false);
            return root;
        }
        root.put("derived_from_present", true);
        root.put("kind", "structured");
        TreeMap<String, String> fields = new TreeMap<>();
        for (AbstractField field : ref.getAllProperties()) {
            fields.put(field.getPropertyName(), stringValue(field));
        }
        root.put("fields", fields);
        return root;
    }

    private static String stringValue(AbstractField field) {
        // Every ResourceRef child is a simple property; read its string form.
        try {
            return (String) field.getClass().getMethod("getStringValue").invoke(field);
        } catch (Exception e) {
            return String.valueOf(field);
        }
    }

    /** Minimal structural fingerprint of the serialized DOM.
     *
     * Parsed namespace-UNAWARE because the upstream serializer emits the
     * inner stRef:* fields without declaring xmlns:stRef, which a
     * namespace-aware parser rejects. We match on qualified tag names
     * ({@code xmpMM:DerivedFrom}, {@code rdf:li}) and the literal
     * {@code rdf:parseType} attribute instead. */
    private static TreeMap<String, Object> domShape(byte[] packet) throws Exception {
        DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
        dbf.setNamespaceAware(false);
        Document doc = dbf.newDocumentBuilder()
                .parse(new java.io.ByteArrayInputStream(packet));
        TreeMap<String, Object> shape = new TreeMap<>();
        Element derived = findFirstByTag(doc.getDocumentElement(), "xmpMM:DerivedFrom");
        if (derived == null) {
            shape.put("wrapper_found", false);
            return shape;
        }
        shape.put("wrapper_found", true);
        shape.put("wrapper_tag", derived.getTagName());
        Element li = firstChildElementByTag(derived, "rdf:li");
        if (li != null) {
            shape.put("has_rdf_li", true);
            shape.put("li_parsetype", li.getAttribute("rdf:parseType"));
            // ordered child field tags of the rdf:li
            List<Object> children = new ArrayList<>();
            for (Node c = li.getFirstChild(); c != null; c = c.getNextSibling()) {
                if (c.getNodeType() == Node.ELEMENT_NODE) {
                    Element e = (Element) c;
                    TreeMap<String, Object> f = new TreeMap<>();
                    f.put("tag", e.getTagName());
                    f.put("value", e.getTextContent());
                    children.add(f);
                }
            }
            shape.put("li_children", children);
        } else {
            shape.put("has_rdf_li", false);
            shape.put("wrapper_direct_parsetype", derived.getAttribute("rdf:parseType"));
        }
        return shape;
    }

    private static Element findFirstByTag(Element root, String tag) {
        if (tag.equals(root.getTagName())) {
            return root;
        }
        for (Node c = root.getFirstChild(); c != null; c = c.getNextSibling()) {
            if (c.getNodeType() == Node.ELEMENT_NODE) {
                Element found = findFirstByTag((Element) c, tag);
                if (found != null) {
                    return found;
                }
            }
        }
        return null;
    }

    private static Element firstChildElementByTag(Element parent, String tag) {
        for (Node c = parent.getFirstChild(); c != null; c = c.getNextSibling()) {
            if (c.getNodeType() == Node.ELEMENT_NODE
                    && tag.equals(((Element) c).getTagName())) {
                return (Element) c;
            }
        }
        return null;
    }

    // --- minimal JSON emitter ---

    private static String jsonify(Object value) {
        StringBuilder sb = new StringBuilder();
        emit(sb, value);
        return sb.toString();
    }

    private static void emit(StringBuilder sb, Object value) {
        if (value == null) {
            sb.append("null");
        } else if (value instanceof java.util.Map<?, ?> map) {
            sb.append("{");
            boolean first = true;
            for (java.util.Map.Entry<?, ?> entry : map.entrySet()) {
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
