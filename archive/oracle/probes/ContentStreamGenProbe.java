import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts.FontName;

/**
 * Live oracle probe for the BYTE-LEVEL content-stream tokens that the
 * high-level {@code PDPageContentStream} drawing API emits.
 *
 * It drives a fixed script of drawing calls — text show/positioning, path
 * construction + painting, the three colour-model setters, line width, and
 * rectangle — through upstream PDFBox 3.0.7, then prints the resulting page
 * content-stream bytes to stdout (raw, uncompressed). The paired pytest runs
 * the identical script through pypdfbox and asserts the bytes match
 * token-for-token, with particular attention to PDFBox's float formatter
 * (no trailing zeros, up to 5 fractional digits for PDPageContentStream,
 * '.' decimal separator, half-up rounding on the fractional part).
 *
 * Modes:
 *   java ContentStreamGenProbe draw    — emit the fixed drawing-script bytes
 *   java ContentStreamGenProbe numbers — emit one formatted operand per arg
 *                                        (drives writeOperand(float) only),
 *                                        each on its own line, so the float
 *                                        formatter can be pinned in isolation.
 */
public final class ContentStreamGenProbe {

    public static void main(String[] args) throws Exception {
        String mode = args.length > 0 ? args[0] : "draw";
        if ("draw".equals(mode)) {
            System.out.write(drawScript());
            System.out.flush();
        } else if ("numbers".equals(mode)) {
            PrintStream out = new PrintStream(System.out, true, "UTF-8");
            for (int i = 1; i < args.length; i++) {
                out.println(formatOne(Float.parseFloat(args[i])));
            }
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    /** Run the fixed drawing script and return the raw content-stream bytes. */
    private static byte[] drawScript() throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            PDType1Font font = new PDType1Font(FontName.HELVETICA);

            try (PDPageContentStream cs =
                    new PDPageContentStream(doc, page)) {
                // --- text block ---
                cs.beginText();
                cs.setFont(font, 12);
                cs.newLineAtOffset(72, 720);
                cs.showText("Hello World");
                cs.setLeading(14.5f);
                cs.newLine();
                cs.showText("Line (with parens) and \\ backslash");
                cs.endText();

                // --- path construction + painting ---
                cs.setLineWidth(0.75f);
                cs.moveTo(100, 100);
                cs.lineTo(200, 100.5f);
                cs.curveTo(210.25f, 110, 220, 120.333f, 230, 100);
                cs.stroke();

                // --- rectangle + fill ---
                cs.addRect(50, 50, 123.456f, 78.9f);
                cs.fill();

                // --- colour setters: gray / rgb / cmyk ---
                cs.setStrokingColor(0.5f);
                cs.setNonStrokingColor(0.1f, 0.2f, 0.3f);
                cs.setStrokingColor(0.11111f, 0.22222f, 0.33333f, 0.44444f);

                // --- a transform + save/restore ---
                cs.saveGraphicsState();
                cs.transform(new org.apache.pdfbox.util.Matrix(
                        1, 0, 0, 1, 12.5f, 0));
                cs.addRect(0, 0, 10, 10);
                cs.stroke();
                cs.restoreGraphicsState();
            }

            PDResources res = page.getResources();
            // Force /Resources to exist so the doc structure parallels pypdfbox,
            // but only the content bytes are compared.
            if (res == null) {
                page.setResources(new PDResources());
            }

            PDStream contents = page.getContentStreams().next();
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            try (var in = contents.createInputStream()) {
                in.transferTo(baos);
            }
            return baos.toByteArray();
        }
    }

    /**
     * Emit the formatter output for a single float exactly as
     * {@code writeOperand(float)} would, by writing it through a real
     * PDPageContentStream and capturing the bytes (then trimming the
     * trailing space the writer appends).
     */
    private static String formatOne(float value) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            try (PDPageContentStream cs =
                    new PDPageContentStream(doc, page)) {
                cs.setLineWidth(value);
            }
            PDStream contents = page.getContentStreams().next();
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            try (var in = contents.createInputStream()) {
                in.transferTo(baos);
            }
            String s = baos.toString("US-ASCII");
            // The stream is "<value> w\n"; strip the operator + whitespace.
            int wIdx = s.indexOf(" w");
            return s.substring(0, wIdx).trim();
        }
    }
}
