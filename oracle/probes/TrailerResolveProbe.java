import java.io.File;
import java.io.PrintStream;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Live oracle probe: resolve the consolidated document trailer of a
 * /Prev-chained, multi-section (incrementally-updated) PDF the way Apache
 * PDFBox 3.0.7 does, and emit a canonical JSON summary of the keys that the
 * trailer-merge actually produces.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TrailerResolveProbe input.pdf
 *
 * The merge rule under test (PDF 32000-1 §7.5.6 + PDFBox's
 * XrefTrailerResolver): the newest xref section's trailer keys win; keys the
 * newest section omits fall back down the /Prev chain. So an incremental
 * update that re-points /Root or adds /Info changes the resolved trailer even
 * though the base section still carries the old values.
 *
 * Output (UTF-8, single JSON object, keys sorted by TreeMap):
 *   root        -> "<objNum> <gen>"   indirect ref form of trailer /Root
 *   rootIsRef   -> bool               whether /Root is an indirect reference
 *   catalog     -> "<objNum> <gen>"   COSDocument.getCatalog() resolved key,
 *                                     or null when no catalog resolves
 *   catalogType -> "/Catalog" | null  the resolved catalog's /Type name
 *   info        -> "<objNum> <gen>"   indirect ref form of trailer /Info,
 *                                     omitted when absent
 *   size        -> int                trailer /Size
 *   encrypt     -> bool               whether trailer carries /Encrypt
 *   id          -> [len0, len1]       byte lengths of the two /ID strings,
 *                                     omitted when /ID absent
 * Absent optional keys are omitted entirely; the Python side mirrors the
 * same emit rules so the comparison is apples-to-apples.
 */
public final class TrailerResolveProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument pd = Loader.loadPDF(new File(args[0]))) {
            COSDocument doc = pd.getDocument();
            COSDictionary trailer = doc.getTrailer();

            TreeMap<String, Object> root = new TreeMap<>();

            // /Root — emit the indirect-reference key (object number + gen)
            // WITHOUT dereferencing, so a re-pointed /Root in a newer section
            // shows the new target number. This is the catalog object key:
            // resolving /Root IS getting the catalog, so the catalog's object
            // number is exactly /Root's referenced number.
            COSBase rawRoot = trailer.getItem(COSName.ROOT);
            if (rawRoot instanceof COSObject) {
                COSObject ref = (COSObject) rawRoot;
                String key = ref.getObjectNumber() + " " + ref.getGenerationNumber();
                root.put("root", key);
                root.put("rootIsRef", true);
                root.put("catalog", key);
                COSBase resolved = ref.getObject();
                if (resolved instanceof COSDictionary) {
                    COSBase type = ((COSDictionary) resolved).getItem(COSName.TYPE);
                    if (type instanceof COSName) {
                        root.put("catalogType", "/" + ((COSName) type).getName());
                    }
                }
            } else if (rawRoot instanceof COSDictionary) {
                root.put("root", "direct");
                root.put("rootIsRef", false);
                COSBase type = ((COSDictionary) rawRoot).getItem(COSName.TYPE);
                if (type instanceof COSName) {
                    root.put("catalogType", "/" + ((COSName) type).getName());
                }
            }

            // /Info — indirect-ref key form, omitted when absent.
            COSBase rawInfo = trailer.getItem(COSName.INFO);
            if (rawInfo instanceof COSObject) {
                COSObject ref = (COSObject) rawInfo;
                root.put("info", ref.getObjectNumber() + " " + ref.getGenerationNumber());
            }

            // /Size
            COSBase rawSize = trailer.getItem(COSName.SIZE);
            if (rawSize instanceof COSNumber) {
                root.put("size", ((COSNumber) rawSize).intValue());
            }

            // /Encrypt presence
            root.put("encrypt", trailer.containsKey(COSName.ENCRYPT));

            // /ID — byte lengths of both array entries.
            COSBase rawId = trailer.getItem(COSName.ID);
            if (rawId instanceof COSArray) {
                COSArray ids = (COSArray) rawId;
                java.util.List<Object> lens = new java.util.ArrayList<>();
                for (int i = 0; i < ids.size(); i++) {
                    COSBase e = ids.getObject(i);
                    if (e instanceof COSString) {
                        lens.add(((COSString) e).getBytes().length);
                    }
                }
                root.put("id", lens);
            }

            out.print(jsonify(root));
        }
    }

    // --- minimal JSON emitter (TreeMap / List / String / Integer / Boolean) ---

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
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) value).entrySet()) {
                if (!first) {
                    sb.append(",");
                }
                first = false;
                emitString(sb, String.valueOf(entry.getKey()));
                sb.append(":");
                emit(sb, entry.getValue());
            }
            sb.append("}");
        } else if (value instanceof java.util.List<?>) {
            java.util.List<?> list = (java.util.List<?>) value;
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
