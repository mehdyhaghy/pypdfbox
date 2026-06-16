import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe fuzzing PDFTextStripper's extraction-OPTION surface: the
 * page-range bounds (setStartPage / setEndPage, including out-of-range,
 * zero/negative, start>end), the separator/markers (line / word / paragraph /
 * page), and the boolean toggles (sortByPosition, shouldSeparateByBeads,
 * addMoreFormatting, suppressDuplicateOverlappingText) over a small synthetic
 * multi-page document built by the caller in pypdfbox.
 *
 * Unlike ExtractTextRangeProbe (which mirrors the ExtractText CLI's
 * Math.min(endPage, pageCount) clamp), this probe drives setStartPage /
 * setEndPage with the RAW caller value so the stripper's own out-of-range
 * tolerance is observed directly: PDFTextStripper.processPages iterates the
 * page tree and only emits a page when currentPageNo >= startPage &&
 * currentPageNo <= endPage, so a 0 / negative start or a beyond-the-end value
 * never throws — it simply selects an empty or full slice.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TextStripperOptionFuzzProbe in.pdf
 *
 * Output (UTF-8): one line per case, "CASE:<name>:<escaped-text>", with
 * backslash / newline / carriage-return escaped so each payload stays on a
 * single line. The Python side reverses the escape and asserts per case.
 */
public final class TextStripperOptionFuzzProbe {
    private static String esc(String s) {
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r");
    }

    private static PDFTextStripper fresh() throws Exception {
        return new PDFTextStripper();
    }

    private static void emit(PrintStream out, String name, String text) {
        out.print("CASE:" + name + ":" + esc(text) + "\n");
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pageCount = doc.getNumberOfPages();

            // ---- page-range bounds (raw, no CLI clamp) ----
            PDFTextStripper s;

            s = fresh();
            emit(out, "default_full", s.getText(doc));

            s = fresh(); s.setStartPage(0);
            emit(out, "start_zero", s.getText(doc));

            s = fresh(); s.setStartPage(-5);
            emit(out, "start_negative", s.getText(doc));

            s = fresh(); s.setEndPage(0);
            emit(out, "end_zero", s.getText(doc));

            s = fresh(); s.setEndPage(-3);
            emit(out, "end_negative", s.getText(doc));

            s = fresh(); s.setEndPage(pageCount + 100);
            emit(out, "end_beyond", s.getText(doc));

            s = fresh(); s.setStartPage(pageCount + 50);
            emit(out, "start_beyond", s.getText(doc));

            s = fresh(); s.setStartPage(3); s.setEndPage(1);
            emit(out, "start_gt_end", s.getText(doc));

            s = fresh(); s.setStartPage(2); s.setEndPage(2);
            emit(out, "single_page_2", s.getText(doc));

            s = fresh(); s.setStartPage(2); s.setEndPage(3);
            emit(out, "range_2_3", s.getText(doc));

            s = fresh(); s.setStartPage(0); s.setEndPage(pageCount + 9);
            emit(out, "start_zero_end_beyond", s.getText(doc));

            // ---- sort-by-position ----
            s = fresh(); s.setSortByPosition(true);
            emit(out, "sort_true", s.getText(doc));

            s = fresh(); s.setSortByPosition(false);
            emit(out, "sort_false", s.getText(doc));

            s = fresh(); s.setSortByPosition(true); s.setStartPage(3); s.setEndPage(3);
            emit(out, "sort_true_page3", s.getText(doc));

            s = fresh(); s.setSortByPosition(false); s.setStartPage(3); s.setEndPage(3);
            emit(out, "sort_false_page3", s.getText(doc));

            // ---- custom separators / markers ----
            s = fresh(); s.setWordSeparator("_WS_");
            emit(out, "word_sep", s.getText(doc));

            s = fresh(); s.setLineSeparator("_LS_\n");
            emit(out, "line_sep", s.getText(doc));

            s = fresh(); s.setWordSeparator("~"); s.setLineSeparator("#\n");
            s.setStartPage(1); s.setEndPage(1);
            emit(out, "word_line_sep_p1", s.getText(doc));

            s = fresh(); s.setParagraphStart("[PS]"); s.setParagraphEnd("[PE]");
            emit(out, "para_markers", s.getText(doc));

            s = fresh(); s.setPageStart("<S>"); s.setPageEnd("<E>\n");
            emit(out, "page_markers", s.getText(doc));

            s = fresh();
            s.setWordSeparator("|w|"); s.setLineSeparator("|l|\n");
            s.setParagraphStart("|ps|"); s.setParagraphEnd("|pe|");
            s.setPageStart("|S|"); s.setPageEnd("|E|\n");
            emit(out, "all_separators", s.getText(doc));

            s = fresh(); s.setWordSeparator("");
            emit(out, "empty_word_sep", s.getText(doc));

            // ---- bead separation ----
            s = fresh(); s.setShouldSeparateByBeads(true);
            emit(out, "beads_true", s.getText(doc));

            s = fresh(); s.setShouldSeparateByBeads(false);
            emit(out, "beads_false", s.getText(doc));

            // ---- add more formatting ----
            s = fresh(); s.setAddMoreFormatting(true);
            emit(out, "more_formatting", s.getText(doc));

            s = fresh(); s.setAddMoreFormatting(true); s.setLineSeparator("/N/\n");
            emit(out, "more_formatting_lsep", s.getText(doc));

            // ---- suppress duplicate overlapping text ----
            s = fresh(); s.setSuppressDuplicateOverlappingText(true);
            emit(out, "suppress_dup_true", s.getText(doc));

            s = fresh(); s.setSuppressDuplicateOverlappingText(false);
            emit(out, "suppress_dup_false", s.getText(doc));

            s = fresh(); s.setSuppressDuplicateOverlappingText(true);
            s.setSortByPosition(true);
            emit(out, "suppress_dup_sorted", s.getText(doc));

            // ---- whitespace-only / empty page slices ----
            // The synthetic doc has a final whitespace-only page; isolate it.
            s = fresh(); s.setStartPage(pageCount); s.setEndPage(pageCount);
            emit(out, "last_page_only", s.getText(doc));

            s = fresh(); s.setStartPage(pageCount); s.setEndPage(pageCount);
            s.setSortByPosition(true);
            emit(out, "last_page_sorted", s.getText(doc));
        }
    }
}
