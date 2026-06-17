import java.io.File;
import java.io.PrintStream;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: catalog (/Root) recovery via brute-force catalog scan.
 *
 * Apache PDFBox's {@code COSParser.retrieveTrailer} fires a brute-force rebuild
 * when the cleanly-parsed xref's trailer carries NO {@code /Root} item (the key
 * itself is absent — checked raw via {@code getItem}, not resolved). The
 * rebuild ({@code BruteForceParser.rebuildTrailer}) re-scans the body for
 * {@code n g obj} definitions, and the FIRST object advertising
 * {@code /Type /Catalog} becomes the recovered {@code /Root}; the trailer is
 * repaired and the document opens normally. A trailer whose {@code /Root} key
 * IS present but DANGLES (points at a missing / non-catalog object) is NOT
 * rebuilt — upstream lets that surface as the {@code initialParse} "Missing
 * root object specification in trailer." failure.
 *
 * This probe drives PDFBox's full {@code Loader.loadPDF} path (which calls
 * {@code initialParse}) and emits the RECOVERED facts so pypdfbox can be held
 * to the same outcome — recovered catalog object number + page count, not byte
 * offsets.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> RootRecoveryProbe input.pdf
 *
 * Output (UTF-8, single JSON object, keys sorted by TreeMap). On success:
 *   catalog  -> "<objNum> <gen>"   resolved trailer /Root indirect-ref key
 *   info     -> "present"|"absent" whether trailer carries a resolvable /Info
 *   objects  -> int                COSDocument xref-table object count
 *   pages    -> int                getNumberOfPages()
 *   root     -> "present"|"absent" whether trailer /Root resolves to a dict
 *   text     -> stripped text, \n/\r/\\ escaped
 *
 * On any throw in load / strip the sole output is the JSON object:
 *   {"status":"PARSE_FAIL"}
 */
public final class RootRecoveryProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        TreeMap<String, Object> result = new TreeMap<>();
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            COSDocument cos = doc.getDocument();
            COSDictionary trailer = cos.getTrailer();
            int pages = doc.getNumberOfPages();
            int objects = cos.getXrefTable().size();

            COSBase rootObj = trailer != null
                    ? trailer.getDictionaryObject(COSName.ROOT) : null;
            boolean root = rootObj instanceof COSDictionary;
            COSBase rawRoot = trailer != null ? trailer.getItem(COSName.ROOT) : null;
            String catalog = "absent";
            if (rawRoot instanceof COSObject) {
                COSObject ref = (COSObject) rawRoot;
                catalog = ref.getObjectNumber() + " " + ref.getGenerationNumber();
            } else if (rawRoot instanceof COSDictionary) {
                catalog = "direct";
            }
            boolean info = trailer != null && trailer.getDictionaryObject(
                    COSName.getPDFName("Info")) != null;
            String text = new PDFTextStripper().getText(doc);

            result.put("pages", pages);
            result.put("objects", objects);
            result.put("root", root ? "present" : "absent");
            result.put("catalog", catalog);
            result.put("info", info ? "present" : "absent");
            result.put("text", escape(text));
        } catch (Throwable t) {
            TreeMap<String, Object> fail = new TreeMap<>();
            fail.put("status", "PARSE_FAIL");
            out.print(jsonify(fail));
            return;
        }
        out.print(jsonify(result));
    }

    private static String escape(String s) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '\n') {
                b.append("\\n");
            } else if (c == '\r') {
                b.append("\\r");
            } else if (c == '\\') {
                b.append("\\\\");
            } else {
                b.append(c);
            }
        }
        return b.toString();
    }

    // --- minimal JSON emitter (TreeMap / String / Integer / Boolean) ---

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
