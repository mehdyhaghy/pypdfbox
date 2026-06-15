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
 * Live oracle probe: PDFStreamParser token-SEQUENCE assembly fuzz (wave 1528).
 *
 * Unlike TokenizeProbe (which parses one page) or the single-token escape
 * probes, this drives parseNextToken() in a loop over malformed CONTENT-STREAM
 * bytes and projects the WHOLE token sequence: operator names, operand
 * type/value, inline-image BI/ID/EI markers (with image-data length + sha1).
 * The angle is how PDFStreamParser accumulates operands and emits Operator
 * objects under malformed input (dangling operands, missing operators,
 * unbalanced arrays/dicts, truncated inline images, embedded EI, garbage
 * bytes, stray close tokens).
 *
 * Per-token projection (one line each):
 *   OP:<name>
 *   IMG:<len>:<sha1>     inline-image bytes carried by the ID operator
 *   INT:<n>
 *   REAL:<canon>
 *   NAME:/<n>
 *   STR:<lowerhex>
 *   BOOL:true|false
 *   NULL
 *   ARRAY:<n> then n element tokens
 *   DICT:<n> then n key/value token pairs
 *   COS:<simpleName>     any other COSBase
 *
 * Per case:
 *   CASE <name>
 *   <token lines...>
 *   END <name> ok           parseNextToken returned null cleanly (EOF)
 * or
 *   CASE <name>
 *   <token lines emitted before the throw...>
 *   END <name> err          a parseNextToken() call threw
 *
 * The exception CLASS differs Java/Python, so only the ok-vs-err fact is
 * compared, plus the prefix of tokens emitted before the throw.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> StreamParserFuzzProbe
 */
public final class StreamParserFuzzProbe {

    public static void main(String[] args) throws Exception {
        java.io.PrintStream out = new java.io.PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        run(sb, "empty", b(""));
        run(sb, "only_ws", b("   \r\n\t "));
        run(sb, "op_no_operands", b("Q"));
        run(sb, "two_bare_ops", b("q Q"));
        run(sb, "dangling_operands_eof", b("1 2 3"));
        run(sb, "operands_then_op", b("1 0 0 1 0 0 cm"));
        run(sb, "trailing_operand_no_op", b("BT /F1 12 Tf 1 2"));
        run(sb, "unbalanced_array_open", b("[1 2 3"));
        run(sb, "balanced_array", b("[1 2 3] 4 d0"));
        run(sb, "nested_array", b("[[1 2][3 4]] op"));
        run(sb, "unbalanced_dict_open", b("<< /A 1 /B 2"));
        run(sb, "balanced_dict_operand", b("<< /A 1 >> op"));
        run(sb, "nested_dict_array", b("[<< /A [1 2] >> 3] op"));
        run(sb, "stray_close_bracket", b("] 1 2 op"));
        run(sb, "stray_close_dict", b(">> 1 op"));
        run(sb, "comment_midstream", b("1 % comment here\n2 op"));
        run(sb, "comment_no_eol", b("1 2 % trailing comment"));
        run(sb, "garbage_between", b("1 @ 2 # op"));
        run(sb, "name_operand", b("/Name1 /Name2#41 op"));
        run(sb, "malformed_name_hash", b("/Bad#G op"));
        run(sb, "double_negative", b("--5 op"));
        run(sb, "mid_dash", b("5-3 op"));
        run(sb, "lone_plus", b("+ op"));
        run(sb, "lone_dot", b(". op"));
        run(sb, "lone_dash", b("- op"));
        run(sb, "real_numbers", b("1.5 -2.25 .5 3. op"));
        run(sb, "string_operand", b("(hello) Tj"));
        run(sb, "hex_string_operand", b("<48656c6c6f> Tj"));
        run(sb, "bool_null_operands", b("true false null op"));
        run(sb, "apostrophe_op", b("(line) '"));
        run(sb, "quote_op", b("0 0 (line) \""));
        run(sb, "star_op", b("W* n f* B*"));
        run(sb, "d0_d1_op", b("0 0 d0 1 1 0 0 0 0 d1"));
        run(sb, "long_operand_run", longRun());
        run(sb, "bi_id_ei_basic",
                cat(b("BI /W 2 /H 2 /BPC 8 /CS /G ID "), bytes(0x00, 0x11, 0x22, 0x33), b(" EI Q")));
        run(sb, "bi_no_ei",
                cat(b("BI /W 2 /H 2 ID "), bytes(0xAA, 0xBB, 0xCC, 0xDD, 0xEE)));
        run(sb, "bi_embedded_ei",
                cat(b("BI /W 8 /H 1 ID "), bytes(0x00, 'E', 'I', 0x00, 0x99), b(" EI Q")));
        run(sb, "bi_truncated_after_id", b("BI /W 2 /H 2 ID"));
        run(sb, "bi_no_dict", cat(b("BI ID "), bytes(0x01, 0x02), b(" EI")));
        run(sb, "bi_nested", b("BI /W 1 ID x EI BI /W 1 ID y EI"));
        run(sb, "id_no_bi", cat(b("ID "), bytes(0x01, 0x02), b(" EI Q")));
        run(sb, "ei_alone", b("EI Q"));
        run(sb, "bi_malformed_dict_value", b("BI /W /H ID xy EI"));
        out.print(sb);
    }

