import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Live oracle probe: emit a CANONICAL, deterministic fingerprint of the COS
 * object graph that a PDF parses into. The pypdfbox side produces the exact
 * same format so the two can be compared character-for-character.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> CosDumpProbe input.pdf
 *
 * Output (UTF-8, LF-terminated lines), one line per indirect object, sorted by
 * (objNum, genNum):
 *
 *   <objNum> <genNum>: <typetag>
 *
 * Where <typetag> is a recursively-built structural description. Leaf scalars
 * carry their normalized value; composite objects carry their shape. Indirect
 * references are rendered as ref(N G) WITHOUT following them (the referenced
 * object gets its own top-level line), so the dump is finite and the graph is
 * flattened by object number rather than by traversal — robust against cycles.
 *
 * Canonical normalizations (must match pypdfbox dumper exactly):
 *   - null            -> null
 *   - boolean         -> bool(true) / bool(false)
 *   - integer         -> int(<decimal>)
 *   - float           -> real(<g-format, see fmtFloat>)
 *   - name            -> name(/Foo)
 *   - string          -> str(len=<n>)            (bytes length only; raw bytes
 *                         are too encoding/encryption brittle to compare)
 *   - array           -> array[<elt0>,<elt1>,...]
 *   - dictionary      -> dict{/A->t,/B->t,...}   (keys sorted)
 *   - stream          -> stream{/A->t,...}(rawlen=<n>)  (raw/encoded byte
 *                         length; the dict is dumped like a dictionary)
 *   - reference        -> ref(N G)
 */
public final class CosDumpProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument pd = Loader.loadPDF(new File(args[0]))) {
            COSDocument doc = pd.getDocument();
            // The xref table is the authoritative set of indirect objects the
            // parser registered. Sort its keys by (objNum, genNum) for a
            // deterministic, traversal-independent dump.
            TreeMap<long[], COSObjectKey> sorted =
                    new TreeMap<>((a, b) -> {
                        if (a[0] != b[0]) {
                            return Long.compare(a[0], b[0]);
                        }
                        return Long.compare(a[1], b[1]);
                    });
            for (COSObjectKey key : doc.getXrefTable().keySet()) {
                sorted.put(new long[] {key.getNumber(), key.getGeneration()}, key);
            }
            StringBuilder sb = new StringBuilder();
            for (Map.Entry<long[], COSObjectKey> e : sorted.entrySet()) {
                long objNum = e.getKey()[0];
                long genNum = e.getKey()[1];
                COSBase resolved;
                try {
                    resolved = doc.getObjectFromPool(e.getValue()).getObject();
                } catch (Exception ex) {
                    resolved = null;
                }
                sb.append(objNum).append(' ').append(genNum).append(": ")
                        .append(typeTag(resolved)).append('\n');
            }
            out.print(sb);
        }
    }

    /** Render a COSBase as its canonical type-tag. Indirect refs are NOT
     * followed (rendered as ref(N G)); the resolved object appears on its own
     * top-level line. */
    private static String typeTag(COSBase base) {
        if (base == null) {
            return "null";
        }
        if (base instanceof COSObject) {
            COSObject o = (COSObject) base;
            return "ref(" + o.getObjectNumber() + " " + o.getGenerationNumber() + ")";
        }
        if (base instanceof COSNull) {
            return "null";
        }
        if (base instanceof COSBoolean) {
            return "bool(" + (((COSBoolean) base).getValue() ? "true" : "false") + ")";
        }
        if (base instanceof COSInteger) {
            return "int(" + ((COSInteger) base).longValue() + ")";
        }
        if (base instanceof COSFloat) {
            return "real(" + fmtFloat(((COSFloat) base).floatValue()) + ")";
        }
        if (base instanceof COSName) {
            return "name(/" + ((COSName) base).getName() + ")";
        }
        if (base instanceof COSString) {
            return "str(len=" + ((COSString) base).getBytes().length + ")";
        }
        if (base instanceof COSStream) {
            // Stream extends dictionary; dump dict then raw (encoded) length.
            COSStream s = (COSStream) base;
            return "stream" + dictBody(s) + "(rawlen=" + rawLen(s) + ")";
        }
        if (base instanceof COSArray) {
            COSArray a = (COSArray) base;
            StringBuilder sb = new StringBuilder("array[");
            for (int i = 0; i < a.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                // Raw element (do not dereference) so a ref stays a ref.
                sb.append(typeTag(a.get(i)));
            }
            sb.append(']');
            return sb.toString();
        }
        if (base instanceof COSDictionary) {
            return "dict" + dictBody((COSDictionary) base);
        }
        return "unknown(" + base.getClass().getSimpleName() + ")";
    }

    /** {/Key->typetag,...} body with keys sorted by name. Skips the
     * stream-only /Length entry so a value-based /Length and an indirect
     * /Length compare identically (rawlen is reported separately). */
    private static String dictBody(COSDictionary d) {
        List<COSName> keys = new ArrayList<>(d.keySet());
        Collections.sort(keys, (x, y) -> x.getName().compareTo(y.getName()));
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (COSName k : keys) {
            if (d instanceof COSStream && k.equals(COSName.LENGTH)) {
                continue;
            }
            if (!first) {
                sb.append(',');
            }
            first = false;
            sb.append('/').append(k.getName()).append("->").append(typeTag(d.getItem(k)));
        }
        sb.append('}');
        return sb.toString();
    }

    /** Raw (encoded) byte length of a stream body — read straight off the
     * raw input stream (no filter decode), so the count is the on-disk
     * encoded length and never triggers a brittle filter round-trip. */
    private static long rawLen(COSStream s) {
        try (java.io.InputStream in = s.createRawInputStream()) {
            long n = 0;
            byte[] buf = new byte[8192];
            int r;
            while ((r = in.read(buf)) != -1) {
                n += r;
            }
            return n;
        } catch (Exception ex) {
            return -1;
        }
    }

    /** Deterministic float formatting shared with the pypdfbox dumper.
     *
     * We emit the raw IEEE-754 single-precision (float32) bit pattern in hex
     * rather than any decimal string. Decimal reprs differ subtly between
     * Java's Float.toString and Python's float formatting; the underlying
     * float32 bits do NOT — they are exactly comparable across both
     * languages (pypdfbox's COSFloat stores the value coerced through
     * float32, matching Java's float). This makes the dump repr-independent
     * while still catching any real parse-fidelity difference (a value parsed
     * to a different float32 shows different bits). */
    private static String fmtFloat(float f) {
        return Integer.toHexString(Float.floatToIntBits(f));
    }
}
