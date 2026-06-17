import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for the embedded /ToUnicode CMap -> Unicode path.
 *
 * Loads a PDF, picks the first font in the first page's resources, and for
 * each character code passed on the command line emits one canonical line:
 *
 *     UNI <code> -> U+XXXX[ U+YYYY...]
 *
 * where <code> is the decimal character code and the right-hand side is the
 * space-separated hex Unicode code points returned by font.toUnicode(code).
 * A code that maps to null/empty emits "UNI <code> -> (none)". Code points
 * are taken via String.codePoints() so a non-BMP destination (surrogate
 * pair in UTF-16) collapses to a single U+1XXXX entry — exactly how Python
 * iterates its string. After the per-code lines, a final block:
 *
 *     ===TEXT===
 *     <PDFTextStripper output>
 *
 * lets the caller diff extracted text for the shown string too.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ToUnicodeCMapProbe input.pdf code [code ...]
 * Codes are decimal integers.
 */
public final class ToUnicodeCMapProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFont font = firstFont(doc);
            if (font != null) {
                for (int i = 1; i < args.length; i++) {
                    int code = Integer.parseInt(args[i]);
                    emitCode(out, font, code);
                }
            }
            out.println("===TEXT===");
            out.print(new PDFTextStripper().getText(doc));
        }
    }

    private static PDFont firstFont(PDDocument doc) throws Exception {
        for (PDPage page : doc.getPages()) {
            PDResources res = page.getResources();
            if (res == null) {
                continue;
            }
            for (COSName fontName : res.getFontNames()) {
                PDFont font = res.getFont(fontName);
                if (font != null) {
                    return font;
                }
            }
        }
        return null;
    }

    private static void emitCode(PrintStream out, PDFont font, int code) {
        String uni;
        try {
            uni = font.toUnicode(code);
        } catch (Exception e) {
            uni = null;
        }
        if (uni == null || uni.isEmpty()) {
            out.println("UNI " + code + " -> (none)");
            return;
        }
        StringBuilder sb = new StringBuilder();
        sb.append("UNI ").append(code).append(" ->");
        uni.codePoints().forEach(cp -> sb.append(" U+").append(String.format("%04X", cp)));
        out.println(sb.toString());
    }
}