    private static void run(StringBuilder sb, String name, byte[] data) {
        sb.append("CASE ").append(name).append('\n');
        PDFStreamParser parser = new PDFStreamParser(data);
        boolean err = false;
        try {
            while (true) {
                Object tok = parser.parseNextToken();
                if (tok == null) {
                    break;
                }
                emit(sb, tok);
            }
        } catch (Throwable t) {
            err = true;
        } finally {
            try {
                parser.close();
            } catch (Exception ignored) {
                // best-effort close
            }
        }
        sb.append("END ").append(name).append(err ? " err" : " ok").append('\n');
    }

    private static void emit(StringBuilder sb, Object tok) {
        if (tok instanceof Operator) {
            Operator op = (Operator) tok;
            sb.append("OP:").append(op.getName()).append('\n');
            if (op.getImageData() != null) {
                byte[] d = op.getImageData();
                sb.append("IMG:").append(d.length).append(':').append(sha1(d)).append('\n');
            }
        } else if (tok instanceof COSBase) {
            emitBase(sb, (COSBase) tok);
        } else {
            sb.append("UNK:").append(tok.getClass().getSimpleName()).append('\n');
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

    private static byte[] b(String s) {
        try {
            return s.getBytes("ISO-8859-1");
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    private static byte[] bytes(int... vals) {
        byte[] out = new byte[vals.length];
        for (int i = 0; i < vals.length; i++) {
            out[i] = (byte) vals[i];
        }
        return out;
    }

    private static byte[] cat(byte[]... parts) {
        int len = 0;
        for (byte[] p : parts) {
            len += p.length;
        }
        byte[] out = new byte[len];
        int pos = 0;
        for (byte[] p : parts) {
            System.arraycopy(p, 0, out, pos, p.length);
            pos += p.length;
        }
        return out;
    }

    private static byte[] longRun() {
        StringBuilder s = new StringBuilder();
        for (int i = 0; i < 200; i++) {
            s.append(i).append(' ');
        }
        s.append("op");
        return b(s.toString());
    }

    private static String hex(byte[] data) {
        StringBuilder s = new StringBuilder(data.length * 2);
        for (byte v : data) {
            s.append(Character.forDigit((v >> 4) & 0xF, 16));
            s.append(Character.forDigit(v & 0xF, 16));
        }
        return s.toString();
    }

    private static String sha1(byte[] data) {
        try {
            java.security.MessageDigest md = java.security.MessageDigest.getInstance("SHA-1");
            return hex(md.digest(data));
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
