import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;

/**
 * Live oracle probe: pin the EXACT raw bytes Apache PDFBox's
 * PDPageContentStream writes for a fixed operator sequence — BEFORE any
 * save round-trip canonicalises them. Unlike ContentGenProbe (which saves
 * the PDF and re-tokenizes, losing the precise float formatting and string
 * serialization), this probe reads the freshly-written, uncompressed
 * content-stream body straight out of the page's COSStream and emits its
 * literal bytes as lower-hex.
 *
 * What this pins that the token-level oracle cannot:
 *   - formatDecimal output (e.g. "2.5" vs "2.50000", integral floats as
 *     bare ints, HALF_UP rounding at the 4th fraction digit);
 *   - operand spacing (one trailing space per operand) and the single LF
 *     after every operator;
 *   - showText() string serialization — PDFBox routes the font-encoded
 *     bytes through COSWriter.writeString(byte[]), producing a LITERAL
 *     "(...)" string with backslash-escaped ( ) \\ and the three special
 *     EOL/﻿control escapes, NOT a hex "<...>" string;
 *   - dash-array "[a b] phase d" framing.
 *
 * The probe takes one selector arg so the test can request individual
 * surfaces independently (keeps a divergence localised):
 *   numbers | colors | path | text | dash | transform | full
 *
 * Output (UTF-8, one line): the lower-hex of every content-stream byte.
 */
public final class ContentRawBytesProbe {
    public static void main(String[] args) throws Exception {
        String which = args.length > 0 ? args[0] : "full";
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(new PDRectangle(0, 0, 300, 400));
            doc.addPage(page);
            PDType1Font font =
                    new PDType1Font(Standard14Fonts.FontName.HELVETICA);
            // compress=false so the COSStream body is the literal operator
            // bytes the writer produced.
            try (PDPageContentStream cs = new PDPageContentStream(
                    doc, page, PDPageContentStream.AppendMode.OVERWRITE,
                    false, false)) {
                draw(cs, font, which);
            }
            out.print(hex(rawBody(page)));
        }
    }

    private static byte[] rawBody(PDPage page) throws Exception {
        PDStream stream = null;
        // page.getContentStreams() iterates the /Contents streams; the
        // single OVERWRITE stream we just wrote is the only one.
        java.util.Iterator<PDStream> it = page.getContentStreams();
        while (it.hasNext()) {
            stream = it.next();
        }
        COSStream cos = stream.getCOSObject();
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        // createRawInputStream() returns the unfiltered (uncompressed,
        // since compress=false) body bytes exactly as written.
        try (InputStream in = cos.createRawInputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) != -1) {
                bos.write(buf, 0, n);
            }
        }
        return bos.toByteArray();
    }

    private static void draw(PDPageContentStream cs, PDType1Font font,
            String which) throws Exception {
        switch (which) {
            case "numbers":
                // Number-formatting surface: integral floats, 4-decimal
                // truncation, HALF_UP rounding at the boundary, negatives.
                cs.setLineWidth(2.5f);
                cs.setLineWidth(1.0f);          // integral float -> "1"
                cs.setLineWidth(0.123456f);     // -> "0.1235" (HALF_UP)
                cs.setLineWidth(0.00001f);      // -> "0" (below 4 digits)
                cs.setLineWidth(100.0f);        // -> "100"
                cs.setLineWidth(0.5f);
                cs.moveTo(-1.25f, 12.75f);      // negatives
                cs.lineTo(0.0f, 3.14159f);      // -> "3.1416"
                break;
            case "colors":
                cs.setStrokingColor(1.0f, 0.0f, 0.0f);            // RG
                cs.setNonStrokingColor(0.0f, 1.0f, 0.0f);         // rg
                cs.setStrokingColor(0.25f);                       // G
                cs.setNonStrokingColor(0.75f);                    // g
                cs.setStrokingColor(0.1f, 0.2f, 0.3f, 0.4f);      // K
                cs.setNonStrokingColor(0.5f, 0.6f, 0.7f, 0.8f);   // k
                break;
            case "path":
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
                break;
            case "text":
                cs.beginText();
                cs.setFont(font, 12f);
                cs.setLeading(14f);
                cs.newLineAtOffset(15, 200);
                cs.showText("Hello");
                cs.newLine();
                cs.showText("World");
                cs.newLine();
                // String-escaping stress: balanced parens + backslash.
                cs.showText("paren (a) and \\backslash");
                cs.endText();
                break;
            case "dash":
                cs.setLineDashPattern(new float[] {3, 2}, 1);
                cs.setLineDashPattern(new float[] {}, 0);
                cs.setLineDashPattern(new float[] {1.5f}, 0.5f);
                cs.setLineCapStyle(1);
                cs.setLineJoinStyle(2);
                cs.setMiterLimit(4.0f);
                break;
            case "transform":
                cs.saveGraphicsState();
                cs.transform(
                        org.apache.pdfbox.util.Matrix.getTranslateInstance(
                                10, 20));
                cs.transform(new org.apache.pdfbox.util.Matrix(
                        2, 0, 0, 2, 5.5f, 7.25f));
                cs.restoreGraphicsState();
                break;
            default:
                throw new IllegalArgumentException("unknown selector: " + which);
        }
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
