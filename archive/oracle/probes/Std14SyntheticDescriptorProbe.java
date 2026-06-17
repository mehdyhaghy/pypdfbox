import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts.FontName;

/**
 * Live oracle probe: emit the SYNTHESISED {@link PDFontDescriptor} that Apache
 * PDFBox builds for a Standard-14 font that has NO explicit {@code
 * /FontDescriptor}. Constructing {@code new PDType1Font(FontName.X)} produces a
 * font dict carrying only {@code /BaseFont}; {@code getFontDescriptor()} then
 * returns the descriptor synthesised from the bundled AFM via
 * {@code PDType1FontEmbedder.buildFontDescriptor(FontMetrics)}.
 *
 * This covers the descriptor fields NOT already asserted by
 * Std14MetricsProbe (wave 1431, which pinned ascent/descent/capHeight/
 * xHeight/italicAngle + the bounding box): namely the IDENTITY + classification
 * block — getFontName, getFlags (the computed symbolic/non-symbolic integer),
 * getStemV, getFontFamily, getCharSet, getFontWeight, getMissingWidth.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Std14SyntheticDescriptorProbe
 *
 * Output (UTF-8, stdout), one block per font:
 *   FONT\t<baseFont>
 *   ID\t<getFontName>\t<getFlags>\t<getFontFamily>\t<getCharacterSet>
 *   NUM\t<getStemV>\t<getFontWeight>\t<getMissingWidth>
 *   CLS\t<isSymbolic>\t<isNonSymbolic>\t<isFixedPitch>\t<isSerif>\t<isItalic>\t<isForceBold>
 * Floats normalised to 4 decimal places; null strings rendered as the literal
 * "null".
 */
public final class Std14SyntheticDescriptorProbe {

    // A representative spread across the four families + both symbolic faces:
    // Helvetica (sans, non-symbolic), Times-Bold (serif), Courier (fixed
    // pitch), Symbol + ZapfDingbats (font-specific / symbolic), plus oblique /
    // bold-italic variants to exercise any italic / weight derivation.
    private static final FontName[] NAMES = {
        FontName.HELVETICA,
        FontName.HELVETICA_BOLD,
        FontName.HELVETICA_OBLIQUE,
        FontName.TIMES_ROMAN,
        FontName.TIMES_BOLD,
        FontName.TIMES_ITALIC,
        FontName.TIMES_BOLD_ITALIC,
        FontName.COURIER,
        FontName.COURIER_BOLD,
        FontName.SYMBOL,
        FontName.ZAPF_DINGBATS,
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        for (FontName name : NAMES) {
            PDType1Font font = new PDType1Font(name);
            PDFontDescriptor fd = font.getFontDescriptor();
            out.printf("FONT\t%s%n", font.getName());
            if (fd == null) {
                out.printf("NO_DESCRIPTOR%n");
                continue;
            }
            out.printf("ID\t%s\t%d\t%s\t%s%n",
                    nz(fd.getFontName()), fd.getFlags(),
                    nz(fd.getFontFamily()), nz(fd.getCharSet()));
            out.printf("NUM\t%s\t%s\t%s%n",
                    fmt(fd.getStemV()), fmt(fd.getFontWeight()),
                    fmt(fd.getMissingWidth()));
            out.printf("CLS\t%b\t%b\t%b\t%b\t%b\t%b%n",
                    fd.isSymbolic(), fd.isNonSymbolic(), fd.isFixedPitch(),
                    fd.isSerif(), fd.isItalic(), fd.isForceBold());
        }
    }

    private static String nz(String s) {
        return s == null ? "null" : s;
    }

    private static String fmt(float v) {
        if (v == 0.0f) {
            v = 0.0f; // collapse -0.0 to 0.0
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
