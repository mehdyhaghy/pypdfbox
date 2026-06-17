import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;

/**
 * Live oracle probe: emit Apache PDFBox's per-font code -> Unicode mapping.
 *
 * For each page, for each font in the page's resources, walk character codes
 * 0..0xFFFF and emit one canonical line per code that maps to a Unicode string:
 *
 *     <page> <fontName> <code> -> U+XXXX[ U+YYYY...]
 *
 * where <page> is the 0-based page index, <fontName> the resource font name
 * (COSName, without the leading slash), <code> the decimal character code, and
 * the right-hand side the space-separated hex Unicode code points of the string
 * PDFBox's font.toUnicode(code) returns. Codes with no mapping (null) are
 * skipped. Output is UTF-8, stable line order (page, then resource iteration
 * order, then ascending code).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ToUniMapProbe input.pdf [maxCode]
 */
public final class ToUniMapProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int maxCode = args.length > 1 ? Integer.parseInt(args[1]) : 0xFFFF;
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res != null) {
                    for (COSName fontName : res.getFontNames()) {
                        PDFont font;
                        try {
                            font = res.getFont(fontName);
                        } catch (Exception e) {
                            // Unloadable font — skip; pypdfbox side skips too.
                            continue;
                        }
                        if (font == null) {
                            continue;
                        }
                        emitFont(out, pageIndex, fontName.getName(), font, maxCode);
                    }
                }
                pageIndex++;
            }
        }
    }

    private static void emitFont(
            PrintStream out, int page, String name, PDFont font, int maxCode) {
        for (int code = 0; code <= maxCode; code++) {
            String uni;
            try {
                uni = font.toUnicode(code);
            } catch (Exception e) {
                // toUnicode can throw on malformed embedded data; treat as no
                // mapping so both sides agree on "skip".
                continue;
            }
            if (uni == null || uni.isEmpty()) {
                continue;
            }
            StringBuilder sb = new StringBuilder();
            sb.append(page).append(' ').append(name).append(' ')
              .append(code).append(" ->");
            uni.codePoints().forEach(cp -> sb.append(" U+")
                    .append(String.format("%04X", cp)));
            out.println(sb.toString());
        }
    }
}
