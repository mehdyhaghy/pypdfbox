import java.io.File;
import java.io.PrintStream;
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
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;

/**
 * Live oracle probe: generate a one-page PDF with a FIXED sequence of
 * PDPageContentStream drawing calls, save it to args[0], then re-parse the
 * page's content stream with PDFStreamParser and emit a canonical token
 * stream to stdout (same grammar as TokenizeProbe).
 *
 * The test reproduces the identical drawing sequence with pypdfbox's
 * PDPageContentStream, tokenises its bytes the same way, and asserts the
 * operator/operand token streams match.
 *
 * Usage:
 *   java -cp ... ContentGenProbe out.pdf
 *
 * Canonical token grammar (one per line, UTF-8) — same as TokenizeProbe:
 *   OP:<name>   INT:<n>   REAL:<canon>   NAME:/<n>   STR:<hexbytes>
 *   BOOL:..     NULL      ARRAY:<n>      DICT:<n>
 */
public final class ContentGenProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File outFile = new File(args[0]);
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(new PDRectangle(0, 0, 300, 400));
            doc.addPage(page);
            PDType1Font font =
                    new PDType1Font(Standard14Fonts.FontName.HELVETICA);
            try (PDPageContentStream cs =
                    new PDPageContentStream(doc, page)) {
                drawFixedSequence(cs, font);
            }
            doc.save(outFile);
        }
        // Re-parse the saved page and tokenize.
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(outFile)) {
            PDPage page = doc.getPage(0);
            PDFStreamParser parser = new PDFStreamParser(page);
            List<Object> tokens = parser.parse();
            for (Object tok : tokens) {
                emit(sb, tok);
            }
        }
        out.print(sb);
    }

    /**
     * The fixed drawing sequence under test. MUST be kept byte-for-byte in
     * sync with the Python reproduction in the differential test.
     */
    static void drawFixedSequence(PDPageContentStream cs, PDType1Font font)
            throws Exception {
        // --- graphics state save + transform ---
        cs.saveGraphicsState();
        cs.transform(org.apache.pdfbox.util.Matrix.getTranslateInstance(10, 20));

        // --- line state ---
        cs.setLineWidth(2.5f);
        cs.setLineCapStyle(1);
        cs.setLineJoinStyle(2);
        cs.setMiterLimit(4.0f);
        cs.setLineDashPattern(new float[] {3, 2}, 1);

        // --- colors (every device space, stroking + non-stroking) ---
        cs.setStrokingColor(1.0f, 0.0f, 0.0f);            // RG
        cs.setNonStrokingColor(0.0f, 1.0f, 0.0f);         // rg
        cs.setStrokingColor(0.25f);                       // G  (gray)
        cs.setNonStrokingColor(0.75f);                    // g
        cs.setStrokingColor(0.1f, 0.2f, 0.3f, 0.4f);      // K  (cmyk)
        cs.setNonStrokingColor(0.5f, 0.6f, 0.7f, 0.8f);   // k

        // --- path construction + painting ---
        cs.moveTo(0, 0);
        cs.lineTo(50, 0);
        cs.curveTo(60, 10, 70, 20, 80, 30);
        cs.addRect(5, 5, 20, 20);
        cs.closePath();
        cs.fillAndStroke();

        cs.moveTo(100, 100);
        cs.lineTo(150, 150);
        cs.stroke();

        cs.addRect(200, 200, 30, 40);
        cs.fill();

        // --- text block ---
        cs.beginText();
        cs.setFont(font, 12f);
        cs.setLeading(14f);
        cs.newLineAtOffset(15, 200);
        cs.showText("Hello");
        cs.newLine();
        cs.showText("World");
        cs.endText();

        // --- restore ---
        cs.restoreGraphicsState();
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
     * TokenizeProbe.canonFloat: round to 5 decimals HALF_EVEN, strip
     * trailing zeros / dot.
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
