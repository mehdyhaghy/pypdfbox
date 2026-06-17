import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.xmpbox.XMPMetadata;
import org.apache.xmpbox.type.AbstractField;
import org.apache.xmpbox.type.AbstractStructuredType;
import org.apache.xmpbox.type.ArrayProperty;
import org.apache.xmpbox.type.Cardinality;
import org.apache.xmpbox.type.DimensionsType;
import org.apache.xmpbox.type.IntegerType;
import org.apache.xmpbox.type.JobType;
import org.apache.xmpbox.type.TextType;
import org.apache.xmpbox.type.ThumbnailType;
import org.apache.xmpbox.type.TypeMapping;
import org.apache.xmpbox.type.Types;

/**
 * Live oracle probe for the Apache xmpbox 3.0.7 TYPE-SYSTEM container / mapping
 * layer, complementing the simple-value probe ({@code XmpPropertyTypeFuzzProbe},
 * wave 1535) and the per-struct field-getter probe
 * ({@code XmpStructuredTypeFuzzProbe}, wave 1536).
 *
 * <p>This probe fuzzes the parts those two left uncovered:
 * <ul>
 *   <li>{@link ArrayProperty} — container kind (Bag/Seq/Alt) detection,
 *       add/getAllProperties size, {@code getElementsAsString} ordering,
 *       {@code getPropertiesByLocalName} (null-vs-list), {@code getProperty}
 *       first-match, {@code removeProperty}, {@code removePropertiesByName},
 *       {@code containsProperty}/isSameProperty equivalence.</li>
 *   <li>{@link AbstractStructuredType} GENERIC field access (not the typed
 *       getters): {@code addSimpleProperty} + {@code getProperty} present/absent,
 *       {@code getPropertyValueAsString}, add-twice-replaces, wrong-type cast.</li>
 *   <li>{@link TypeMapping} {@code instanciateSimpleProperty} /
 *       {@code instanciateStructuredType} for a known vs unknown type.</li>
 * </ul>
 *
 * <p>Usage: {@code java -cp <jars> XmpTypeSystemFuzzProbe <case>}
 *
 * <p>Output (one line per call, UTF-8): a {@code key=value} payload joined by
 * the ASCII unit separator (0x1f), or {@code ERR<US>ExceptionSimpleName} when a
 * call throws (reflection causes are unwrapped to the real exception).
 */
