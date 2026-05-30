import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
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
 * Live oracle probe: drive Apache PDFBox's {@code PDFStreamParser} over a raw
 * content-stream byte buffer and emit the PARSED INLINE-IMAGE PARAMETER
 * DICTIONARY for every {@code BI} operator, in keySet (insertion) order, plus
 * the raw image-data byte length carried on the {@code ID} operator.
 *
 * <p>This isolates the inline-image dict-parsing facet (PDF 32000-1 §8.9.7):
 * the parser collects the {@code /Key value} pairs between {@code BI} and
 * {@code ID} into {@code Operator.getImageParameters()} using the verbatim
 * (abbreviated) key names — {@code /W /H /CS /BPC /F /IM /D /DP /I} — without
 * expanding them to long form. A wrong key, dropped pair, mis-typed value, or
 * a key-order divergence shows up here even when the EI scan length matches.
 *
 * <p>Usage: {@code java -cp <pdfbox-app.jar>:<build> InlineImageDictProbe stream.cs}
 *
 * <p>In PDFBox 3.0.x the parser absorbs the {@code ID}...{@code EI} segment
 * into the {@code BI} operator: there is no separate {@code ID} token, and the
 * {@code BI} operator carries BOTH {@code getImageParameters()} and the raw
 * {@code getImageData()}. We therefore report the dict and the raw data length
 * together on the {@code BI} line.
 *
 * <p>Output (UTF-8, to stdout), one block per {@code BI} operator in order:
 * <pre>
 *   BI keys=[K1=V1 K2=V2 ...] data=&lt;rawImageDataLength&gt;
 * </pre>
 * A trailing {@code OPS:<n>} line reports the total token count so a divergence
 * in post-EI resynchronisation is also caught. Each {@code Vi} is a canonical
 * rendering: names as {@code /Name}, ints verbatim, reals via PDFBox's own
 * {@code COSFloat.toString}, booleans {@code true}/{@code false}, strings
 * {@code (...)}-quoted as raw lower-hex, arrays {@code [..]}, dicts {@code <<..>>}.
 */
public final class InlineImageDictProbe {

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
        PDFStreamParser parser = new PDFStreamParser(bytes);
        StringBuilder sb = new StringBuilder();
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
                      .append(" data=")
                      .append(data == null ? -1 : data.length)
                      .append('\n');
                }
            }
        }
        sb.append("OPS:").append(count).append('\n');
        out.print(sb);
    }
}
