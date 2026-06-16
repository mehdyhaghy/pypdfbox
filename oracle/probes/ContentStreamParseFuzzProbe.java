import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.contentstream.operator.Operator;

/**
 * Live oracle probe: differential-fuzz Apache PDFBox's content-stream
 * tokenizer (PDFStreamParser) over malformed / edge-case operand+operator
 * byte blobs. Complements ParseEdgeTokenProbe / TokenizeProbe by pushing on
 * the lenient-recovery corners: pathological numbers, name #-escapes, literal
 * and hex strings, unterminated arrays/dicts, no-whitespace operator/operand
 * adjacency, comments mid-token, null bytes, and mid-token truncation.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ContentStreamParseFuzzProbe blob.bin
 *
 * The argument is a path to a file holding raw content-stream bytes (NOT a
 * full PDF). The whole token stream is drained with parse(); a throw is
 * projected as a single trailing ``ERR:<ExceptionSimpleName>`` line so a
 * parse error is itself a comparable observation. Output (UTF-8, LF):
 *
 *   int(<decimal>)
 *   real(<float32-bits-hex>)        # raw IEEE-754 bits, exact, locale-free
 *   name(/Foo)
 *   str(<hex-of-bytes>)
 *   bool(true|false)
 *   null
 *   op(<operator>)                  # ID carries image data, see below
 *   imgdata(<len>:<hex>)            # raw inline-image bytes of preceding ID/BI
 *   array[...]                      # nested token tags joined by ','
 *   dict{/K->tag,...}               # keys sorted, like ParseEdgeTokenProbe
 *   ref(<num> <gen>)                # unresolved COSObject (indirect ref)
 *   ERR:<ExceptionSimpleName>       # parse() threw; final line
 */
public final class ContentStreamParseFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] data = Files.readAllBytes(Paths.get(args[0]));
        StringBuilder sb = new StringBuilder();
        PDFStreamParser parser = new PDFStreamParser(data);
        try {
            Object token;
            while ((token = parser.parseNextToken()) != null) {
                sb.append(tag(token)).append('\n');
            }
        } catch (Exception e) {
            sb.append("ERR:").append(e.getClass().getSimpleName()).append('\n');
        }
        out.print(sb);
    }

    private static String tag(Object token) {
        if (token instanceof Operator) {
            Operator op = (Operator) token;
            String s = "op(" + op.getName() + ")";
            byte[] img = op.getImageData();
            if (img != null) {
                s += "\nimgdata(" + img.length + ":" + hex(img) + ")";
            }
            return s;
        }
        return cosTag((COSBase) token);
    }

    private static String cosTag(COSBase base) {
        if (base == null || base instanceof COSNull) {
            return "null";
        }
        if (base instanceof COSObject) {
            COSObject o = (COSObject) base;
            return "ref(" + o.getObjectNumber() + " " + o.getGenerationNumber() + ")";
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
