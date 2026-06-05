import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.pdmodel.PDAppearanceContentStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;

/**
 * Live oracle probe pinning the SHARED {@code PDAbstractContentStream}
 * numeric-operand formatter (used by appearance / form / pattern content
 * streams) against the concrete {@code PDPageContentStream} formatter.
 *
 * The shared base constructor configures the formatter with
 * {@code setMaximumFractionDigits(4)} (PDFBox 3.0.7
 * {@code PDAbstractContentStream} line 112), whereas {@code PDPageContentStream}
 * bumps it to 5 via {@code setMaximumFractionDigits(5)}. Both route through
 * {@code NumberFormatUtil.formatFloatFast(float, maxFractionDigits, buffer)},
 * which narrows the operand to a 32-bit {@code float} and half-up-rounds the
 * narrowed fraction.
 *
 * Each argument is a float literal; one formatted operand is printed per line
 * (the trailing operator + whitespace from the {@code w} operator is trimmed),
 * so the formatter can be pinned byte-for-byte in isolation.
 *
 * Modes:
 *   java AbstractContentStreamFormatProbe abstract  v1 v2 ...  (4-digit base)
 *   java AbstractContentStreamFormatProbe page      v1 v2 ...  (5-digit page)
 */
public final class AbstractContentStreamFormatProbe {

    public static void main(String[] args) throws Exception {
        String mode = args.length > 0 ? args[0] : "abstract";
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        boolean page = "page".equals(mode);
        if (!page && !"abstract".equals(mode)) {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
        for (int i = 1; i < args.length; i++) {
            float v = Float.parseFloat(args[i]);
            out.println(page ? formatPage(v) : formatAbstract(v));
        }
    }

    /** writeOperand(float) via the 4-digit shared PDAbstractContentStream. */
    private static String formatAbstract(float value) throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        try (PDDocument doc = new PDDocument()) {
            PDAppearanceStream appearance = new PDAppearanceStream(doc);
            try (PDAppearanceContentStream cs =
                    new PDAppearanceContentStream(appearance, baos)) {
                cs.setLineWidth(value);
            }
        }
        return trimW(baos.toString("US-ASCII"));
    }

    /** writeOperand(float) via the 5-digit concrete PDPageContentStream. */
    private static String formatPage(float value) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.setLineWidth(value);
            }
            PDStream contents = page.getContentStreams().next();
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            try (var in = contents.createInputStream()) {
                in.transferTo(baos);
            }
            return trimW(baos.toString("US-ASCII"));
        }
    }

    /** The stream is "<value> w\n"; strip the operator + whitespace. */
    private static String trimW(String s) {
        int wIdx = s.indexOf(" w");
        return s.substring(0, wIdx).trim();
    }
}
