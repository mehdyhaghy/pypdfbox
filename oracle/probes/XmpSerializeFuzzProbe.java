import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.TreeMap;
import org.apache.xmpbox.XMPMetadata;
import org.apache.xmpbox.schema.AdobePDFSchema;
import org.apache.xmpbox.schema.DublinCoreSchema;
import org.apache.xmpbox.schema.XMPBasicSchema;
import org.apache.xmpbox.schema.XMPSchema;
import org.apache.xmpbox.type.AbstractField;
import org.apache.xmpbox.type.ArrayProperty;
import org.apache.xmpbox.type.TextType;
import org.apache.xmpbox.xml.DomXmpParser;
import org.apache.xmpbox.xml.XmpSerializer;

/**
 * Differential SERIALIZE fuzz probe for Apache xmpbox 3.0.7 (wave 1548).
 *
 * <p>Sibling of {@code XmpSerializerStructureProbe} (fixed two-schema shape
 * dump) and {@code XmpReverseSerializeProbe} (xmpbox-writes / pypdfbox-reads).
 * Neither stresses the serializer over a wide corpus of edge content. This
 * probe builds ~30 programmatic {@code XMPMetadata} documents with adversarial
 * content, serializes each with {@code XmpSerializer.serialize(meta, os, true)},
 * then <em>re-parses</em> the serialized bytes with {@code DomXmpParser} and
 * projects a STABLE, byte-formatting-independent round-trip shape. Comparing
 * the round-tripped shape (rather than raw bytes) lets pypdfbox and xmpbox
 * legitimately differ on whitespace / attribute order / xmlns placement while
 * still pinning the load-bearing structural facts that a faithful serializer
 * must preserve: schema count, per-schema prefix/namespace/about, property
 * local names, array container type + item order, LangAlt lang→value mapping,
 * and survival of XML special chars / unicode / control chars / long values.
 *
 * <p>Edge angles: empty metadata; schema with no properties; arrays with
 * 0/1/many items; Alt with multiple xml:lang; XML special chars (&amp; &lt;
 * &gt; quotes) in values and in array items; unicode + astral + control chars;
 * very long values; duplicate-prefix-namespace pairs across schemas; non-empty
 * rdf:about; whitespace-only and empty-string values.
 *
 * <p>Output grammar: one line per case in corpus order,
 * {@code CASE <name> <json>} where {@code <json>} is the normalized shape (or
 * {@code EXC <ErrorType>} if serialize-then-parse threw). The Python side
 * mirrors the build + the projection and asserts line-for-line.
 *
 * Usage: {@code java -cp ... XmpSerializeFuzzProbe}
 */
