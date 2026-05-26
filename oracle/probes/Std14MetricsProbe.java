import java.io.PrintStream;
import java.util.Locale;
import org.apache.fontbox.util.BoundingBox;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;

/**
 * Live oracle probe: emit Apache PDFBox Standard-14 (AFM, non-embedded) font
 * metrics for all 14 core fonts, in a canonical line-oriented format that
 * pypdfbox mirrors.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Std14MetricsProbe
 *
 * Each font is constructed directly from its {@code Standard14Fonts.FontName}
 * (no PDF, no /Widths array) so every metric comes from the bundled Adobe Core
 * 14 AFM. Output (UTF-8, stdout): one block per font:
 *   FONT\t<baseFont>
 *   W\t<code>\t<width>            (codes 32..255, advance via getWidth(code))
 *   SW\t<sampleId>\t<width>       (getStringWidth of a sample string)
 *   BBOX\t<x0>\t<y0>\t<x1>\t<y1>  (font bounding box)
 *   DESC\t<ascent>\t<descent>\t<capHeight>\t<xHeight>\t<italicAngle>
 * Widths/metrics normalized to 4 decimal places. getWidth / getStringWidth that
 * throw are emitted as "ERR" so pypdfbox parity asserts the same failure
 * boundary. The high-value aggregate is SW over a mixed ASCII string.
 */
public final class Std14MetricsProbe {

    // All 14 standard fonts, paired with the canonical /BaseFont name.
    private static final Standard14Fonts.FontName[] NAMES = {
        Standard14Fonts.FontName.HELVETICA,
        Standard14Fonts.FontName.HELVETICA_BOLD,
        Standard14Fonts.FontName.HELVETICA_OBLIQUE,
        Standard14Fonts.FontName.HELVETICA_BOLD_OBLIQUE,
        Standard14Fonts.FontName.TIMES_ROMAN,
        Standard14Fonts.FontName.TIMES_BOLD,
        Standard14Fonts.FontName.TIMES_ITALIC,
        Standard14Fonts.FontName.TIMES_BOLD_ITALIC,
        Standard14Fonts.FontName.COURIER,
        Standard14Fonts.FontName.COURIER_BOLD,
        Standard14Fonts.FontName.COURIER_OBLIQUE,
        Standard14Fonts.FontName.COURIER_BOLD_OBLIQUE,
        Standard14Fonts.FontName.SYMBOL,
        Standard14Fonts.FontName.ZAPF_DINGBATS,
    };

    // Representative strings. Latin samples exercise the standard text fonts;
    // the Symbol / ZapfDingbats samples exercise their own built-in encodings.
    private static final String[] SAMPLE_IDS = {
        "space", "ABC", "Hello", "digits", "mixed", "punct", "latin1", "symbol",
    };
    private static final String[] SAMPLES = {
        " ",
        "ABC",
        "Hello, World!",
        "0123456789",
        "The quick brown fox jumps over 12 lazy dogs.",
        "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
        "éèüñç",      // latin-1 accented
        "ΑΒΓ•♦",      // greek + bullet + diamond
    };

    public static void main(String[] args) {
        PrintStream out;
        try {
            out = new PrintStream(System.out, true, "UTF-8");
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
        for (Standard14Fonts.FontName fn : NAMES) {
            emitFont(out, new PDType1Font(fn));
        }
    }

    private static void emitFont(PrintStream out, PDType1Font font) {
        out.printf("FONT\t%s%n", font.getName());
        for (int code = 32; code <= 255; code++) {
            String w;
            try {
                w = fmt(font.getWidth(code));
            } catch (Exception e) {
                w = "ERR";
            }
            out.printf("W\t%d\t%s%n", code, w);
        }
        for (int i = 0; i < SAMPLES.length; i++) {
            String sw;
            try {
                sw = fmt(font.getStringWidth(SAMPLES[i]));
            } catch (Exception e) {
                sw = "ERR";
            }
            out.printf("SW\t%s\t%s%n", SAMPLE_IDS[i], sw);
        }
        BoundingBox bbox;
        try {
            bbox = font.getBoundingBox();
        } catch (Exception e) {
            bbox = null;
        }
        if (bbox == null) {
            out.printf("BBOX\tNULL%n");
        } else {
            out.printf("BBOX\t%s\t%s\t%s\t%s%n",
                    fmt(bbox.getLowerLeftX()), fmt(bbox.getLowerLeftY()),
                    fmt(bbox.getUpperRightX()), fmt(bbox.getUpperRightY()));
        }
        PDFontDescriptor fd = font.getFontDescriptor();
        if (fd == null) {
            out.printf("DESC\tNULL%n");
        } else {
            out.printf("DESC\t%s\t%s\t%s\t%s\t%s%n",
                    fmt(fd.getAscent()), fmt(fd.getDescent()),
                    fmt(fd.getCapHeight()), fmt(fd.getXHeight()),
                    fmt(fd.getItalicAngle()));
        }
    }

    private static String fmt(float v) {
        // Canonical 4-decimal formatting; collapse -0.0 to 0.0.
        if (v == 0.0f) {
            v = 0.0f;
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
