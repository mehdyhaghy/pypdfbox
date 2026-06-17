import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;

/**
 * Live oracle probe: emit a CANONICAL, deterministic listing of every
 * annotation on every page of a PDF, as Apache PDFBox parses them.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> AnnotProbe input.pdf
 *
 * Output (UTF-8, LF-terminated lines): one line per annotation, grouped by
 * page (0-based page index) and sorted WITHIN a page by the canonical field
 * tuple so the order is independent of /Annots array order:
 *
 *   page <pageIndex> <subtype> rect=<x0>,<y0>,<x1>,<y1> contents=<0|1> apN=<0|1>
 *
 * Where:
 *   - subtype  = /Subtype name (or "?" when absent)
 *   - rect     = the four PDRectangle corners rounded to the nearest int
 *                (lowerLeftX, lowerLeftY, upperRightX, upperRightY); "none"
 *                when /Rect is missing or unparsable
 *   - contents = 1 when a non-null /Contents string is present, else 0
 *   - apN      = 1 when /AP has a normal (/N) appearance entry, else 0
 *
 * Rect corners are rounded to int so float-formatting differences between
 * Java and Python never produce a spurious mismatch (the task asks for "rect
 * (4 ints)").
 */
public final class AnnotProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            StringBuilder sb = new StringBuilder();
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                List<String> lines = new ArrayList<>();
                for (PDAnnotation annot : page.getAnnotations()) {
                    lines.add(line(pageIndex, annot));
                }
                Collections.sort(lines);
                for (String l : lines) {
                    sb.append(l).append('\n');
                }
                pageIndex++;
            }
            out.print(sb);
        }
    }

    private static String line(int pageIndex, PDAnnotation annot) {
        String subtype = annot.getSubtype();
        if (subtype == null) {
            subtype = "?";
        }
        String rect = rect(annot.getRectangle());
        int contents = annot.getContents() != null ? 1 : 0;
        int apN = hasNormalAppearance(annot) ? 1 : 0;
        return "page " + pageIndex + " " + subtype + " rect=" + rect
                + " contents=" + contents + " apN=" + apN;
    }

    private static String rect(PDRectangle r) {
        if (r == null) {
            return "none";
        }
        return Math.round(r.getLowerLeftX()) + "," + Math.round(r.getLowerLeftY())
                + "," + Math.round(r.getUpperRightX()) + "," + Math.round(r.getUpperRightY());
    }

    private static boolean hasNormalAppearance(PDAnnotation annot) {
        PDAppearanceDictionary ap = annot.getAppearance();
        if (ap == null) {
            return false;
        }
        return ap.getNormalAppearance() != null;
    }
}
