import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;

/**
 * Live oracle probe: emit Apache PDFBox font *descriptor* metrics for every
 * font on every page of a PDF, in a canonical line-oriented format that
 * pypdfbox mirrors. Companion to FontMetricsProbe (per-code widths, wave 1408);
 * this one verifies the PDFontDescriptor metric block (wave 1412).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> FontDescProbe input.pdf
 *
 * Output (UTF-8, stdout): one block per (page, font-resource-name):
 *   FONT\t<pageIndex>\t<resourceName>\t<baseFont>\t<subType>
 *   then either:
 *     NO_DESCRIPTOR                      (getFontDescriptor() == null)
 *   or:
 *     DESC\t<fontName>\t<flags>\t<bboxLLx>\t<bboxLLy>\t<bboxURx>\t<bboxURy>\t
 *          <italicAngle>\t<ascent>\t<descent>\t<capHeight>\t<xHeight>\t
 *          <stemV>\t<missingWidth>\t<fontFamily>\t<fontWeight>
 * Float metrics are normalized to 4 decimal places (-0.0 collapsed to 0.0).
 * A missing /FontBBox is emitted as NO_BBOX in place of the 4 numbers.
 * /FontFamily that is absent is emitted as the literal "null".
 */
public final class FontDescProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res != null) {
                    for (COSName name : res.getFontNames()) {
                        emitFont(out, pageIndex, name, res);
                    }
                }
                pageIndex++;
            }
        }
    }

    private static void emitFont(PrintStream out, int pageIndex, COSName name, PDResources res) {
        PDFont font;
        try {
            font = res.getFont(name);
        } catch (Exception e) {
            out.printf("FONT\t%d\t%s\tLOAD_ERR%n", pageIndex, name.getName());
            return;
        }
        if (font == null) {
            out.printf("FONT\t%d\t%s\tNULL%n", pageIndex, name.getName());
            return;
        }
        out.printf("FONT\t%d\t%s\t%s\t%s%n",
                pageIndex, name.getName(), font.getName(), font.getSubType());

        PDFontDescriptor fd = font.getFontDescriptor();
        if (fd == null) {
            out.printf("NO_DESCRIPTOR%n");
            return;
        }

        StringBuilder sb = new StringBuilder("DESC");
        sb.append('\t').append(str(fd.getFontName()));
        sb.append('\t').append(fd.getFlags());

        PDRectangle bbox = fd.getFontBoundingBox();
        if (bbox == null) {
            sb.append('\t').append("NO_BBOX");
        } else {
            sb.append('\t').append(fmt(bbox.getLowerLeftX()));
            sb.append('\t').append(fmt(bbox.getLowerLeftY()));
            sb.append('\t').append(fmt(bbox.getUpperRightX()));
            sb.append('\t').append(fmt(bbox.getUpperRightY()));
        }

        sb.append('\t').append(fmt(fd.getItalicAngle()));
        sb.append('\t').append(fmt(fd.getAscent()));
        sb.append('\t').append(fmt(fd.getDescent()));
        sb.append('\t').append(fmt(fd.getCapHeight()));
        sb.append('\t').append(fmt(fd.getXHeight()));
        sb.append('\t').append(fmt(fd.getStemV()));
        sb.append('\t').append(fmt(fd.getMissingWidth()));
        sb.append('\t').append(str(fd.getFontFamily()));
        sb.append('\t').append(fmt(fd.getFontWeight()));
        out.printf("%s%n", sb.toString());
    }

    private static String str(String s) {
        return s == null ? "null" : s;
    }

    private static String fmt(float v) {
        // Canonical 4-decimal formatting; collapse -0.0 to 0.0.
        if (v == 0.0f) {
            v = 0.0f;
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
