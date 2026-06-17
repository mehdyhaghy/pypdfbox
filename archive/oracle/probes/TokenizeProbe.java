import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;

/**
 * Live oracle probe: tokenize a page's content stream with Apache PDFBox's
 * PDFStreamParser and emit one canonical token per line.
 *
 * Usage:
 *   java -cp ... TokenizeProbe input.pdf pageIndex   (tokenize a page)
 *   java -cp ... TokenizeProbe stream.cs --raw       (tokenize raw bytes;
 *       lets us cover inline-image BI/ID/EI without a binary PDF fixture)
 *
 * Canonical token grammar (one per line, UTF-8):
 *   OP:<name>           operator keyword
 *   INT:<n>             COSInteger
 *   REAL:<canon>        COSFloat (canonicalized, locale-independent)
 *   NAME:/<n>           COSName
 *   STR:<hexbytes>      COSString (raw bytes, lower-hex)
 *   BOOL:true|false     COSBoolean
 *   NULL                COSNull
 *   ARRAY:<n>           COSArray header, then n element tokens follow
 *   DICT:<n>            COSDictionary header, then n key/value token pairs
 *   IMGDATA:<len>:<sha> inline-image bytes carried by the ID operator
 */
public final class TokenizeProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        if (args.length > 1 && "--raw".equals(args[1])) {
            byte[] bytes = Files.readAllBytes(new File(args[0]).toPath());
            PDFStreamParser parser = new PDFStreamParser(bytes);
            for (Object tok : parser.parse()) {
                emit(sb, tok);
            }
            out.print(sb);
            return;
        }
        int pageIndex = Integer.parseInt(args[1]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(pageIndex);
            PDFStreamParser parser = new PDFStreamParser(page);
            List<Object> tokens = parser.parse();
            for (Object tok : tokens) {
                emit(sb, tok);
            }
            out.print(sb);
        }
    }

    private static void emit(StringBuilder sb, Object tok) throws Exception {
        if (tok instanceof Operator) {
            Operator op = (Operator) tok;
            sb.append("OP:").append(op.getName()).append('\n');
            if (op.getImageData() != null) {
                byte[] data = op.getImageData();
                sb.append("IMGDATA:").append(data.length).append(':')
                        .append(sha1(data)).append('\n');
            }
        } else if (tok instanceof COSBase) {
            emitBase(sb, (COSBase) tok);
        } else {
            sb.append("UNKNOWN:").append(tok.getClass().getName()).append('\n');
        }
    }

    private static void emitBase(StringBuilder sb, COSBase b) throws Exception {
        if (b instanceof COSInteger) {
            sb.append("INT:").append(((COSInteger) b).longValue()).append('\n');
        } else if (b instanceof COSFloat) {
            sb.append("REAL:").append(canonFloat(((COSNumber) b).floatValue())).append('\n');
        } else if (b instanceof COSName) {
            sb.append("NAME:/").append(((COSName) b).getName()).append('\n');
        } else if (b instanceof COSString) {
            sb.append("STR:").append(hex(((COSString) b).getBytes())).append('\n');
        } else if (b instanceof COSBoolean) {
            sb.append("BOOL:").append(((COSBoolean) b).getValue() ? "true" : "false").append('\n');
        } else if (b instanceof COSNull) {
            sb.append("NULL").append('\n');
        } else if (b instanceof COSArray) {
            COSArray arr = (COSArray) b;
            sb.append("ARRAY:").append(arr.size()).append('\n');
            for (int i = 0; i < arr.size(); i++) {
                emitBase(sb, arr.get(i));
            }
        } else if (b instanceof COSDictionary) {
            COSDictionary d = (COSDictionary) b;
            sb.append("DICT:").append(d.size()).append('\n');
            for (COSName key : d.keySet()) {
                sb.append("NAME:/").append(key.getName()).append('\n');
                emitBase(sb, d.getDictionaryObject(key));
            }
        } else {
            sb.append("COS:").append(b.getClass().getSimpleName()).append('\n');
        }
    }

    /**
     * Locale-independent canonical float rendering. Round the float to a
     * fixed decimal precision then strip trailing zeros / trailing dot so
     * Java and Python agree regardless of shortest-round-trip differences.
     */
    static String canonFloat(float f) {
        if (Float.isNaN(f)) {
            return "nan";
        }
        if (Float.isInfinite(f)) {
            return f > 0 ? "inf" : "-inf";
        }
        java.math.BigDecimal bd = new java.math.BigDecimal(Float.toString(f))
                .setScale(5, java.math.RoundingMode.HALF_EVEN)
                .stripTrailingZeros();
        String s = bd.toPlainString();
        if (s.equals("-0")) {
            s = "0";
        }
        return s;
    }

    private static String hex(byte[] data) {
        StringBuilder s = new StringBuilder(data.length * 2);
        for (byte v : data) {
            s.append(Character.forDigit((v >> 4) & 0xF, 16));
            s.append(Character.forDigit(v & 0xF, 16));
        }
        return s.toString();
    }

    private static String sha1(byte[] data) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-1");
        return hex(md.digest(data));
    }
}
