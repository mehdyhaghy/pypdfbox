import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.pagenavigation.PDTransition;

/**
 * Live oracle probe: emit Apache PDFBox's per-page page-transition (``/Trans``)
 * dictionary state via the typed ``PDTransition`` accessors.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> PageTransProbe input.pdf
 *
 * Output (UTF-8, LF-terminated), one block per page:
 *
 *   page <i> trans <yes|no>
 *   page <i> S <style> D <duration> Dm <dim> M <motion> Di <direction> SS <scale> B <flag>
 *
 * When the page carries no ``/Trans`` dictionary the second line is omitted and
 * the first line ends with ``trans no``. When it does carry one we emit the
 * canonical PDFBox 3.0.7 values for:
 *
 *   - ``/S``   transition style (Split / Blinds / Box / Wipe / Dissolve /
 *               Glitter / R / Fly / Push / Cover / Uncover / Fade); default
 *               ``R`` per upstream when absent.
 *   - ``/D``   duration in seconds; default ``1`` per upstream when absent.
 *   - ``/Dm``  dimension (``H`` / ``V``); default ``H`` per upstream when
 *               absent.
 *   - ``/M``   motion (``I`` / ``O``); default ``I`` per upstream when absent.
 *   - ``/Di``  direction; PDFBox returns a ``COSBase`` (the raw entry, or
 *               ``COSInteger.ZERO`` when absent, or the name ``/None`` when
 *               the spec sentinel is set). We render the integer degrees
 *               (``0`` / ``90`` / ``180`` / ``270`` / ``315``) or the literal
 *               ``None`` for the spec sentinel.
 *   - ``/SS``  fly scale; default ``1`` per upstream when absent.
 *   - ``/B``   fly-area-opaque boolean (``true`` / ``false``); default
 *               ``false`` per upstream when absent.
 *
 * Floats render canonically (integral values without a trailing ``.0``;
 * non-integral with up to 4 decimals, trailing zeros stripped) so the Python
 * side can compare byte-for-byte. Locale.ROOT keeps ``.`` as the separator.
 */
public final class PageTransProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 1) {
            System.err.println("usage: PageTransProbe <pdf>");
            System.exit(2);
        }
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            StringBuilder sb = new StringBuilder();
            int index = 0;
            for (PDPage page : doc.getPages()) {
                PDTransition trans = page.getTransition();
                if (trans == null) {
                    sb.append("page ").append(index).append(" trans no\n");
                } else {
                    sb.append("page ").append(index).append(" trans yes\n");
                    sb.append("page ").append(index)
                      .append(" S ").append(trans.getStyle())
                      .append(" D ").append(fmt(trans.getDuration()))
                      .append(" Dm ").append(trans.getDimension())
                      .append(" M ").append(trans.getMotion())
                      .append(" Di ").append(direction(trans.getDirection()))
                      .append(" SS ").append(fmt(trans.getFlyScale()))
                      .append(" B ").append(trans.isFlyAreaOpaque())
                      .append('\n');
                }
                index++;
            }
            out.print(sb);
        }
    }

    /**
     * Render the ``/Di`` raw COS direction. PDFBox returns ``COSInteger.ZERO``
     * when ``/Di`` is absent (the default LEFT_TO_RIGHT direction), a
     * ``COSInteger`` for the degree value otherwise, and ``COSName.NONE``
     * for the spec's ``/None`` sentinel (Fly with non-unit SS).
     */
    private static String direction(COSBase value) {
        if (value instanceof COSInteger) {
            return Long.toString(((COSInteger) value).longValue());
        }
        if (value instanceof COSName) {
            return ((COSName) value).getName();
        }
        return "?";
    }

    /**
     * Canonical float rendering: integral values without a trailing ``.0``,
     * non-integral with up to 4 decimals, trailing zeros stripped. Locale.ROOT
     * so the decimal separator is always ``.``.
     */
    private static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Long.toString((long) v);
        }
        String s = String.format(Locale.ROOT, "%.4f", v);
        int end = s.length();
        while (end > 0 && s.charAt(end - 1) == '0') {
            end--;
        }
        if (end > 0 && s.charAt(end - 1) == '.') {
            end--;
        }
        return s.substring(0, end);
    }
}
