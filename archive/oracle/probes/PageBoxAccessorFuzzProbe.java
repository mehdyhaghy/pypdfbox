import java.io.File;
import java.io.IOException;
import java.io.PrintStream;
import java.util.Arrays;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;

/**
 * Differential fuzz probe for {@link PDPage} page-box / rotation / user-unit /
 * annotation ACCESSORS, Apache PDFBox 3.0.7 (wave 1552, agent B).
 *
 * <p>Complements {@code PageInheritanceFuzzProbe} (wave 1515) and the
 * well-formed {@code PageBoxProbe} / {@code PageUserUnitBoxProbe}. Those pin
 * the inherited-attribute walk, the explicit-value path, the default chain and
 * the simple clip cases. This probe drills into the page-box ACCESSOR edge
 * cases the earlier corpora never reach:
 *
 * <ul>
 *   <li>{@code /MediaBox} zero-area (degenerate edge), single-entry / empty
 *       array, over-long (5+ entries, truncated to 4), and negative-huge
 *       magnitude (the {@code -Integer.MAX_VALUE} clamp arm);</li>
 *   <li>{@code /CropBox} wrong-type (a dictionary, not an array -> default to
 *       MediaBox), one-corner-outside MediaBox (partial clip / intersection),
 *       and inverted-then-clipped (corner normalisation vs clip order);</li>
 *   <li>{@code /BleedBox} {@code /TrimBox} {@code /ArtBox} wrong-type (not an
 *       array -> fall back to resolved CropBox), zero-area and inverted
 *       explicit boxes;</li>
 *   <li>{@code /Rotate} non-integral float (90.7 truncates to 90, 269.5),
 *       off-axis float (45.0), huge multiple (3600 / -3600), numeric string
 *       ("90" -> not a COSNumber -> 0), and boolean;</li>
 *   <li>{@code /UserUnit} huge, numeric string, boolean (non-number -> 1.0);</li>
 *   <li>{@code /Annots} empty array (count 0), wrong-type variants
 *       (dictionary / integer / name), a member that is null, and a member
 *       that is a non-dict COS object (the exception-vs-skip parity pin).</li>
 * </ul>
 *
 * <p>Driven file-based exactly like {@code PageInheritanceFuzzProbe}: the
 * pypdfbox sibling writes one PDF per case plus a {@code manifest.txt} into a
 * tmp dir; both sides read the same bytes and project the identical framed
 * grammar:
 *
 * <pre>
 *   CASE &lt;name&gt; mediabox=&lt;rect|ERR:X&gt; cropbox=&lt;rect|ERR:X&gt;
 *       bleedbox=&lt;rect|ERR:X&gt; trimbox=&lt;rect|ERR:X&gt; artbox=&lt;rect|ERR:X&gt;
 *       rotate=&lt;n|ERR:X&gt; userunit=&lt;f|ERR:X&gt; resources=&lt;present|null|ERR:X&gt;
 *       annots=&lt;count|ERR:X&gt;
 * </pre>
 *
 * <p>A rectangle is rendered as {@code llx,lly,urx,ury}; each component is
 * formatted by {@link #fmt(float)} (integral values lose the trailing
 * {@code .0} so both runtimes agree). "ERR:X" means the accessor threw the
 * exception whose simple name is X.
 */
public final class PageBoxAccessorFuzzProbe {

    static PrintStream out;

    static String exc(Throwable e) {
        return "ERR:" + e.getClass().getSimpleName();
    }

    /** Format a float so 612.0 -> "612" but 612.5 -> "612.5" (both sides). */
    static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Long.toString((long) v);
        }
        return Float.toString(v);
    }

    static String rect(PDRectangle r) {
        return fmt(r.getLowerLeftX()) + "," + fmt(r.getLowerLeftY()) + ","
                + fmt(r.getUpperRightX()) + "," + fmt(r.getUpperRightY());
    }

    static String boxCell(java.util.function.Supplier<PDRectangle> s) {
        try {
            return rect(s.get());
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String rotateCell(PDPage page) {
        try {
            return Integer.toString(page.getRotation());
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String userUnitCell(PDPage page) {
        try {
            return fmt(page.getUserUnit());
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String resourcesCell(PDPage page) {
        try {
            PDResources res = page.getResources();
            return res == null ? "null" : "present";
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static String annotsCell(PDPage page) {
        try {
            List<PDAnnotation> annots = page.getAnnotations();
            return Integer.toString(annots.size());
        } catch (Throwable e) {
            return exc(e);
        }
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
            PDPage page = doc.getPage(0);
            sb.append("mediabox=").append(boxCell(page::getMediaBox));
            sb.append(" cropbox=").append(boxCell(page::getCropBox));
            sb.append(" bleedbox=").append(boxCell(page::getBleedBox));
            sb.append(" trimbox=").append(boxCell(page::getTrimBox));
            sb.append(" artbox=").append(boxCell(page::getArtBox));
            sb.append(" rotate=").append(rotateCell(page));
            sb.append(" userunit=").append(userUnitCell(page));
            sb.append(" resources=").append(resourcesCell(page));
            sb.append(" annots=").append(annotsCell(page));
        } catch (Throwable e) {
            sb.append("mediabox=LOAD:").append(e.getClass().getSimpleName())
                    .append(" cropbox=LOAD bleedbox=LOAD trimbox=LOAD "
                            + "artbox=LOAD rotate=LOAD userunit=LOAD "
                            + "resources=LOAD annots=LOAD");
        } finally {
            if (doc != null) {
                try {
                    doc.close();
                } catch (IOException ignored) {
                    // best-effort close
                }
            }
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        Arrays.stream(names)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(name -> runCase(dir, name));
    }
}
