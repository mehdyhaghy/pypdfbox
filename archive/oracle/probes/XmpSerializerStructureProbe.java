import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.TreeMap;
import javax.xml.parsers.DocumentBuilderFactory;
import org.apache.xmpbox.XMPMetadata;
import org.apache.xmpbox.schema.AdobePDFSchema;
import org.apache.xmpbox.schema.DublinCoreSchema;
import org.apache.xmpbox.xml.XmpSerializer;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NamedNodeMap;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

/**
 * Live oracle probe for the Apache xmpbox 3.0.7 {@code XmpSerializer.serialize}
 * <em>output structure</em> — the emitted XMP packet's shape rather than the
 * round-tripped property values (that surface is covered by
 * {@code XmpRoundTripProbe}).
 *
 * <p>Builds a fixed two-schema document (Dublin Core + Adobe PDF), serializes
 * it with {@code withXpacket=true}, and emits a canonical, whitespace- and
 * namespace-placement-independent structural summary as JSON:
 *
 * <ul>
 *   <li>{@code starts_with_xml_decl} — must be {@code false}; upstream sets
 *       {@code OMIT_XML_DECLARATION="yes"} so the packet begins with the
 *       {@code <?xpacket?>} PI, never an {@code <?xml?>} prolog.</li>
 *   <li>{@code xpacket_begin_id} / {@code xpacket_end} — the header PI's id and
 *       the trailer PI's end marker.</li>
 *   <li>{@code root_tag} — the wrapper element ({@code x:xmpmeta}).</li>
 *   <li>{@code descriptions} — one entry per {@code rdf:Description}, each with
 *       its declared schema prefix, {@code rdf:about} value, and the ordered
 *       list of property element local names. Array properties record their
 *       RDF container type ({@code Bag}/{@code Seq}/{@code Alt}) and the number
 *       of {@code rdf:li} children. Simple properties record that they are
 *       child <em>elements</em> (not attributes).</li>
 * </ul>
 *
 * Usage: {@code java -cp ... XmpSerializerStructureProbe}
 */
public final class XmpSerializerStructureProbe {

    private static final String RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#";

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        XMPMetadata meta = XMPMetadata.createXMPMetadata();
        DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
        dc.setTitle("Sample Title");
        dc.addCreator("Alice Smith");
        dc.addSubject("pdf");
        dc.addSubject("xmp");
        dc.setFormat("application/pdf");
        AdobePDFSchema ap = meta.createAndAddAdobePDFSchema();
        ap.setProducer("pypdfbox/test");
        ap.setKeywords("k1, k2");
        ap.setPDFVersion("1.7");

        XmpSerializer serializer = new XmpSerializer();
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        serializer.serialize(meta, baos, true);
        byte[] packet = baos.toByteArray();
        String text = new String(packet, StandardCharsets.UTF_8);

        TreeMap<String, Object> root = new TreeMap<>();
        root.put("starts_with_xml_decl", text.stripLeading().startsWith("<?xml"));
        // Locate the xpacket processing instructions by parsing the DOM.
        DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
        dbf.setNamespaceAware(true);
        Document doc = dbf.newDocumentBuilder()
                .parse(new java.io.ByteArrayInputStream(packet));

        for (Node n = doc.getFirstChild(); n != null; n = n.getNextSibling()) {
            if (n.getNodeType() == Node.PROCESSING_INSTRUCTION_NODE
                    && "xpacket".equals(n.getNodeName())) {
                String data = n.getNodeValue();
                if (data.startsWith("begin=")) {
                    root.put("xpacket_begin_present", true);
                    root.put("xpacket_begin_id", extract(data, "id"));
                } else if (data.startsWith("end=")) {
                    root.put("xpacket_end", extract(data, "end"));
                }
            }
        }

        Element xmpmeta = doc.getDocumentElement();
        root.put("root_tag", xmpmeta.getTagName());
        Element rdf = firstChildElement(xmpmeta);
        root.put("rdf_tag", rdf.getTagName());

