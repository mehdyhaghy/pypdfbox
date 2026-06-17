import java.io.OutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfparser.PDFObjectStreamParser;

/**
 * Differential fuzz probe for {@code PDFObjectStreamParser} INTERNAL parsing,
 * Apache PDFBox 3.0.7 (wave 1547, agent D).
 *
 * <p>Complements the well-formed direct-parser oracle
 * ({@code test_obj_stream_parse_oracle.py} / {@code ObjStmParseProbe}, which
 * crashes on a malformed body) and the loader-driven leniency fuzz
 * ({@code test_objstm_fuzz_wave1516.py} / {@code ObjStmFuzzProbe}, which only
 * inspects the final lazy-resolved value of a single member through
 * {@code Loader.loadPDF}). Neither exposes what the header-table reader and the
 * object-extraction walk actually PRODUCE on a malformed body — the
 * {@code {objNum: offset}} table from {@code readObjectNumbers()} and the
 * {@code {COSObjectKey: COSBase}} map from {@code parseAllObjects()}, with the
 * exception (if any) surfaced per-method. That contract is what this probe pins.
 *
 * <p><b>Driver model.</b> File-driven: the pypdfbox sibling writes one
 * {@code <name>.bin} per case (the RAW, unfiltered ObjStm body bytes) plus a
 * {@code manifest.txt} whose lines are {@code <name> <N> <First>}. This probe
 * reads the identical bytes, stamps {@code /N} and {@code /First} onto a fresh
 * {@link COSStream}, and drives the upstream parser directly — isolating the
 * body parse from any xref/document plumbing.
 *
 * <p><b>Output grammar</b> — exactly one line per case, in manifest order:
 * <pre>
 *   CASE &lt;name&gt; numbers=&lt;proj&gt; objects=&lt;proj&gt;
 * </pre>
 * where each {@code <proj>} is either {@code ERR:&lt;ExcSimpleName&gt;} (the
 * method threw) or a deterministic, order-independent rendering:
 * <ul>
 *   <li>{@code numbers} → {@code [num=off,num=off,...]} sorted by object
 *       number (upstream returns an unordered map; sorting canonicalises it);
 *   <li>{@code objects} → {@code [num/gen:kind:value,...]} sorted by object
 *       number, where {@code value} is the same compact projection
 *       {@code ObjStmParseProbe} uses ({@code type|tag} for a dict, the name /
 *       string / long value otherwise, {@code null} for a null member).
 * </ul>
 *
 * <p>Usage: {@code java -cp <cp> ObjStmParseFuzzProbe <corpus-dir>}
 */
public final class ObjStmParseFuzzProbe {

    static PrintStream out;

    static COSStream newObjStm(COSDocument doc, byte[] body, int n, int first)
            throws Exception {
        COSStream stream = doc.createCOSStream();
        stream.setItem(COSName.TYPE, COSName.getPDFName("ObjStm"));
        stream.setItem(COSName.N, COSInteger.get(n));
        stream.setItem(COSName.FIRST, COSInteger.get(first));
        try (OutputStream os = stream.createRawOutputStream()) {
            os.write(body);
        }
        return stream;
    }

    static String projectNumbers(COSDocument doc, byte[] body, int n, int first) {
        try {
            COSStream s = newObjStm(doc, body, n, first);
            Map<Long, Integer> numbers =
                    new PDFObjectStreamParser(s, doc).readObjectNumbers();
            TreeMap<Long, Integer> sorted = new TreeMap<>(numbers);
            StringBuilder b = new StringBuilder("[");
            boolean first2 = true;
            for (Map.Entry<Long, Integer> e : sorted.entrySet()) {
                if (!first2) {
                    b.append(",");
                }
                first2 = false;
                b.append(e.getKey()).append("=").append(e.getValue());
            }
            return b.append("]").toString();
        } catch (Throwable t) {
            return "ERR:" + t.getClass().getSimpleName();
        }
    }

    static String projectObjects(COSDocument doc, byte[] body, int n, int first) {
        try {
            COSStream s = newObjStm(doc, body, n, first);
            Map<COSObjectKey, COSBase> objects =
                    new PDFObjectStreamParser(s, doc).parseAllObjects();
            TreeMap<Long, String> sorted = new TreeMap<>();
            for (Map.Entry<COSObjectKey, COSBase> e : objects.entrySet()) {
                COSObjectKey key = e.getKey();
                COSBase v = e.getValue();
                sorted.put(key.getNumber(),
                        key.getNumber() + "/" + key.getGeneration() + ":"
                                + kind(v) + ":" + value(v));
            }
            List<String> parts = new ArrayList<>(sorted.values());
            return "[" + String.join(",", parts) + "]";
        } catch (Throwable t) {
            return "ERR:" + t.getClass().getSimpleName();
        }
    }

    static String kind(COSBase v) {
        if (v == null) {
            return "null";
        }
        if (v instanceof COSDictionary) {
            return "dict";
        }
        if (v instanceof COSName) {
            return "name";
        }
        if (v instanceof COSString) {
            return "string";
        }
        if (v instanceof COSNumber) {
            return "number";
        }
        return v.getClass().getSimpleName();
    }

    static String value(COSBase v) {
        if (v instanceof COSDictionary) {
            COSDictionary d = (COSDictionary) v;
            COSBase type = d.getDictionaryObject(COSName.TYPE);
            COSBase tag = d.getDictionaryObject(COSName.getPDFName("Tag"));
            String t = type instanceof COSName ? ((COSName) type).getName() : "";
            String g = tag instanceof COSString ? ((COSString) tag).getString() : "";
            return esc(t) + "|" + esc(g);
        }
        if (v instanceof COSName) {
            return esc(((COSName) v).getName());
        }
        if (v instanceof COSString) {
            return esc(((COSString) v).getString());
        }
        if (v instanceof COSNumber) {
            return Long.toString(((COSNumber) v).longValue());
        }
        return "null";
    }

    static String esc(String s) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == ',' || c == '|' || c == ':' || c == '[' || c == ']') {
                b.append('_');
            } else if (c == '\n' || c == '\r') {
                b.append(' ');
            } else {
                b.append(c);
            }
        }
        return b.toString();
    }

    static void runCase(java.io.File dir, String name, int n, int first)
            throws Exception {
        byte[] body = Files.readAllBytes(new java.io.File(dir, name + ".bin").toPath());
        // Each method consumes the source view, so build a fresh stream per call.
        try (COSDocument doc = new COSDocument()) {
            String numbers = projectNumbers(doc, body, n, first);
            String objects = projectObjects(doc, body, n, first);
            out.println("CASE " + name + " numbers=" + numbers
                    + " objects=" + objects);
        }
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        java.io.File dir = new java.io.File(args[0]);
        String manifest = new String(
                Files.readAllBytes(Paths.get(dir.getPath(), "manifest.txt")),
                StandardCharsets.UTF_8);
        for (String line : manifest.split("\n")) {
            String row = line.trim();
            if (row.isEmpty()) {
                continue;
            }
            String[] f = row.split("\\s+");
            runCase(dir, f[0], Integer.parseInt(f[1]), Integer.parseInt(f[2]));
        }
    }
}
