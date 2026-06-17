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
 * Differential fuzz probe for {@link PDPage} parsing leniency and INHERITED
 * attribute resolution, Apache PDFBox 3.0.7 (wave 1515, agent B).
 *
 * <p>Complements the well-formed {@code PageInheritanceProbe} (multi-level
 * page-tree walk with valid {@code /Pages} nodes). This probe targets the
 * MALFORMED / edge-case subset that the well-formed probe never reaches:
 *
 * <ul>
 *   <li>the four inheritable attributes ({@code /MediaBox} {@code /CropBox}
 *       {@code /Resources} {@code /Rotate}) present on the leaf page vs
 *       inherited from a {@code /Pages} ancestor vs absent everywhere — and
 *       the crucial {@code getInheritableAttribute} rule that the walk only
 *       ascends to a parent whose {@code /Type} is {@code /Pages} (a parent
 *       that is missing, not a dictionary, or carries a different/absent
 *       {@code /Type} TERMINATES the walk);</li>
 *   <li>{@code /MediaBox} missing / wrong-arity (2 entries) / non-numeric /
 *       inverted / huge-magnitude — and the upstream U.S.-Letter fallback when
 *       it is not an array at all;</li>
 *   <li>{@code /CropBox} clipping/intersection with the resolved MediaBox +
 *       default-to-MediaBox;</li>
 *   <li>{@code /BleedBox} {@code /TrimBox} {@code /ArtBox} default-to-CropBox +
 *       clip-to-MediaBox;</li>
 *   <li>{@code /Rotate} non-multiple-of-90 / negative / float / non-numeric /
 *       inherited;</li>
 *   <li>{@code /Contents} missing vs single stream vs array vs non-stream
 *       member;</li>
 *   <li>{@code /Annots} missing / non-array / non-dict member;</li>
 *   <li>{@code /UserUnit} default / explicit / non-positive / non-numeric.</li>
 * </ul>
 *
 * <p>Driven file-based exactly like {@code ResourcesLookupFuzzProbe}: the
 * pypdfbox sibling
 * (tests/pdmodel/oracle/test_page_inheritance_fuzz_wave1515.py) writes one PDF
 * per case (the fuzzed page, with a parent {@code /Pages} node for the
 * inheritance cases) plus a {@code manifest.txt} into a tmp dir. Both sides
 * read the same bytes and project the identical framed grammar:
 *
 * <pre>
 *   CASE &lt;name&gt; mediabox=&lt;rect|ERR:X&gt; cropbox=&lt;rect|ERR:X&gt;
 *       bleedbox=&lt;rect|ERR:X&gt; trimbox=&lt;rect|ERR:X&gt; artbox=&lt;rect|ERR:X&gt;
 *       rotate=&lt;n|ERR:X&gt; userunit=&lt;f|ERR:X&gt; resources=&lt;present|null|ERR:X&gt;
 *       contents=&lt;count|ERR:X&gt; annots=&lt;count|ERR:X&gt;
 * </pre>
 *
 * <p>A rectangle is rendered as {@code llx,lly,urx,ury} with each component
 * formatted by {@link #fmt(float)} (integral values lose the trailing
 * {@code .0} so both runtimes agree). "ERR:X" means the accessor threw the
 * exception whose simple name is X.
 */
public final class PageInheritanceFuzzProbe {

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

    static String contentsCell(PDPage page) {
        try {
            int count = 0;
            java.util.Iterator<?> it = page.getContentStreams();
            while (it.hasNext()) {
                it.next();
                count++;
            }
            return Integer.toString(count);
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
            sb.append(" contents=").append(contentsCell(page));
            sb.append(" annots=").append(annotsCell(page));
        } catch (Throwable e) {
            sb.append("mediabox=LOAD:").append(e.getClass().getSimpleName())
                    .append(" cropbox=LOAD bleedbox=LOAD trimbox=LOAD "
                            + "artbox=LOAD rotate=LOAD userunit=LOAD "
                            + "resources=LOAD contents=LOAD annots=LOAD");
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
