import java.awt.geom.Rectangle2D;
import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.text.PDFTextStripperByArea;

/**
 * Live oracle probe fuzzing PDFTextStripperByArea's REGION-API surface — the
 * by-area facets the existing area probes (TextByAreaProbe / TextSortAreaProbe /
 * TextMultiRegionProbe) do not exhaustively pin: degenerate region geometry
 * (zero-area, fully-out-of-page, page-spanning, negative-coordinate), the
 * region-management lifecycle (duplicate add = replace, removeRegion of a
 * registered / unregistered name), getTextForRegion of an unregistered name,
 * many small regions, and the sort-by-position toggle applied across the whole
 * extraction.
 *
 * The caller builds a small synthetic multi-text page in pypdfbox (Standard-14
 * Helvetica, so PDFBox and pypdfbox resolve identical glyph metrics) and passes
 * its path. Every region rectangle is hard-coded HERE as an AWT Rectangle2D
 * (top-left origin, y-down — the native PDFBox convention) so the Python side
 * can mirror the SAME geometric rectangle via its user-space inverse and the
 * two engines are compared on identical inputs. The synthetic layout the rects
 * assume (612x792 page):
 *
 *   user (100, 700) "ALPHA"    -> awt (100,  92)
 *   user (400, 700) "BRAVO"    -> awt (400,  92)
 *   user (100, 400) "CHARLIE"  -> awt (100, 392)
 *   user (400, 100) "DELTA"    -> awt (400, 692)
 *
 * A single sort flag is read from args[1] ("sort" / "nosort") so the Python
 * side can pin both setSortByPosition states across the whole matrix.
 *
 * Usage: java ... TextByAreaFuzzProbe in.pdf <sort|nosort>
 *
 * Output (UTF-8): one line per CASE, "CASE:<name>:<payload>", where <payload>
 * is the escaped getTextForRegion(...) for the case's probe name, or one of the
 * literal markers EXC:<type> (an exception was thrown) / REGIONS:<csv> (the
 * getRegions() snapshot for lifecycle cases). Backslash / newline / carriage
 * return are escaped so each payload stays on a single line; the Python side
 * reverses the escape.
 */
public final class TextByAreaFuzzProbe {
    private static String esc(String s) {
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r");
    }

    private static boolean sortFlag;

    private static PDFTextStripperByArea fresh() throws Exception {
        PDFTextStripperByArea s = new PDFTextStripperByArea();
        s.setSortByPosition(sortFlag);
        return s;
    }

    private static void emit(PrintStream out, String name, String text) {
        out.print("CASE:" + name + ":" + esc(text) + "\n");
    }