        List<Object> descriptions = new ArrayList<>();
        NodeList descNodes = rdf.getElementsByTagNameNS(RDF_NS, "Description");
        for (int i = 0; i < descNodes.getLength(); i++) {
            descriptions.add(describeDescription((Element) descNodes.item(i)));
        }
        root.put("descriptions", descriptions);

        out.print(jsonify(root));
    }

    private static TreeMap<String, Object> describeDescription(Element desc) {
        TreeMap<String, Object> map = new TreeMap<>();
        map.put("about", attrNS(desc, RDF_NS, "about"));
        // Schema prefix derived from the first property element's prefix.
        List<Object> props = new ArrayList<>();
        String schemaPrefix = null;
        for (Node c = desc.getFirstChild(); c != null; c = c.getNextSibling()) {
            if (c.getNodeType() != Node.ELEMENT_NODE) {
                continue;
            }
            Element prop = (Element) c;
            String qn = prop.getTagName();
            int colon = qn.indexOf(':');
            String prefix = colon >= 0 ? qn.substring(0, colon) : "";
            String local = colon >= 0 ? qn.substring(colon + 1) : qn;
            if (schemaPrefix == null) {
                schemaPrefix = prefix;
            }
            props.add(describeProperty(local, prop));
        }
        map.put("prefix", schemaPrefix == null ? "" : schemaPrefix);
        map.put("properties", props);
        return map;
    }

    private static TreeMap<String, Object> describeProperty(String local, Element prop) {
        TreeMap<String, Object> map = new TreeMap<>();
        map.put("name", local);
        Element container = arrayContainer(prop);
        if (container != null) {
            map.put("kind", "array");
            String cn = container.getTagName();
            int colon = cn.indexOf(':');
            map.put("array_type", colon >= 0 ? cn.substring(colon + 1) : cn);
            int li = 0;
            for (Node c = container.getFirstChild(); c != null; c = c.getNextSibling()) {
                if (c.getNodeType() == Node.ELEMENT_NODE) {
                    li++;
                }
            }
            map.put("li_count", li);
        } else {
            map.put("kind", "simple");
            map.put("value", prop.getTextContent());
        }
        return map;
    }

    /** Returns the rdf:Bag/Seq/Alt child element, or null for simple props. */
    private static Element arrayContainer(Element prop) {
        for (Node c = prop.getFirstChild(); c != null; c = c.getNextSibling()) {
            if (c.getNodeType() == Node.ELEMENT_NODE) {
                Element e = (Element) c;
                if (RDF_NS.equals(e.getNamespaceURI())) {
                    String ln = e.getLocalName();
                    if ("Bag".equals(ln) || "Seq".equals(ln) || "Alt".equals(ln)) {
                        return e;
                    }
                }
            }
        }
        return null;
    }

    private static Element firstChildElement(Element parent) {
        for (Node c = parent.getFirstChild(); c != null; c = c.getNextSibling()) {
            if (c.getNodeType() == Node.ELEMENT_NODE) {
                return (Element) c;
            }
        }
        throw new IllegalStateException("no child element of " + parent.getTagName());
    }

    private static String attrNS(Element e, String ns, String local) {
        NamedNodeMap attrs = e.getAttributes();
        Node n = attrs.getNamedItemNS(ns, local);
        return n == null ? null : n.getNodeValue();
    }

    /** Pull a {@code key="value"} token out of a PI data string. */
    private static String extract(String data, String key) {
        String needle = key + "=\"";
        int start = data.indexOf(needle);
        if (start < 0) {
            return null;
        }
        start += needle.length();
        int end = data.indexOf('"', start);
        return end < 0 ? null : data.substring(start, end);
    }

    // --- minimal JSON emitter (TreeMap / List / String / Boolean / Number) ---

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
