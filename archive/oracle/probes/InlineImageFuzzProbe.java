import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.List;
import org.apache.pdfbox.contentstream.operator.Operator;
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

/**
 * Live oracle probe (wave 1517): drive Apache PDFBox's {@code PDFStreamParser}
 * over a raw content-stream byte buffer and emit a COMBINED projection of how
 * the inline-image {@code BI ... ID <bytes> EI} sequence was tokenized — both
 * the parsed parameter dictionary (verbatim abbreviated keys) AND the raw
 * image-data length / digest extracted by the EI binary scan, for every
 * {@code BI} operator, in stream order.
 *
 * <p>This complements {@code InlineImageDictProbe} (dict only) and
 * {@code InlineEiScanProbe} (EI scan only) by exercising malformed/edge-case
 * inputs across BOTH facets at once: {@code ID} with no / multiple trailing
 * whitespace, missing {@code EI} entirely (truncated payload), filter
 * abbreviations (AHx/A85/LZW/Fl/RL/CCF/DCT), abbreviated key forms, a
 * non-{@code /Name} token where a key is expected, an empty parameter dict,
 * and post-EI operator-stream resynchronisation.
 *
 * <p>In PDFBox 3.0.x the parser absorbs the {@code ID}...{@code EI} segment
 * into the {@code BI} operator: there is no separate {@code ID} token, and the
 * {@code BI} operator carries BOTH {@code getImageParameters()} and the raw
 * {@code getImageData()}.
 *
 * <p>Output (UTF-8, to stdout), one block per {@code BI} operator in order:
 * <pre>
 *   BI keys=[K1=V1 ...] dlen=&lt;len&gt; dsha=&lt;sha1&gt; dhead=&lt;hex&gt; dtail=&lt;hex&gt;
 * </pre>
 * A trailing {@code OPS:<n>} line reports the total token count so a divergence
 * in post-EI resynchronisation is also caught. On any throw out of
 * {@code parse()} we emit {@code THROW} (exception class names differ across
 * the port, so only the throw-vs-not fact is compared).
 *
 * <p>Usage: {@code java -cp <pdfbox-app.jar>:<build> InlineImageFuzzProbe stream.cs}
 */
public final class InlineImageFuzzProbe {

    static String describe(COSBase v) {
        if (v == null) {
            return "null";
        }
        if (v instanceof COSName) {
            return "/" + ((COSName) v).getName();
        }
        if (v instanceof COSInteger) {
            return Long.toString(((COSInteger) v).longValue());
        }
        if (v instanceof COSFloat) {
            return v.toString();
        }
        if (v instanceof COSBoolean) {
            return ((COSBoolean) v).getValue() ? "true" : "false";
        }
        if (v instanceof COSNull) {
            return "null";
        }
        if (v instanceof COSString) {
            StringBuilder s = new StringBuilder("(");
            for (byte b : ((COSString) v).getBytes()) {
                s.append(Character.forDigit((b >> 4) & 0xF, 16));
                s.append(Character.forDigit(b & 0xF, 16));
            }
            return s.append(')').toString();
        }
        if (v instanceof COSArray) {
            StringBuilder s = new StringBuilder("[");
            COSArray arr = (COSArray) v;
            for (int i = 0; i < arr.size(); i++) {
                if (i > 0) {
                    s.append(' ');
                }
                s.append(describe(arr.get(i)));
            }
            return s.append(']').toString();
        }
        if (v instanceof COSDictionary) {
            StringBuilder s = new StringBuilder("<<");
            boolean first = true;
            for (COSName k : ((COSDictionary) v).keySet()) {
                if (!first) {
                    s.append(' ');
                }
                first = false;
                s.append('/').append(k.getName()).append('=');
                s.append(describe(((COSDictionary) v).getItem(k)));
            }
            return s.append(">>").toString();
        }
        return v.getClass().getSimpleName();
    }

    static String describeDict(COSDictionary d) {
        StringBuilder s = new StringBuilder("[");
        boolean first = true;
        for (COSName k : d.keySet()) {
            if (!first) {
                s.append(' ');
            }
            first = false;
            s.append(k.getName()).append('=').append(describe(d.getItem(k)));
        }
        return s.append(']').toString();
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] bytes = Files.readAllBytes(new File(args[0]).toPath());
        StringBuilder sb = new StringBuilder();
        try {
            PDFStreamParser parser = new PDFStreamParser(bytes);
            int count = 0;
            List<Object> tokens = parser.parse();
            for (Object tok : tokens) {
                count++;
                if (tok instanceof Operator) {
                    Operator op = (Operator) tok;
                    if ("BI".equals(op.getName())) {
                        COSDictionary params = op.getImageParameters();
                        byte[] data = op.getImageData();
                        sb.append("BI keys=")
                          .append(params == null ? "null" : describeDict(params))
                          .append(" dlen=")
                          .append(data == null ? -1 : data.length)
                          .append(" dsha=")
                          .append(data == null ? "-" : sha1(data))
                          .append(" dhead=")
                          .append(data == null ? "-" : head(data, 16))
                          .append(" dtail=")
                          .append(data == null ? "-" : tail(data, 16))
                          .append('\n');
                    }
                }
            }
            sb.append("OPS:").append(count).append('\n');
        } catch (Throwable t) {
            out.print("THROW\n");
            return;
        }
        out.print(sb);
    }

    private static String head(byte[] data, int n) {
        int end = Math.min(n, data.length);
        byte[] slice = new byte[end];
        System.arraycopy(data, 0, slice, 0, end);
        return hex(slice);
    }

    private static String tail(byte[] data, int n) {
        int start = Math.max(0, data.length - n);
        byte[] slice = new byte[data.length - start];
        System.arraycopy(data, start, slice, 0, slice.length);
        return hex(slice);
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
