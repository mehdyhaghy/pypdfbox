import java.io.OutputStream;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Map;
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
 * Live oracle probe for PDF 1.5+ object-stream (/Type /ObjStm) INTERNAL
 * parsing — the header offset table and the object-extraction ordering that
 * {@code org.apache.pdfbox.pdfparser.PDFObjectStreamParser} performs.
 *
 * The probe constructs a {@link COSStream} whose RAW (unfiltered) body is read
 * verbatim from a {@code .bin} fixture, stamps {@code /N} and {@code /First}
 * from the command line, and drives the upstream parser:
 *
 *   - {@code readObjectNumbers()} → the {@code {objectNumber: offset}} header
 *     table, exactly as upstream decodes the leading integer pairs.
 *   - {@code parseAllObjects()} → the {@code {COSObjectKey: COSBase}} result,
 *     emitted in the parser's own iteration order so the PDFBOX-4927
 *     duplicate-object-number / stream-index handling is observable.
 *
 * This isolates the ObjStm body parsing from any surrounding xref/document
 * plumbing: the same raw bytes + same /N + /First feed both libraries.
 *
 * Output: a single JSON object on stdout, e.g.
 *   {"numbers":[[3,0],[4,12]],"objects":[{"num":3,"gen":0,"kind":"name","value":"Foo"},...]}
 *
 * Usage:
 *   java -cp <cp> ObjStmParseProbe body.bin <N> <First>
 */
public final class ObjStmParseProbe {
    public static void main(String[] args) throws Exception {
        byte[] body = Files.readAllBytes(Paths.get(args[0]));
        int n = Integer.parseInt(args[1]);
        int first = Integer.parseInt(args[2]);

        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        sb.append("{");

        try (COSDocument doc = new COSDocument()) {
            // readObjectNumbers consumes the source, so build two streams.
            COSStream s1 = newObjStm(doc, body, n, first);
            Map<Long, Integer> numbers =
                new PDFObjectStreamParser(s1, doc).readObjectNumbers();
            sb.append("\"numbers\":[");
            boolean firstEntry = true;
            for (Map.Entry<Long, Integer> e : numbers.entrySet()) {
                if (!firstEntry) {
                    sb.append(",");
                }
                firstEntry = false;
                sb.append("[").append(e.getKey()).append(",")
                  .append(e.getValue()).append("]");
            }
            sb.append("],");

            COSStream s2 = newObjStm(doc, body, n, first);
            Map<COSObjectKey, COSBase> objects =
                new PDFObjectStreamParser(s2, doc).parseAllObjects();
            sb.append("\"objects\":[");
            firstEntry = true;
            for (Map.Entry<COSObjectKey, COSBase> e : objects.entrySet()) {
                if (!firstEntry) {
                    sb.append(",");
                }
                firstEntry = false;
                COSObjectKey key = e.getKey();
                COSBase v = e.getValue();
                sb.append("{\"num\":").append(key.getNumber())
                  .append(",\"gen\":").append(key.getGeneration())
                  .append(",\"kind\":\"").append(kind(v)).append("\"")
                  .append(",\"value\":").append(jsonValue(v))
                  .append("}");
            }
            sb.append("]");
        }
        sb.append("}");
        out.print(sb);
    }

    private static COSStream newObjStm(COSDocument doc, byte[] body, int n, int first)
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

    private static String kind(COSBase v) {
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

    private static String jsonValue(COSBase v) {
        if (v instanceof COSDictionary) {
            COSDictionary d = (COSDictionary) v;
            COSBase type = d.getDictionaryObject(COSName.TYPE);
            COSBase tag = d.getDictionaryObject(COSName.getPDFName("Tag"));
            String t = type instanceof COSName ? ((COSName) type).getName() : "";
            String g = tag instanceof COSString ? ((COSString) tag).getString() : "";
            return "\"" + esc(t) + "|" + esc(g) + "\"";
        }
        if (v instanceof COSName) {
            return "\"" + esc(((COSName) v).getName()) + "\"";
        }
        if (v instanceof COSString) {
            return "\"" + esc(((COSString) v).getString()) + "\"";
        }
        if (v instanceof COSNumber) {
            return Long.toString(((COSNumber) v).longValue());
        }
        return "null";
    }

    private static String esc(String s) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"' || c == '\\') {
                b.append('\\').append(c);
            } else if (c == '\n') {
                b.append("\\n");
            } else {
                b.append(c);
            }
        }
        return b.toString();
    }
}
