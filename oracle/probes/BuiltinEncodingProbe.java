import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDSimpleFont;
import org.apache.pdfbox.pdmodel.font.encoding.Encoding;
import org.apache.pdfbox.rendering.PDFRenderer;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for the embedded-simple-font-without-/Encoding render bug
 * (DEFERRED.md pdmodel/font). For the first {@link PDSimpleFont} on page 0 it
 * emits, all to stdout (UTF-8):
 *
 *   FONT\t<baseFont>\t<subType>\t<embedded>\t<hasEncodingDict>
 *     <hasEncodingDict> = "true" when the PDF font dict carries an /Encoding
 *     entry, "false" otherwise — confirms the no-/Encoding case under test.
 *   ENC\t<encClass>
 *     simple class name of font.getEncoding() (the resolved Encoding), or
 *     "null".
 *   CODE\t<code>\t<glyphName>\t<width>      for codes 0..255
 *     <glyphName> = font.getEncoding().getName(code) (".notdef" when the font
 *     has no resolved Encoding); <width> = font.getWidth(code) rendered with
 *     canonNumber.
 *
 * Then the document-level lines:
 *   TEXT\t<line>                            PDFTextStripper output, one line
 *                                           per source line (\n stripped),
 *                                           with a literal "␀" placeholder
 *                                           swapped for empty lines so the line
 *                                           shape stays diffable.
 *   DIM\t<width>\t<height>                  rendered page-0 pixel size @72 DPI
 *   GRID\t<256 space-separated luminances>  16x16 luminance fingerprint,
 *                                           row-major (same recipe as
 *                                           RenderProbe — lets the test assert
 *                                           the glyphs are no longer blank).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> BuiltinEncodingProbe input.pdf
 */
public final class BuiltinEncodingProbe {
    private static final int GRID = 16;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(0);
            PDResources res = page.getResources();
            PDSimpleFont simple = null;
            COSName fontName = null;
            if (res != null) {
                for (COSName name : res.getFontNames()) {
                    PDFont font = res.getFont(name);
                    if (font instanceof PDSimpleFont) {
                        simple = (PDSimpleFont) font;
                        fontName = name;
                        break;
                    }
                }
            }
            if (simple == null) {
                out.println("FONT\tNONE");
            } else {
                boolean embedded = simple.isEmbedded();
                boolean hasEncDict =
                        simple.getCOSObject().getDictionaryObject(COSName.ENCODING) != null;
                out.printf("FONT\t%s\t%s\t%s\t%s%n",
                        simple.getName(), simple.getSubType(), embedded, hasEncDict);

                Encoding enc = simple.getEncoding();
                out.printf("ENC\t%s%n", enc == null ? "null" : enc.getClass().getSimpleName());

                for (int code = 0; code <= 255; code++) {
                    String glyph = enc == null ? ".notdef" : enc.getName(code);
                    float width = simple.getWidth(code);
                    out.printf("CODE\t%d\t%s\t%s%n", code, glyph, canonNumber(width));
                }
            }

            // Document-level text.
            String text = new PDFTextStripper().getText(doc);
            for (String line : text.split("\n", -1)) {
                String stripped = line.replace("\r", "");
                if (stripped.isEmpty()) {
                    out.println("TEXT\t␀");
                } else {
                    out.printf("TEXT\t%s%n", stripped);
                }
            }

            // Render fingerprint (page 0).
            PDFRenderer renderer = new PDFRenderer(doc);
            BufferedImage img = renderer.renderImageWithDPI(0, 72.0f);
            int w = img.getWidth();
            int h = img.getHeight();
            out.printf("DIM\t%d\t%d%n", w, h);

            long[] sum = new long[GRID * GRID];
            long[] cnt = new long[GRID * GRID];
            for (int y = 0; y < h; y++) {
                int cy = (int) ((long) y * GRID / h);
                if (cy >= GRID) {
                    cy = GRID - 1;
                }
                for (int x = 0; x < w; x++) {
                    int cx = (int) ((long) x * GRID / w);
                    if (cx >= GRID) {
                        cx = GRID - 1;
                    }
                    int rgb = img.getRGB(x, y);
                    int r = (rgb >> 16) & 0xFF;
                    int g = (rgb >> 8) & 0xFF;
                    int b = rgb & 0xFF;
                    int lum = (int) Math.round(0.299 * r + 0.587 * g + 0.114 * b);
                    int idx = cy * GRID + cx;
                    sum[idx] += lum;
                    cnt[idx] += 1;
                }
            }
            StringBuilder sb = new StringBuilder("GRID");
            for (int i = 0; i < GRID * GRID; i++) {
                long avg = cnt[i] > 0 ? Math.round((double) sum[i] / cnt[i]) : 255;
                sb.append('\t').append(avg);
            }
            out.println(sb.toString());
        }
    }

    /** Mirror the canonical number rendering used by other probes/tests. */
    private static String canonNumber(double value) {
        if (value == Math.rint(value) && !Double.isInfinite(value)) {
            return Long.toString((long) value);
        }
        return Double.toString(value);
    }
}
