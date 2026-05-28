import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.PrintStream;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.CFFParser;
import org.apache.fontbox.cff.CFFType1Font;
import org.apache.fontbox.cff.CFFEncoding;

/**
 * Live oracle probe for fontbox CFFType1Font encoding resolution — the
 * **Top DICT /Encoding** path. Covers three on-disk cases:
 *
 *  - Predefined StandardEncoding   (Top DICT /Encoding operand = 0).
 *  - Predefined ExpertEncoding     (Top DICT /Encoding operand = 1).
 *  - Embedded Format0 / Format1    (Top DICT /Encoding operand is an
 *                                   offset into the CFF program).
 *
 * The CffSubsetProbe sibling covers /FontFile3 subset *structure* (glyph
 * count + /W widths) and never emits encoding facts; the
 * CffCidFdProbe sibling covers CID-keyed /FDSelect + /FDArray and never
 * touches name-keyed encodings — so this probe owns the encoding-class
 * + per-code-name surface with no collision.
 *
 * <pre>
 *   java -cp ... CffEncodingProbe &lt;input.cff&gt;
 * </pre>
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic order):
 *
 *   FONT \t baseFontClass
 *       Simple class name returned by ``CFFFont.getClass()`` (e.g.
 *       ``CFFType1Font`` for name-keyed Type1C).
 *
 *   ENC \t encodingClass
 *       Simple class name returned by
 *       ``CFFType1Font.getEncoding().getClass()`` — exactly one of
 *       ``CFFStandardEncoding`` / ``CFFExpertEncoding`` /
 *       ``Format0Encoding`` / ``Format1Encoding``. This is the
 *       load-bearing line: the predefined-vs-embedded distinction
 *       lives here.
 *
 *   ENC_FULL \t fullyQualifiedEncodingClass
 *       Java FQN for the encoding class (e.g.
 *       ``org.apache.fontbox.cff.CFFStandardEncoding`` for predefined,
 *       ``org.apache.fontbox.cff.CFFParser$Format0Encoding`` for
 *       embedded). pypdfbox compares the *trailing simple name* only,
 *       so the FQN is informational.
 *
 *   MAP \t code \t glyphName
 *       Per-code mapping from the encoding's ``getName(int)`` for every
 *       code 0..255 whose glyph is not ``.notdef``. Codes that resolve
 *       to ``.notdef`` are omitted to keep the diff small.
 *
 * Never mutates the input file; closes the input stream via
 * try-with-resources.
 */
public final class CffEncodingProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 1) {
            out.println("usage: CffEncodingProbe <input.cff>");
            return;
        }
        read(out, args[0]);
    }

    private static void read(PrintStream out, String path) throws Exception {
        byte[] data;
        try (FileInputStream fis = new FileInputStream(new File(path))) {
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = fis.read(buf)) > 0) {
                bos.write(buf, 0, n);
            }
            data = bos.toByteArray();
        }
        final byte[] payload = data;
        CFFFont font = new CFFParser().parse(payload,
                new CFFParser.ByteSource() {
                    @Override
                    public byte[] getBytes() {
                        return payload;
                    }
                }).get(0);
        out.printf("FONT\t%s%n", font.getClass().getSimpleName());
        if (!(font instanceof CFFType1Font)) {
            out.printf("ENC\tNONE%n");
            out.printf("ENC_FULL\tNONE%n");
            return;
        }
        CFFEncoding enc = ((CFFType1Font) font).getEncoding();
        if (enc == null) {
            out.printf("ENC\tNULL%n");
            out.printf("ENC_FULL\tNULL%n");
            return;
        }
        out.printf("ENC\t%s%n", enc.getClass().getSimpleName());
        out.printf("ENC_FULL\t%s%n", enc.getClass().getName());
        for (int code = 0; code <= 255; code++) {
            String name = enc.getName(code);
            if (name == null || ".notdef".equals(name)) {
                continue;
            }
            out.printf("MAP\t%d\t%s%n", code, name);
        }
    }
}
