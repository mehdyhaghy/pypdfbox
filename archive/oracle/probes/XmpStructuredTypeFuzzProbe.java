import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.xmpbox.XMPMetadata;
import org.apache.xmpbox.type.AbstractField;
import org.apache.xmpbox.type.AbstractStructuredType;
import org.apache.xmpbox.type.DimensionsType;
import org.apache.xmpbox.type.JobType;
import org.apache.xmpbox.type.LayerType;
import org.apache.xmpbox.type.ResourceRefType;
import org.apache.xmpbox.type.ThumbnailType;
import org.apache.xmpbox.type.VersionType;

/**
 * Live oracle probe for the Apache xmpbox 3.0.7 STRUCTURED property types built
 * on {@code AbstractStructuredType}: Dimensions / Job / Layer / ResourceRef /
 * Thumbnail / Version.
 *
 * <p>Where {@code XmpPropertyTypeFuzzProbe} fuzzes the simple value-conversion
 * classes, this probe fuzzes the *field access* layer of the structured types:
 * the typed getters returning null for missing fields, set/get round-trips, the
 * field-name -> property mapping, getAllProperties ordering, the namespace /
 * prefix carried on each child field, and getW/getH/getUnit etc. for malformed
 * (wrong-type / empty) field values.
 *
 * <p>Usage: {@code java -cp <jars> XmpStructuredTypeFuzzProbe <case>}
 *
 * <p>Output (one line per probe call, UTF-8 to stdout): a small key=value
 * payload (US-separated) describing the projected outcome, or
 * {@code ERR<US>ExceptionSimpleName} when a call throws.
 */