    // Run a single-region extraction and emit getTextForRegion("r"), trapping
    // any thrown exception as EXC:<simpleName>.
    private static void single(
            PrintStream out, PDPage page, String name, Rectangle2D rect) {
        try {
            PDFTextStripperByArea s = fresh();
            s.addRegion("r", rect);
            s.extractRegions(page);
            emit(out, name, s.getTextForRegion("r"));
        } catch (Exception e) {
            emit(out, name, "EXC:" + e.getClass().getSimpleName());
        }
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        sortFlag = args.length < 2 || !"nosort".equals(args[1]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(0);

            // ---- degenerate single-region geometry ----
            // Region around ALPHA (awt 100,92) — the baseline capture.
            single(out, page, "around_alpha",
                    new Rectangle2D.Double(80, 80, 120, 40));
            // Zero-width region on ALPHA's x edge.
            single(out, page, "zero_width",
                    new Rectangle2D.Double(100, 80, 0, 40));
            // Zero-height region.
            single(out, page, "zero_height",
                    new Rectangle2D.Double(80, 92, 120, 0));
            // Zero-area (point) region exactly on ALPHA's origin.
            single(out, page, "zero_area_point",
                    new Rectangle2D.Double(100, 92, 0, 0));
            // Region fully outside the page (way past the right/bottom edge).
            single(out, page, "outside_page",
                    new Rectangle2D.Double(5000, 5000, 100, 100));
            // Region fully off the top (negative y), no glyph there.
            single(out, page, "outside_top",
                    new Rectangle2D.Double(100, -500, 100, 100));
            // Negative-coordinate region overlapping the top-left corner so it
            // can still reach ALPHA-band glyphs at awt y ~ 92.
            single(out, page, "neg_origin_reaches",
                    new Rectangle2D.Double(-50, 60, 300, 80));
            // Negative coords entirely off-page (no glyphs).
            single(out, page, "neg_origin_empty",
                    new Rectangle2D.Double(-500, -500, 100, 100));
            // Region larger than the whole page (captures everything).
            single(out, page, "larger_than_page",
                    new Rectangle2D.Double(-100, -100, 5000, 5000));
            // Region exactly the page size.
            single(out, page, "exact_page",
                    new Rectangle2D.Double(0, 0, 612, 792));
            // Negative width/height (AWT normalizes via getMinX/getWidth — a
            // Rectangle2D.Double with negative w/h has width()<0, and
            // contains() returns false for any point). Pins that semantics.
            single(out, page, "neg_width",
                    new Rectangle2D.Double(200, 92, -120, 40));
            single(out, page, "neg_height",
                    new Rectangle2D.Double(80, 132, 120, -40));
            // Region straddling ALPHA's left edge (glyph origin on left edge =
            // inside per Rectangle2D.contains half-open test).
            single(out, page, "left_edge_inclusive",
                    new Rectangle2D.Double(100, 80, 120, 40));
            // Region whose RIGHT edge is exactly ALPHA's origin x (exclusive ->
            // glyph excluded).
            single(out, page, "right_edge_exclusive",
                    new Rectangle2D.Double(0, 80, 100, 40));
            // Region covering CHARLIE only (awt 100,392).
            single(out, page, "around_charlie",
                    new Rectangle2D.Double(80, 380, 120, 40));
            // Tall thin region spanning ALPHA + CHARLIE columns (both glyphs).
            single(out, page, "tall_column",
                    new Rectangle2D.Double(80, 80, 120, 360));

            // ---- getTextForRegion of an unregistered name ----
            try {
                PDFTextStripperByArea s = fresh();
                s.addRegion("r", new Rectangle2D.Double(80, 80, 120, 40));
                s.extractRegions(page);
                emit(out, "unregistered_name",
                        s.getTextForRegion("does_not_exist"));
            } catch (Exception e) {
                emit(out, "unregistered_name",
                        "EXC:" + e.getClass().getSimpleName());
            }

            // getTextForRegion BEFORE any extractRegions call.
            try {
                PDFTextStripperByArea s = fresh();
                s.addRegion("r", new Rectangle2D.Double(80, 80, 120, 40));
                emit(out, "before_extract", s.getTextForRegion("r"));
            } catch (Exception e) {
                emit(out, "before_extract",
                        "EXC:" + e.getClass().getSimpleName());
            }

            // ---- duplicate region name (replace) ----
            // Add "r" around ALPHA, then re-add "r" around CHARLIE — the second
            // add replaces the rectangle but keeps the single name. After
            // extraction "r" should carry CHARLIE, not ALPHA, and getRegions()
            // should list "r" exactly once.
            try {
                PDFTextStripperByArea s = fresh();
                s.addRegion("r", new Rectangle2D.Double(80, 80, 120, 40));
                s.addRegion("r", new Rectangle2D.Double(80, 380, 120, 40));
                s.extractRegions(page);
                List<String> regions = s.getRegions();
                emit(out, "dup_replace_regions", "REGIONS:" + String.join(",", regions));
                emit(out, "dup_replace_text", s.getTextForRegion("r"));
            } catch (Exception e) {
                emit(out, "dup_replace_text",
                        "EXC:" + e.getClass().getSimpleName());
            }

            // ---- removeRegion lifecycle ----
            // Remove a registered region: gone from getRegions, empty text.
            try {
                PDFTextStripperByArea s = fresh();
                s.addRegion("keep", new Rectangle2D.Double(80, 80, 120, 40));
                s.addRegion("drop", new Rectangle2D.Double(80, 380, 120, 40));
                s.removeRegion("drop");
                s.extractRegions(page);
                emit(out, "remove_regions",
                        "REGIONS:" + String.join(",", s.getRegions()));
                emit(out, "remove_kept", s.getTextForRegion("keep"));
                emit(out, "remove_dropped", s.getTextForRegion("drop"));
            } catch (Exception e) {
                emit(out, "remove_dropped",
                        "EXC:" + e.getClass().getSimpleName());
            }

            // Remove an UNREGISTERED name: silent no-op.
            try {
                PDFTextStripperByArea s = fresh();
                s.addRegion("only", new Rectangle2D.Double(80, 80, 120, 40));
                s.removeRegion("never_added");
                s.extractRegions(page);
                emit(out, "remove_unregistered_regions",
                        "REGIONS:" + String.join(",", s.getRegions()));
                emit(out, "remove_unregistered_text", s.getTextForRegion("only"));
            } catch (Exception e) {
                emit(out, "remove_unregistered_text",
                        "EXC:" + e.getClass().getSimpleName());
            }

            // ---- many small regions ----
            // Eight tiny 4x4 regions, each on a distinct glyph origin / corner.
            // Each region's capture is emitted as its own CASE line
            // ("many_small_m<i>") so the payload is singly-escaped and the
            // Python side can compare per region.
            try {
                PDFTextStripperByArea s = fresh();
                for (int i = 0; i < 8; i++) {
                    s.addRegion("m" + i,
                            new Rectangle2D.Double(100 + i * 2, 90 + i, 4, 4));
                }
                s.extractRegions(page);
                for (String n : s.getRegions()) {
                    emit(out, "many_small_" + n, s.getTextForRegion(n));
                }
            } catch (Exception e) {
                emit(out, "many_small_exc",
                        "EXC:" + e.getClass().getSimpleName());
            }

            // ---- re-extract clears prior state ----
            // Extract with a capturing region, then remove it / add an empty
            // region and re-extract: the new run must not leak the old text.
            try {
                PDFTextStripperByArea s = fresh();
                s.addRegion("r", new Rectangle2D.Double(80, 80, 120, 40));
                s.extractRegions(page);
                String first = s.getTextForRegion("r");
                s.removeRegion("r");
                s.addRegion("r", new Rectangle2D.Double(5000, 5000, 10, 10));
                s.extractRegions(page);
                emit(out, "reextract_first", first);
                emit(out, "reextract_second", s.getTextForRegion("r"));
            } catch (Exception e) {
                emit(out, "reextract_second",
                        "EXC:" + e.getClass().getSimpleName());
            }
        }
    }
}