public final class XmpTypeSystemFuzzProbe {
    private static final char US = (char) 0x1f;
    private static final String NS = "http://ns.example/";
    private static final String PFX = "ex";

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String c = args[0];
        XMPMetadata meta = XMPMetadata.createXMPMetadata();
        try {
            out.print(run(meta, c) + "\n");
        } catch (java.lang.reflect.InvocationTargetException ite) {
            Throwable cause = ite.getCause() == null ? ite : ite.getCause();
            out.print("ERR" + US + cause.getClass().getSimpleName() + "\n");
        } catch (Throwable ex) {
            out.print("ERR" + US + ex.getClass().getSimpleName() + "\n");
        }
    }

    private static String run(XMPMetadata meta, String c) throws Exception {
        switch (c) {
            // === ArrayProperty: container-kind detection ==================
            case "arr_bag_kind":
                return kvLast("type", bag(meta).getArrayType().name());
            case "arr_seq_kind":
                return kvLast("type", seq(meta).getArrayType().name());
            case "arr_alt_kind":
                return kvLast("type", alt(meta).getArrayType().name());

            // === ArrayProperty: add + size + elements (ordered) ==========
            case "arr_empty_elems": {
                ArrayProperty a = bag(meta);
                return kv("size", a.getContainer().getAllProperties().size())
                        + kvLast("elems", join(a.getElementsAsString()));
            }
            case "arr_add_elems": {
                ArrayProperty a = seq(meta);
                a.getContainer().addProperty(text(meta, "one"));
                a.getContainer().addProperty(text(meta, "two"));
                a.getContainer().addProperty(text(meta, "three"));
                return kv("size", a.getContainer().getAllProperties().size())
                        + kvLast("elems", join(a.getElementsAsString()));
            }
            case "arr_add_dup": {
                // Array containers APPEND duplicates (do not replace by name).
                ArrayProperty a = bag(meta);
                a.getContainer().addProperty(text(meta, "x"));
                a.getContainer().addProperty(text(meta, "x"));
                return kv("size", a.getContainer().getAllProperties().size())
                        + kvLast("elems", join(a.getElementsAsString()));
            }
            case "arr_add_empty_str": {
                ArrayProperty a = bag(meta);
                a.getContainer().addProperty(text(meta, ""));
                return kv("size", a.getContainer().getAllProperties().size())
                        + kvLast("elems", join(a.getElementsAsString()));
            }

            // === ArrayProperty: getPropertiesByLocalName null-vs-list ====
            case "arr_byname_miss": {
                ArrayProperty a = bag(meta);
                a.getContainer().addProperty(text(meta, "v"));
                List<AbstractField> r =
                        a.getContainer().getPropertiesByLocalName("nope");
                return kvLast("r", r == null ? "null" : "size=" + r.size());
            }
            case "arr_byname_hit": {
                ArrayProperty a = bag(meta);
                a.getContainer().addProperty(text(meta, "v1"));
                a.getContainer().addProperty(text(meta, "v2"));
                // Both li children share local name "li" by construction here.
                List<AbstractField> r =
                        a.getContainer().getPropertiesByLocalName("li");
                return kvLast("r", r == null ? "null" : "size=" + r.size());
            }

            // === ArrayProperty: removeProperty / removePropertiesByName ==
            case "arr_remove_prop": {
                ArrayProperty a = seq(meta);
                TextType keep = text(meta, "keep");
                TextType drop = text(meta, "drop");
                a.getContainer().addProperty(keep);
                a.getContainer().addProperty(drop);
                a.getContainer().removeProperty(drop);
                return kv("size", a.getContainer().getAllProperties().size())
                        + kvLast("elems", join(a.getElementsAsString()));
            }
            case "arr_remove_byname": {
                ArrayProperty a = seq(meta);
                a.getContainer().addProperty(text(meta, "a"));
                a.getContainer().addProperty(text(meta, "b"));
                a.getContainer().removePropertiesByName("li");
                return kvLast("size", a.getContainer().getAllProperties().size());
            }

            // === ArrayProperty: containsProperty / isSameProperty ========
            case "arr_contains_same_value": {
                // Two distinct TextType objects, same local name + same value
                // => isSameProperty true => containsProperty true.
                ArrayProperty a = bag(meta);
                a.getContainer().addProperty(text(meta, "dup"));
                return kvLast("c",
                        a.getContainer().containsProperty(text(meta, "dup")));
            }
            case "arr_contains_diff_value": {
                ArrayProperty a = bag(meta);
                a.getContainer().addProperty(text(meta, "one"));
                return kvLast("c",
                        a.getContainer().containsProperty(text(meta, "two")));
            }

            // === AbstractStructuredType: generic field access ============
            case "struct_get_absent": {
                JobType j = new JobType(meta);
                return kvLast("p", j.getProperty(JobType.ID) == null ? "null" : "obj");
            }
            case "struct_add_get": {
                // addSimpleProperty is protected; reach it via reflection so the
                // generic (not typed-getter) path is exercised. JobType.ID is a
                // declared field (type Text), so the type lookup succeeds.
                JobType j = new JobType(meta);
                addSimple(j, JobType.ID, "J7");
                AbstractField f = j.getProperty(JobType.ID);
                return kv("found", f != null)
                        + kvLast("val", valueAsString(j, JobType.ID));
            }
            case "struct_add_twice_replaces": {
                // Non-array complex containers REPLACE by local name.
                JobType j = new JobType(meta);
                addSimple(j, JobType.ID, "first");
                addSimple(j, JobType.ID, "second");
                return kv("size", j.getAllProperties().size())
                        + kvLast("val", valueAsString(j, JobType.ID));
            }
            case "struct_remove_present": {
                JobType j = new JobType(meta);
                addSimple(j, JobType.ID, "X");
                AbstractField f = j.getProperty(JobType.ID);
                j.removeProperty(f);
                return kvLast("size", j.getAllProperties().size());
            }
            case "struct_value_as_string_absent": {
                JobType j = new JobType(meta);
                return kvLast("v", valueAsString(j, JobType.ID));
            }
            case "struct_add_unknown_field": {
                // Field name NOT declared on JobType: upstream's
                // getPropertyType(name) returns null and addSimpleProperty NPEs
                // on .type(). pypdfbox is intentionally lenient (defaults the
                // type to Text); pinned as an explicit divergence on the Python
                // side rather than compared cross-side here.
                JobType j = new JobType(meta);
                addSimple(j, "undeclared", "v");
                return kvLast("size", j.getAllProperties().size());
            }
            case "struct_wrong_type_cast": {
                // 'w' is a Real field on DimensionsType; store a Text there via
                // the generic addSimpleProperty then read the typed getW() (which
                // casts to RealType). Project the failure class.
                DimensionsType d = new DimensionsType(meta);
                addSimple(d, DimensionsType.W, "not-a-real");
                return kvLast("w", d.getW());
            }
            case "struct_int_wrong_type_cast": {
                ThumbnailType t = new ThumbnailType(meta);
                addSimple(t, ThumbnailType.HEIGHT, "not-an-int");
                return kvLast("h", t.getHeight());
            }

            // === TypeMapping.instanciateSimpleProperty ===================
            case "tm_simple_text": {
                TypeMapping tm = meta.getTypeMapping();
                AbstractField f = tm.instanciateSimpleProperty(
                        NS, PFX, "p", "hello", Types.Text);
                return kv("cls", f.getClass().getSimpleName())
                        + kvLast("v", ((TextType) f).getStringValue());
            }
            case "tm_simple_integer_ok": {
                TypeMapping tm = meta.getTypeMapping();
                AbstractField f = tm.instanciateSimpleProperty(
                        NS, PFX, "p", "42", Types.Integer);
                return kv("cls", f.getClass().getSimpleName())
                        + kvLast("v", ((IntegerType) f).getStringValue());
            }
            case "tm_simple_integer_bad": {
                // Integer type, non-numeric raw -> the underlying setValue throws.
                TypeMapping tm = meta.getTypeMapping();
                AbstractField f = tm.instanciateSimpleProperty(
                        NS, PFX, "p", "abc", Types.Integer);
                return kvLast("cls", f.getClass().getSimpleName());
            }
            case "tm_simple_structured_type": {
                // A structured type name is not a valid simple type.
                TypeMapping tm = meta.getTypeMapping();
                AbstractField f = tm.instanciateSimpleProperty(
                        NS, PFX, "p", "x", Types.Dimensions);
                return kvLast("cls", f.getClass().getSimpleName());
            }

            // === TypeMapping.instanciateStructuredType ===================
            case "tm_struct_known": {
                TypeMapping tm = meta.getTypeMapping();
                AbstractStructuredType s =
                        tm.instanciateStructuredType(Types.Dimensions, "p");
                return kv("cls", s.getClass().getSimpleName())
                        + kvLast("name", s.getPropertyName());
            }
            case "tm_struct_simple_name": {
                // A simple type passed where a structured type is expected.
                TypeMapping tm = meta.getTypeMapping();
                AbstractStructuredType s =
                        tm.instanciateStructuredType(Types.Text, "p");
                return kvLast("cls", s.getClass().getSimpleName());
            }

            default:
                return "ERR" + US + "UnknownCase";
        }
    }

    // --- builders -----------------------------------------------------

    private static ArrayProperty bag(XMPMetadata meta) {
        return new ArrayProperty(meta, NS, PFX, "arr", Cardinality.Bag);
    }

    private static ArrayProperty seq(XMPMetadata meta) {
        return new ArrayProperty(meta, NS, PFX, "arr", Cardinality.Seq);
    }

    private static ArrayProperty alt(XMPMetadata meta) {
        return new ArrayProperty(meta, NS, PFX, "arr", Cardinality.Alt);
    }

    private static TextType text(XMPMetadata meta, String v) {
        // rdf:li children carry the structure-array element name "li".
        return new TextType(meta, NS, PFX, "li", v);
    }

    private static void addSimple(AbstractStructuredType t, String name, Object value)
            throws Exception {
        java.lang.reflect.Method m = AbstractStructuredType.class
                .getDeclaredMethod("addSimpleProperty", String.class, Object.class);
        m.setAccessible(true);
        m.invoke(t, name, value);
    }

    private static String valueAsString(AbstractStructuredType t, String name)
            throws Exception {
        java.lang.reflect.Method m = AbstractStructuredType.class
                .getDeclaredMethod("getPropertyValueAsString", String.class);
        m.setAccessible(true);
        return String.valueOf(m.invoke(t, name));
    }

    private static String join(List<String> items) {
        List<String> safe = items == null ? new ArrayList<>() : items;
        return String.join(",", safe);
    }

    private static String kv(String k, Object v) {
        return k + "=" + String.valueOf(v) + US;
    }

    private static String kvLast(String k, Object v) {
        return k + "=" + String.valueOf(v);
    }
}
