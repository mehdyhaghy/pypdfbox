import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
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

/**
 * Live oracle probe for content-stream tokenizer edge cases that are easy to
 * get subtly wrong: <code>%</code>-comment skipping and the
 * <code>BX</code>/<code>EX</code> compatibility operators wrapping unknown
 * operators.
 *
 * <p>The probe carries a fixed bank of raw content streams (selected by name
 * on the command line) so the Python side can compare against the identical
 * input bytes without shipping a binary fixture. Each case is tokenized with
 * Apache PDFBox's {@link PDFStreamParser#parse()} and emitted as one canonical
 * token per line, matching the grammar used by {@code TokenizeProbe}:
 *
 * <pre>
 *   OP:&lt;name&gt;       operator keyword
 *   INT:&lt;n&gt;          COSInteger
 *   REAL:&lt;canon&gt;      COSFloat (canonical, locale-independent)
 *   NAME:/&lt;n&gt;        COSName
 *   STR:&lt;hexbytes&gt;    COSString (raw bytes, lower-hex)
 *   BOOL:true|false   COSBoolean
 *   NULL              COSNull
 *   ARRAY:&lt;n&gt;        COSArray header, then n element tokens
 *   DICT:&lt;n&gt;         COSDictionary header, then n key/value token pairs
 * </pre>
 *
 * Usage: {@code java -cp ... CommentCompatTokenizeProbe <caseName>}
 */
public final class CommentCompatTokenizeProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] bytes = caseBytes(args[0]);
        PDFStreamParser parser = new PDFStreamParser(bytes);
        StringBuilder sb = new StringBuilder();
        for (Object tok : parser.parse()) {
            emit(sb, tok);
        }
        out.print(sb);
    }

    /**
     * Fixed bank of content streams. Kept in lock-step with the Python
     * test's CASES dict (same bytes, same case keys) so a divergence can only
     * come from the tokenizer, never from differing input.
     */
    static byte[] caseBytes(String name) {
        String cs;
        switch (name) {
            case "leading_comment":
                // Comment as the very first token of the stream.
                cs = "% a leading comment\nq\n1 0 0 1 0 0 cm\nQ\n";
                break;
            case "trailing_comment":
                // Comment as the final bytes, no trailing EOL.
                cs = "q\nQ\n% trailing comment with no newline";
                break;
            case "inline_comment":
                // Comment between operands and after an operator on a line.
                cs = "10 % comment mid-operand-run\n20 m % after operator\n";
                break;
            case "comment_crlf":
                // CRLF-terminated comment lines.
                cs = "% first\r\nq\r\n% second\r\nQ\r\n";
                break;
            case "comment_cr_only":
                // Bare-CR-terminated comment line.
                cs = "% bare cr\rq\rQ\r";
                break;
            case "comment_no_space":
                // No space after the % marker, percent inside a comment.
                cs = "%100%off\nq\nQ\n";
                break;
            case "empty_comment":
                // Empty comment lines back-to-back.
                cs = "%\n%\nq\nQ\n";
                break;
            case "bx_ex_unknown":
                // Classic compatibility block wrapping an unknown operator.
                cs = "q\nBX\n/Foo 5 fooUnknownOp\n2.5 3 anotherUnknownOp\nEX\nQ\n";
                break;
            case "bx_ex_empty":
                // Empty compatibility section.
                cs = "BX\nEX\n";
                break;
            case "bx_ex_nested":
                // Nested BX/EX (allowed; both are just operators).
                cs = "BX\nBX\nweirdOp\nEX\nEX\n";
                break;
            case "unknown_op_bare":
                // Unknown operator outside any BX/EX block.
                cs = "1 2 totallyMadeUpOperator\n";
                break;
            case "bx_ex_comment_mix":
                // BX/EX section with comments and an unknown op interleaved.
                cs = "BX % begin compat\n"
                        + "/X 1 unknownA % an unknown op\n"
                        + "% standalone comment\n"
                        + "true unknownB\n"
                        + "EX % end compat\n";
                break;
            default:
                throw new IllegalArgumentException("unknown case: " + name);
        }
        return cs.getBytes(StandardCharsets.US_ASCII);
    }

    private static void emit(StringBuilder sb, Object tok) {
        if (tok instanceof Operator) {
            Operator op = (Operator) tok;
            sb.append("OP:").append(op.getName()).append('\n');
        } else if (tok instanceof COSBase) {
            emitBase(sb, (COSBase) tok);
        } else {
            sb.append("UNKNOWN:").append(tok.getClass().getName()).append('\n');
        }
    }

    private static void emitBase(StringBuilder sb, COSBase b) {
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
     * Locale-independent canonical float rendering — identical to
     * {@code TokenizeProbe.canonFloat}: round the float32's shortest decimal
     * to 5 places (half-even), strip trailing zeros, normalize {@code -0}.
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
}
