import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;

/**
 * Live oracle probe: emit Apache PDFBox font metrics for every font on every
 * page of a PDF, in a canonical line-oriented format that pypdfbox mirrors.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> FontMetricsProbe input.pdf
 *
 * Output (UTF-8, stdout): one block per (page, font-resource-name):
 *   FONT\t<pageIndex>\t<resourceName>\t<baseFont>\t<subType>\t<isEmbedded>
 *   W\t<code>\t<width>          (codes 32..126, advance via getWidth(code))
 *   SW\t<sampleId>\t<width>     (getStringWidth of a sample string)
 * Widths are normalized to 4 decimal places. getWidth / getStringWidth that
 * throw (unmappable codes in subset fonts, missing glyphs) are emitted as
 * "ERR" so pypdfbox parity can assert the same failure boundary.
 */
public final class FontMetricsProbe {
    private static final String[] SAMPLE_IDS = {"space", "ABC", "Hello", "digits"};
    private static final String[] SAMPLES = {" ", "ABC", "Hello", "0123456789"};

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
        String baseFont = font.getName();
        String subType = font.getSubType();
        boolean embedded;
        try {
            embedded = font.isEmbedded();
        } catch (Exception e) {
            embedded = false;
        }
        out.printf("FONT\t%d\t%s\t%s\t%s\t%b%n",
                pageIndex, name.getName(), baseFont, subType, embedded);
        for (int code = 32; code <= 126; code++) {
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
    }

    private static String fmt(float v) {
        // Canonical 4-decimal formatting; collapse -0.0 to 0.0.
        if (v == 0.0f) {
            v = 0.0f;
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
