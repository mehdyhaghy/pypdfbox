import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;

/**
 * Live oracle probe: pin Apache PDFBox Standard-14 (AFM, non-embedded) per-code
 * height / width-from-font / average-font-width metrics that the aggregate
 * {@code Std14MetricsProbe} (which only covers getWidth / getStringWidth /
 * bbox / descriptor) does not exercise.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Std14HeightWidthProbe
 *
 * Output (UTF-8, stdout): one block per probed font:
 *   FONT\t<baseFont>
 *   H\t<code>\t<getHeight(code)>
 *   WF\t<code>\t<getWidthFromFont(code)>
 *   AVG\t<getAverageFontWidth()>
 * Values normalized to 4 decimal places; getHeight that throws -> "ERR".
 */
public final class Std14HeightWidthProbe {

    private static final Standard14Fonts.FontName[] NAMES = {
        Standard14Fonts.FontName.HELVETICA,
        Standard14Fonts.FontName.TIMES_BOLD,
        Standard14Fonts.FontName.SYMBOL,
        Standard14Fonts.FontName.COURIER,
    };

    // Probe a representative spread: space (32), digits, A..Z start,
    // lowercase, accented latin-1, and a few high codes.
    private static final int[] CODES = {
        32, 33, 48, 65, 66, 67, 97, 98, 99, 101, 109, 200, 233, 255,
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        for (Standard14Fonts.FontName fn : NAMES) {
            PDType1Font font = new PDType1Font(fn);
            out.printf("FONT\t%s%n", font.getName());
            for (int code : CODES) {
                String h;
                try {
                    h = fmt(font.getHeight(code));
                } catch (Exception e) {
                    h = "ERR";
                }
                out.printf("H\t%d\t%s%n", code, h);
            }
            for (int code : CODES) {
                String wf;
                try {
                    wf = fmt(font.getWidthFromFont(code));
                } catch (Exception e) {
                    wf = "ERR";
                }
                out.printf("WF\t%d\t%s%n", code, wf);
            }
            out.printf("AVG\t%s%n", fmt(font.getAverageFontWidth()));
        }
    }

    private static String fmt(float v) {
        if (v == 0.0f) {
            v = 0.0f;
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