public final class XmpStructuredTypeFuzzProbe {
    private static final char US = (char) 0x1f;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String c = args[0];
        XMPMetadata meta = XMPMetadata.createXMPMetadata();
        try {
            out.print(run(meta, c) + "\n");
        } catch (java.lang.reflect.InvocationTargetException ite) {
            // Reflection wraps the real exception; report the cause's class so
            // the projected surface is the actual upstream failure, not the
            // reflection plumbing.
            Throwable cause = ite.getCause() == null ? ite : ite.getCause();
            out.print("ERR" + US + cause.getClass().getSimpleName() + "\n");
        } catch (Throwable ex) {
            out.print("ERR" + US + ex.getClass().getSimpleName() + "\n");
        }
    }

    private static String run(XMPMetadata meta, String c) throws Exception {
        switch (c) {
            // --- empty struct: every getter -> null ----------------------
            case "dim_empty": {
                DimensionsType d = new DimensionsType(meta);
                return kv("w", d.getW()) + kv("h", d.getH()) + kvLast("unit", d.getUnit());
            }
            case "job_empty": {
                JobType j = new JobType(meta);
                return kv("id", j.getId()) + kv("name", j.getName()) + kvLast("url", j.getUrl());
            }
            case "layer_empty": {
                LayerType l = new LayerType(meta);
                return kv("name", l.getLayerName()) + kvLast("text", l.getLayerText());
            }
            case "ref_empty": {
                ResourceRefType r = new ResourceRefType(meta);
                return kv("doc", r.getDocumentID())
                        + kv("inst", r.getInstanceID())
                        + kv("date", r.getLastModifyDate() == null ? null : "cal")
                        + kv("alt", r.getAlternatePaths() == null ? null : "list")
                        + kvLast("rc", r.getRenditionClass());
            }
            case "thumb_empty": {
                ThumbnailType t = new ThumbnailType(meta);
                return kv("w", t.getWidth())
                        + kv("h", t.getHeight())
                        + kv("fmt", t.getFormat())
                        + kvLast("img", t.getImage());
            }
            case "ver_empty": {
                VersionType v = new VersionType(meta);
                return kv("comments", v.getComments())
                        + kv("modifier", v.getModifier())
                        + kv("version", v.getVersion())
                        + kv("date", v.getModifyDate() == null ? null : "cal")
                        + kvLast("event", v.getEvent() == null ? null : "evt");
            }

            // --- Dimensions getW/getH/getUnit round-trips ----------------
            case "dim_set_floats": {
                // Upstream DimensionsType has NO public setters; the only way to
                // populate it from outside the package is the protected
                // addSimpleProperty. Field type for w/h is RealType (Float).
                DimensionsType d = new DimensionsType(meta);
                addSimple(d, DimensionsType.W, 2.5f);
                addSimple(d, DimensionsType.H, 3.0f);
                addSimple(d, DimensionsType.UNIT, "inch");
                return kv("w", d.getW()) + kv("h", d.getH()) + kvLast("unit", d.getUnit());
            }
            case "dim_set_nan": {
                DimensionsType d = new DimensionsType(meta);
                addSimple(d, DimensionsType.W, Float.NaN);
                addSimple(d, DimensionsType.H, Float.POSITIVE_INFINITY);
                return kv("w", d.getW()) + kvLast("h", d.getH());
            }
            case "dim_set_zero": {
                DimensionsType d = new DimensionsType(meta);
                addSimple(d, DimensionsType.W, 0f);
                addSimple(d, DimensionsType.H, -1.5f);
                return kv("w", d.getW()) + kvLast("h", d.getH());
            }
            case "dim_unit_empty": {
                DimensionsType d = new DimensionsType(meta);
                addSimple(d, DimensionsType.UNIT, "");
                return kvLast("unit", d.getUnit());
            }
            // w field set to a NON-Real (Text) via addSimpleProperty -> typed
            // getW must cope (cast). Project class + getW outcome.
            case "dim_w_wrong_type": {
                DimensionsType d = new DimensionsType(meta);
                addSimple(d, DimensionsType.W, "notanumber");
                // getW does a cast to RealType internally; capture what happens.
                return kvLast("w", d.getW());
            }
            case "dim_tostring_empty": {
                DimensionsType d = new DimensionsType(meta);
                return kvLast("ts", d.toString());
            }
            case "dim_tostring_set": {
                DimensionsType d = new DimensionsType(meta);
                addSimple(d, DimensionsType.W, 4f);
                addSimple(d, DimensionsType.H, 5f);
                addSimple(d, DimensionsType.UNIT, "px");
                return kvLast("ts", d.toString());
            }

            // --- Job round-trip + namespace / prefix ---------------------
            case "job_set_get": {
                JobType j = new JobType(meta);
                j.setId("J1");
                j.setName("nightly");
                j.setUrl("http://x/");
                return kv("id", j.getId()) + kv("name", j.getName()) + kvLast("url", j.getUrl());
            }
            case "job_ns_prefix": {
                JobType j = new JobType(meta);
                return kv("ns", j.getNamespace()) + kvLast("pfx", j.getPrefix());
            }
            case "job_field_ns": {
                JobType j = new JobType(meta);
                j.setId("J1");
                AbstractField f = j.getProperty(JobType.ID);
                return kv("found", f != null)
                        + kv("fns", f == null ? null : f.getNamespace())
                        + kvLast("fpfx", f == null ? null : f.getPrefix());
            }
            // set twice: addProperty replaces, not appends (getAllProperties size 1)
            case "job_set_twice": {
                JobType j = new JobType(meta);
                j.setId("first");
                j.setId("second");
                return kv("count", j.getAllProperties().size()) + kvLast("id", j.getId());
            }
            case "job_order": {
                JobType j = new JobType(meta);
                j.setUrl("u");
                j.setName("n");
                j.setId("i");
                return kvLast("order", names(j));
            }
            case "job_set_null": {
                JobType j = new JobType(meta);
                j.setId(null);
                return kvLast("id", j.getId());
            }

            // --- Thumbnail integer field fuzz ----------------------------
            case "thumb_set_get": {
                ThumbnailType t = new ThumbnailType(meta);
                t.setWidth(64);
                t.setHeight(48);
                t.setFormat("JPEG");
                t.setImage("/9j/base64");
                return kv("w", t.getWidth())
                        + kv("h", t.getHeight())
                        + kv("fmt", t.getFormat())
                        + kvLast("img", t.getImage());
            }
            case "thumb_zero": {
                ThumbnailType t = new ThumbnailType(meta);
                t.setWidth(0);
                t.setHeight(-5);
                return kv("w", t.getWidth()) + kvLast("h", t.getHeight());
            }
            case "thumb_img_empty": {
                ThumbnailType t = new ThumbnailType(meta);
                t.setImage("");
                return kvLast("img", t.getImage());
            }
            // height field set to a Text "abc" via addSimpleProperty: getHeight
            // casts to IntegerType. Project outcome.
            case "thumb_h_wrong_type": {
                ThumbnailType t = new ThumbnailType(meta);
                addSimple(t, ThumbnailType.HEIGHT, "abc");
                return kvLast("h", t.getHeight());
            }
            case "thumb_order": {
                ThumbnailType t = new ThumbnailType(meta);
                t.setImage("img");
                t.setFormat("PNG");
                t.setHeight(10);
                t.setWidth(20);
                return kvLast("order", names(t));
            }

            // --- Layer round-trip ----------------------------------------
            case "layer_set_get": {
                LayerType l = new LayerType(meta);
                l.setLayerName("Layer 1");
                l.setLayerText("hello");
                return kv("name", l.getLayerName()) + kvLast("text", l.getLayerText());
            }
            case "layer_empty_str": {
                LayerType l = new LayerType(meta);
                l.setLayerName("");
                return kvLast("name", l.getLayerName());
            }
            case "layer_order": {
                LayerType l = new LayerType(meta);
                l.setLayerText("t");
                l.setLayerName("n");
                return kvLast("order", names(l));
            }

            // --- ResourceRef field surface -------------------------------
            case "ref_set_get": {
                ResourceRefType r = new ResourceRefType(meta);
                r.setDocumentID("uuid:doc");
                r.setInstanceID("uuid:inst");
                r.setRenditionClass("default");
                r.setVersionID("3");
                return kv("doc", r.getDocumentID())
                        + kv("inst", r.getInstanceID())
                        + kv("rc", r.getRenditionClass())
                        + kvLast("ver", r.getVersionID());
            }
            case "ref_alt_paths": {
                ResourceRefType r = new ResourceRefType(meta);
                r.addAlternatePath("a");
                r.addAlternatePath("b");
                List<String> alts = r.getAlternatePaths();
                return kv("size", alts == null ? -1 : alts.size())
                        + kvLast("vals", alts == null ? null : String.join(",", alts));
            }
            case "ref_alt_empty": {
                ResourceRefType r = new ResourceRefType(meta);
                return kvLast("alt", r.getAlternatePaths() == null ? null : "list");
            }
            case "ref_alt_one_empty": {
                ResourceRefType r = new ResourceRefType(meta);
                r.addAlternatePath("");
                List<String> alts = r.getAlternatePaths();
                return kv("size", alts == null ? -1 : alts.size())
                        + kvLast("v0", alts == null || alts.isEmpty() ? null : alts.get(0));
            }
            case "ref_field_ns": {
                ResourceRefType r = new ResourceRefType(meta);
                r.setDocumentID("d");
                AbstractField f = r.getProperty(ResourceRefType.DOCUMENT_ID);
                return kv("fns", f == null ? null : f.getNamespace())
                        + kvLast("fpfx", f == null ? null : f.getPrefix());
            }
            case "ref_mask_markers": {
                ResourceRefType r = new ResourceRefType(meta);
                r.setMaskMarkers("All");
                return kvLast("mm", r.getMaskMarkers());
            }

            // --- Version round-trip + nested event -----------------------
            case "ver_set_get": {
                VersionType v = new VersionType(meta);
                v.setComments("c");
                v.setVersion("2.0");
                v.setModifier("Bob");
                return kv("comments", v.getComments())
                        + kv("version", v.getVersion())
                        + kvLast("modifier", v.getModifier());
            }
            case "ver_ns_prefix": {
                VersionType v = new VersionType(meta);
                return kv("ns", v.getNamespace()) + kvLast("pfx", v.getPrefix());
            }
            case "ver_order": {
                VersionType v = new VersionType(meta);
                v.setVersion("v");
                v.setComments("c");
                v.setModifier("m");
                return kvLast("order", names(v));
            }

            default:
                return "ERR" + US + "UnknownCase";
        }
    }

    /** Invoke the protected {@code addSimpleProperty(String, Object)} via
     * reflection so the default-package probe can reach it. */
    private static void addSimple(AbstractStructuredType t, String name, Object value)
            throws Exception {
        java.lang.reflect.Method m = AbstractStructuredType.class
                .getDeclaredMethod("addSimpleProperty", String.class, Object.class);
        m.setAccessible(true);
        m.invoke(t, name, value);
    }

    private static String names(AbstractStructuredType t) {
        List<String> ns = new ArrayList<>();
        for (AbstractField f : t.getAllProperties()) {
            ns.add(f.getPropertyName());
        }
        return String.join(",", ns);
    }

    private static String kv(String k, Object v) {
        return k + "=" + String.valueOf(v) + US;
    }

    private static String kvLast(String k, Object v) {
        return k + "=" + String.valueOf(v);
    }
}