public final class XmpSerializeFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        List<Case> cases = corpus();
        for (Case c : cases) {
            sb.append("CASE ").append(c.name).append(' ');
            try {
                XMPMetadata meta = c.build();
                XmpSerializer serializer = new XmpSerializer();
                ByteArrayOutputStream baos = new ByteArrayOutputStream();
                serializer.serialize(meta, baos, true);
                byte[] packet = baos.toByteArray();
                DomXmpParser parser = new DomXmpParser();
                XMPMetadata reparsed = parser.parse(
                        new ByteArrayInputStream(packet));
                sb.append(jsonify(project(reparsed)));
            } catch (Exception e) {
                sb.append("EXC ").append(e.getClass().getSimpleName());
            }
            sb.append('\n');
        }
        out.print(sb);
    }

    // ------------------------------------------------------------------
    // Corpus: each Case knows how to build one XMPMetadata.

    private interface Builder {
        XMPMetadata build() throws Exception;
    }

    private static final class Case {
        final String name;
        final Builder builder;

        Case(String name, Builder builder) {
            this.name = name;
            this.builder = builder;
        }

        XMPMetadata build() throws Exception {
            return builder.build();
        }
    }

    private static List<Case> corpus() {
        List<Case> c = new ArrayList<>();

        c.add(new Case("empty", () -> XMPMetadata.createXMPMetadata()));

        c.add(new Case("dc_empty_schema", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            m.createAndAddDublinCoreSchema();
            return m;
        }));

        c.add(new Case("dc_single_creator", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addCreator("Solo");
            return m;
        }));

        c.add(new Case("dc_many_creators", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addCreator("A");
            dc.addCreator("B");
            dc.addCreator("C");
            dc.addCreator("D");
            return m;
        }));

        c.add(new Case("dc_subject_bag_order", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addSubject("zeta");
            dc.addSubject("alpha");
            dc.addSubject("mu");
            return m;
        }));

        c.add(new Case("dc_title_alt_multi_lang", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addTitle("x-default", "Default");
            dc.addTitle("en", "English");
            dc.addTitle("fr", "Francais");
            dc.addTitle("de", "Deutsch");
            return m;
        }));

        c.add(new Case("dc_value_ampersand", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addCreator("Tom & Jerry");
            return m;
        }));

        c.add(new Case("dc_value_angle_brackets", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addCreator("<not a tag>");
            return m;
        }));

        c.add(new Case("dc_value_quotes", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addCreator("She said \"hi\" & 'bye'");
            return m;
        }));

        c.add(new Case("dc_title_special_in_alt", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addTitle("x-default", "A & B < C > D");
            return m;
        }));

        c.add(new Case("dc_unicode", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addCreator("éèê café");
            dc.addSubject("安全");
            dc.addTitle("ja", "こんにちは");
            return m;
        }));

        c.add(new Case("dc_astral", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            // U+1F600 grinning face (surrogate pair) + U+1D11E G-clef.
            dc.addCreator("emoji 😀 clef 𝄞");
            return m;
        }));

        c.add(new Case("dc_tab_newline", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addCreator("line1\nline2\ttabbed");
            return m;
        }));

        c.add(new Case("dc_empty_string_creator", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addCreator("");
            dc.addCreator("after-empty");
            return m;
        }));

        c.add(new Case("dc_whitespace_value", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.setFormat("   ");
            return m;
        }));

        c.add(new Case("dc_long_value", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            StringBuilder big = new StringBuilder();
            for (int i = 0; i < 500; i++) {
                big.append("abcdefghij");
            }
            dc.addCreator(big.toString());
            return m;
        }));

        c.add(new Case("dc_format_simple", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.setFormat("application/pdf");
            return m;
        }));

        c.add(new Case("two_schemas", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addCreator("Author");
            AdobePDFSchema ap = m.createAndAddAdobePDFSchema();
            ap.setProducer("prod");
            ap.setKeywords("k1, k2");
            return m;
        }));

        c.add(new Case("three_schemas", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.setFormat("application/pdf");
            AdobePDFSchema ap = m.createAndAddAdobePDFSchema();
            ap.setProducer("prod");
            XMPBasicSchema xb = m.createAndAddXMPBasicSchema();
            xb.setCreatorTool("toolname");
            return m;
        }));

        c.add(new Case("pdf_keywords_special", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            AdobePDFSchema ap = m.createAndAddAdobePDFSchema();
            ap.setKeywords("a & b, <c>, \"d\"");
            ap.setProducer("p & q");
            ap.setPDFVersion("1.7");
            return m;
        }));

        c.add(new Case("nonempty_about", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.setAboutAsSimple("uuid:1234-5678");
            dc.addCreator("X");
            return m;
        }));

        c.add(new Case("about_url", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.setAboutAsSimple("http://example.com/doc#meta");
            dc.addSubject("s");
            return m;
        }));

        c.add(new Case("xmp_basic_text", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            XMPBasicSchema xb = m.createAndAddXMPBasicSchema();
            xb.setCreatorTool("My Tool 2.0");
            return m;
        }));

        c.add(new Case("dc_alt_single_lang", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.setTitle("Only Default");
            return m;
        }));

        c.add(new Case("dc_desc_and_title", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addTitle("x-default", "T");
            dc.setDescription("A description with & and < chars");
            return m;
        }));

        c.add(new Case("dc_lang_value_special", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addTitle("en", "Tom & <Jerry>");
            dc.addTitle("fr", "café & crème");
            return m;
        }));

        c.add(new Case("dc_creator_with_newline_amp", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addCreator("first & second\nthird < fourth");
            return m;
        }));

        c.add(new Case("dc_all_arrays", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addCreator("c1");
            dc.addCreator("c2");
            dc.addSubject("s1");
            dc.addSubject("s2");
            dc.addSubject("s3");
            dc.addTitle("x-default", "td");
            dc.addTitle("en", "te");
            dc.setFormat("text/plain");
            return m;
        }));

        c.add(new Case("xmp_then_dc_prefix", () -> {
            // XMP basic first, DC second — order-sensitive schema emission.
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            XMPBasicSchema xb = m.createAndAddXMPBasicSchema();
            xb.setCreatorTool("tool");
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addCreator("auth");
            return m;
        }));

        c.add(new Case("dc_subject_special_items", () -> {
            XMPMetadata m = XMPMetadata.createXMPMetadata();
            DublinCoreSchema dc = m.createAndAddDublinCoreSchema();
            dc.addSubject("a&b");
            dc.addSubject("<x>");
            dc.addSubject("\"q\"");
            dc.addSubject("normal");
            return m;
        }));

        return c;
    }

    // ------------------------------------------------------------------
    // Projection: normalized round-trip shape.

    private static final String RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#";

    private static TreeMap<String, Object> project(XMPMetadata meta) {
        TreeMap<String, Object> root = new TreeMap<>();
        List<XMPSchema> schemas = meta.getAllSchemas();
        root.put("schema_count", schemas.size());
        // Schemas keyed + sorted by namespace then prefix for stable order.
        List<Object> schemaList = new ArrayList<>();
        List<XMPSchema> sorted = new ArrayList<>(schemas);
        sorted.sort((a, b) -> {
            String na = nz(a.getNamespace());
            String nb = nz(b.getNamespace());
            int cmp = na.compareTo(nb);
            if (cmp != 0) {
                return cmp;
            }
            return nz(a.getPrefix()).compareTo(nz(b.getPrefix()));
        });
        for (XMPSchema s : sorted) {
            schemaList.add(projectSchema(s));
        }
        root.put("schemas", schemaList);
        return root;
    }

    private static TreeMap<String, Object> projectSchema(XMPSchema s) {
        TreeMap<String, Object> map = new TreeMap<>();
        map.put("prefix", nz(s.getPrefix()));
        map.put("namespace", nz(s.getNamespace()));
        map.put("about", nz(s.getAboutValue()));
        List<Object> props = new ArrayList<>();
        List<AbstractField> fields = new ArrayList<>(s.getAllProperties());
        fields.sort((a, b) -> nz(a.getPropertyName()).compareTo(nz(b.getPropertyName())));
        for (AbstractField f : fields) {
            props.add(projectField(f));
        }
        map.put("properties", props);
        return map;
    }

    private static TreeMap<String, Object> projectField(AbstractField f) {
        TreeMap<String, Object> map = new TreeMap<>();
        map.put("name", nz(f.getPropertyName()));
        if (f instanceof ArrayProperty arr) {
            map.put("kind", "array");
            org.apache.xmpbox.type.Cardinality at = arr.getArrayType();
            map.put("array_type", at == null ? "" : at.name());
            // Determine if this is a LangAlt (children carry xml:lang).
            List<AbstractField> children = arr.getContainer().getAllProperties();
            boolean isLangAlt = false;
            for (AbstractField child : children) {
                if (child instanceof TextType tt && tt.getAttribute("lang") != null) {
                    isLangAlt = true;
                    break;
                }
            }
            if (isLangAlt) {
                map.put("lang_alt", true);
                TreeMap<String, String> langs = new TreeMap<>();
                for (AbstractField child : children) {
                    if (child instanceof TextType tt) {
                        String lang = tt.getAttribute("lang") != null
                                ? tt.getAttribute("lang").getValue() : "x-default";
                        langs.put(lang, tt.getStringValue());
                    }
                }
                map.put("items", langs);
            } else {
                List<Object> items = new ArrayList<>();
                for (AbstractField child : children) {
                    if (child instanceof TextType tt) {
                        items.add(tt.getStringValue());
                    } else {
                        items.add("<" + child.getClass().getSimpleName() + ">");
                    }
                }
                map.put("items", items);
            }
        } else if (f instanceof TextType tt) {
            map.put("kind", "simple");
            map.put("value", nz(tt.getStringValue()));
        } else {
            map.put("kind", "other");
            map.put("type", f.getClass().getSimpleName());
        }
        return map;
    }

    private static String nz(String s) {
        return s == null ? "" : s;
    }

    // --- minimal JSON emitter (TreeMap / List / String / Number / Boolean) ---

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
