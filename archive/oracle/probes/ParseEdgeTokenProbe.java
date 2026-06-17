import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.contentstream.operator.Operator;

/**
 * Live oracle probe: tokenize a raw content-stream byte snippet through Apache
 * PDFBox's PDFStreamParser and emit each token's canonical fingerprint. This
 * exercises the exact BaseParser scalar-parse code paths (parseCOSNumber,
 * parseCOSString, parseCOSName, the content-stream double-negative / mid-dash
 * recovery, octal escapes, name #-hex escapes) that pypdfbox must match.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ParseEdgeTokenProbe snippet.bin
 *
 * The argument is a path to a file holding the raw operand/operator bytes
 * (NOT a full PDF). Output (UTF-8, LF-terminated), one line per token:
 *
 *   int(<decimal>)
 *   real(<float32-bits-hex>)
 *   name(/Foo)              # decoded name
 *   str(<hex-of-bytes>)     # raw decoded string bytes, hex
 *   bool(true|false)
 *   null
 *   op(<operator>)
 *   array[...]              # nested token tags joined by ','
 *   dict{/K->tag,...}
 */
public final class ParseEdgeTokenProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] data = Files.readAllBytes(Paths.get(args[0]));
        PDFStreamParser parser = new PDFStreamParser(data);
        StringBuilder sb = new StringBuilder();
        Object token;
        while ((token = parser.parseNextToken()) != null) {
            sb.append(tag(token)).append('\n');
        }
        out.print(sb);
    }

    private static String tag(Object token) throws Exception {
        if (token instanceof Operator) {
            return "op(" + ((Operator) token).getName() + ")";
        }
        return cosTag((COSBase) token);
    }

    private static String cosTag(COSBase base) throws Exception {
        if (base == null || base instanceof COSNull) {
            return "null";
        }
        if (base instanceof COSBoolean) {
            return "bool(" + (((COSBoolean) base).getValue() ? "true" : "false") + ")";
        }
        if (base instanceof COSInteger) {
            return "int(" + ((COSInteger) base).longValue() + ")";
        }
        if (base instanceof COSFloat) {
            return "real(" + Integer.toHexString(
                    Float.floatToIntBits(((COSFloat) base).floatValue())) + ")";
        }
        if (base instanceof COSName) {
            return "name(/" + ((COSName) base).getName() + ")";
        }
        if (base instanceof COSString) {
            return "str(" + hex(((COSString) base).getBytes()) + ")";
        }
        if (base instanceof COSArray) {
            COSArray a = (COSArray) base;
            StringBuilder sb = new StringBuilder("array[");
            for (int i = 0; i < a.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                sb.append(cosTag(a.get(i)));
            }
            return sb.append(']').toString();
        }
        if (base instanceof COSDictionary) {
            COSDictionary d = (COSDictionary) base;
            java.util.List<COSName> keys = new java.util.ArrayList<>(d.keySet());
            keys.sort((x, y) -> x.getName().compareTo(y.getName()));
            StringBuilder sb = new StringBuilder("dict{");
            boolean first = true;
            for (COSName k : keys) {
                if (!first) {
                    sb.append(',');
                }
                first = false;
                sb.append('/').append(k.getName()).append("->").append(cosTag(d.getItem(k)));
            }
            return sb.append('}').toString();
        }
        return "unknown(" + base.getClass().getSimpleName() + ")";
    }

    private static String hex(byte[] data) {
        StringBuilder sb = new StringBuilder();
        for (byte b : data) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }
}
