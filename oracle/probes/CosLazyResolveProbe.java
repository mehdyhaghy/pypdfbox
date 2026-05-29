import java.io.File;
import java.io.PrintStream;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Live oracle probe for COSObject lazy indirect resolution.
 *
 * Loads a hand-built PDF (passed as a file path) whose catalog carries a fixed
 * set of indirect references that exercise the COSObject reference surface, then
 * drives Apache PDFBox 3.0.7's lazy-resolution machinery and emits one canonical
 * JSON object so the Python side can assert byte/behaviour parity of:
 *
 *   - object-pool dedup IDENTITY: two distinct ``N G R`` references to the SAME
 *     object number/generation resolve, through ``COSDocument.getObjectFromPool``,
 *     to the SAME ``COSObject`` instance, and ``getObject()`` on each yields the
 *     SAME underlying ``COSBase`` instance (one parse, one shared base);
 *   - lazy on-demand parse: ``COSObject.getObject()`` triggers the body parse
 *     (the resolved type is what the body defines);
 *   - a reference to a NON-EXISTENT object (no xref entry, dangling) dereferences
 *     to null — ``getObject()`` is null and ``isObjectNull()`` is true;
 *   - ``isObjectNull()`` is false for a live reference once resolved;
 *   - a SELF reference (object whose value is a dict pointing at itself) and a
 *     two-object CYCLE both resolve without infinite recursion, and the
 *     self-reference's resolved base is identical to the COSObject's own
 *     resolved base (the cycle closes on the same instance).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> CosLazyResolveProbe input.pdf
 *
 * Output (UTF-8, to stdout): a single JSON object, keys sorted (TreeMap), with
 * identity comparisons rendered as JSON booleans and types rendered as coarse
 * tags so the comparison is repr-independent.
 */
public final class CosLazyResolveProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument pd = Loader.loadPDF(new File(args[0]))) {
            COSDocument doc = pd.getDocument();
            COSDictionary catalog = pd.getDocumentCatalog().getCOSObject();

            TreeMap<String, Object> root = new TreeMap<>();

            // --- dedup identity: /SharedA and /SharedB both -> the same object.
            COSBase rawA = catalog.getItem(COSName.getPDFName("SharedA"));
            COSBase rawB = catalog.getItem(COSName.getPDFName("SharedB"));
            root.put("sharedA_is_object", rawA instanceof COSObject);
            root.put("sharedB_is_object", rawB instanceof COSObject);
            // The raw items are the SAME COSObject instance (pool dedup).
            root.put("shared_raw_same_ref", rawA == rawB);
            COSObject objA = (COSObject) rawA;
            COSObject objB = (COSObject) rawB;
            // Pool lookups by key also yield the SAME COSObject.
            COSObject pooled = doc.getObjectFromPool(
                    new COSObjectKey(objA.getObjectNumber(), objA.getGenerationNumber()));
            root.put("shared_pool_same_ref", pooled == objA);
            // Resolving each ref yields the SAME underlying base instance.
            COSBase baseA = objA.getObject();
            COSBase baseB = objB.getObject();
            root.put("shared_base_same", baseA == baseB);
            root.put("shared_type", typeTag(baseA));
            root.put("sharedA_object_null", objA.isObjectNull());

            // --- dangling reference: /Dangling -> a non-existent object.
            COSBase rawD = catalog.getItem(COSName.getPDFName("Dangling"));
            root.put("dangling_is_object", rawD instanceof COSObject);
            COSObject objD = (COSObject) rawD;
            COSBase baseD = objD.getObject();
            root.put("dangling_base_null", baseD == null);
            root.put("dangling_object_null", objD.isObjectNull());
            // getDictionaryObject collapses the dangling reference to null.
            root.put("dangling_dictobj_null",
                    catalog.getDictionaryObject(COSName.getPDFName("Dangling")) == null);

            // --- self reference: object 20 is a dict with /Me -> 20 0 R.
            COSBase rawSelf = catalog.getItem(COSName.getPDFName("SelfRef"));
            COSObject objSelf = (COSObject) rawSelf;
            COSBase baseSelf = objSelf.getObject();
            root.put("self_type", typeTag(baseSelf));
            COSDictionary selfDict = (COSDictionary) baseSelf;
            COSBase rawMe = selfDict.getItem(COSName.getPDFName("Me"));
            root.put("self_me_is_object", rawMe instanceof COSObject);
            COSObject objMe = (COSObject) rawMe;
            // The self pointer dereferences to the SAME base — cycle closes.
            root.put("self_cycle_same_base", objMe.getObject() == baseSelf);
            // And the inner COSObject is the SAME pooled instance as the outer.
            root.put("self_cycle_same_ref", objMe == objSelf);

            // --- two-object cycle: 30 -> /Next 31 0 R, 31 -> /Next 30 0 R.
            COSObject obj30 = (COSObject) catalog.getItem(COSName.getPDFName("CycleHead"));
            COSDictionary d30 = (COSDictionary) obj30.getObject();
            COSObject obj31 = (COSObject) d30.getItem(COSName.getPDFName("Next"));
            COSDictionary d31 = (COSDictionary) obj31.getObject();
            COSObject back = (COSObject) d31.getItem(COSName.getPDFName("Next"));
            // Following the cycle one full turn lands on the SAME base as 30.
            root.put("cycle_closes_same_base", back.getObject() == d30);
            root.put("cycle_back_same_ref", back == obj30);

            // --- an indirect ref inside an array dedups too: /Arr [10 0 R 10 0 R].
            COSArray arr = (COSArray) catalog.getDictionaryObject(COSName.getPDFName("Arr"));
            COSBase arr0 = arr.get(0);
            COSBase arr1 = arr.get(1);
            root.put("arr_elems_same_ref", arr0 == arr1);
            // And the array element is the SAME pooled COSObject as /SharedA.
            root.put("arr_elem_same_as_shared", arr0 == objA);

            out.print(jsonify(root));
        }
    }

    private static String typeTag(COSBase b) {
        if (b == null) {
            return "null";
        }
        if (b instanceof COSObject) {
            return "object";
        }
        if (b instanceof COSArray) {
            return "array";
        }
        if (b instanceof COSDictionary) {
            return "dict";
        }
        return "other:" + b.getClass().getSimpleName();
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
        } else if (value instanceof Map<?, ?>) {
            sb.append("{");
            boolean first = true;
            for (Map.Entry<?, ?> e : ((Map<?, ?>) value).entrySet()) {
                if (!first) {
                    sb.append(",");
                }
                first = false;
                emitString(sb, String.valueOf(e.getKey()));
                sb.append(":");
                emit(sb, e.getValue());
            }
            sb.append("}");
        } else if (value instanceof List<?>) {
            sb.append("[");
            List<?> list = (List<?>) value;
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
