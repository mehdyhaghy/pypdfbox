import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe: differential-fuzz PDFTextStripper text extraction over
 * text drawn with non-trivial text matrices (Tm rotation 45/90/180/270),
 * page /Rotate combined with upright text, text rise (super/subscript),
 * extreme horizontal scaling (Tz), opposite-direction runs on one line, and
 * bottom-to-top text — each extracted with sort-by-position ON and OFF
 * (wave 1557).
 *
 * The existing rotated probes (RotatedTextDirProbe, RotatedMultiLineProbe,
 * RotatedUprightTextProbe, TextStateMatrixProbe, TextRiseProbe,
 * TextHorizScalingProbe, SortByPositionProbe) each isolate ONE facet on a
 * fixed page. This probe sweeps a MATRIX of ~30 configurations so the
 * direction-grouping + reading-order reconstruction is exercised across the
 * combinatorial surface, and emits both the sorted and unsorted extraction
 * for each so a sort-only divergence is directly observable.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> RotatedTextFuzzProbe build <id> <out.pdf>
 *       Build configuration <id> into out.pdf. The Python side loads the SAME
 *       probe-built PDF, so the input bytes are identical on both engines.
 *   java -cp <pdfbox-app.jar>:<build> RotatedTextFuzzProbe extract <in.pdf>
 *       Emit, for the file, two framed UTF-8 sections (newlines escaped to
 *       "\n" so each marker stays one line; the Python side reverses it):
 *           SORTED:<text>      sort-by-position ON
 *           UNSORTED:<text>    sort-by-position OFF
 *       or, on any exception during extraction, EXC:<SimpleClassName>.
 *
 * Configuration ids (each a single LETTER page, MediaBox at origin):
 *   tm_0 tm_45 tm_90 tm_180 tm_270   text matrix rotated by N degrees about
 *                                    its own origin (page /Rotate 0)
 *   page_0 page_90 page_180 page_270 upright identity-Tm text, page /Rotate N
 *   combo_90 combo_180 combo_270     page /Rotate N AND text Tm rotated N
 *                                    (cancels to visually-upright reading)
 *   rise_pos rise_neg                superscript (+rise) / subscript (-rise)
 *                                    run mid-line
 *   tz_wide tz_narrow                horizontal scaling 300 / 25 percent
 *   opposite_dir                     two runs on one baseline, second rotated
 *                                    180 deg (reads right-to-left visually)
 *   bottom_to_top                    a column of glyphs drawn going up the page
 *                                    (Tm rotated 90 deg, successive baselines)
 *   multiline_45                     three short lines each Tm-rotated 45 deg
 *   mixed_dirs                       upright heading + 90-deg sidebar + 270-deg
 *                                    sidebar on one page (3 directions)
 *   rotate90_multiline               page /Rotate 90 with several upright lines
 *   tm_neg_scale                     Tm with negative d (vertically mirrored)
 *   rise_zero_baseline               rise applied then reset, same baseline
 */
public final class RotatedTextFuzzProbe {

    private static final float SIZE = 14f;

    private static String esc(String s) {
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r");
    }

    private static PDType1Font helv() {
        return new PDType1Font(Standard14Fonts.FontName.HELVETICA);
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("build".equals(mode)) {
            build(args[1], new File(args[2]));
            return;
        }
        if ("extract".equals(mode)) {
            try {
                String sorted;
                String unsorted;
                try (PDDocument doc = Loader.loadPDF(new File(args[1]))) {
                    PDFTextStripper s = new PDFTextStripper();
                    s.setSortByPosition(true);
                    sorted = s.getText(doc);
                }
                try (PDDocument doc = Loader.loadPDF(new File(args[1]))) {
                    PDFTextStripper s = new PDFTextStripper();
                    s.setSortByPosition(false);
                    unsorted = s.getText(doc);
                }
                out.print("SORTED:" + esc(sorted) + "\n");
                out.print("UNSORTED:" + esc(unsorted) + "\n");
            } catch (Throwable t) {
                out.print("EXC:" + t.getClass().getSimpleName() + "\n");
            }
            return;
        }
        throw new IllegalArgumentException("unknown mode: " + mode);
    }

    private static void rot(PDPageContentStream cs, PDType1Font f, String text,
            double deg, float x, float y) throws Exception {
        cs.beginText();
        cs.setFont(f, SIZE);
        cs.setTextMatrix(Matrix.getRotateInstance(Math.toRadians(deg), x, y));
        cs.showText(text);
        cs.endText();
    }

    private static void upright(PDPageContentStream cs, PDType1Font f,
            String text, float x, float y) throws Exception {
        cs.beginText();
        cs.setFont(f, SIZE);
        cs.newLineAtOffset(x, y);
        cs.showText(text);
        cs.endText();
    }

    private static void build(String id, File target) throws Exception {
        int rotate = 0;
        if ("page_90".equals(id) || "combo_90".equals(id)) {
            rotate = 90;
        } else if ("page_180".equals(id) || "combo_180".equals(id)) {
            rotate = 180;
        } else if ("page_270".equals(id) || "combo_270".equals(id)) {
            rotate = 270;
        } else if ("rotate90_multiline".equals(id)) {
            rotate = 90;
        }

        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.LETTER);
            page.setRotation(rotate);
            doc.addPage(page);
            PDType1Font f = helv();
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                switch (id) {
                    case "tm_0":
                        rot(cs, f, "Zero", 0, 200, 600);
                        break;
                    case "tm_45":
                        rot(cs, f, "FortyFive", 45, 200, 400);
                        break;
                    case "tm_90":
                        rot(cs, f, "Ninety", 90, 300, 300);
                        break;
                    case "tm_180":
                        rot(cs, f, "OneEighty", 180, 350, 500);
                        break;
                    case "tm_270":
                        rot(cs, f, "TwoSeventy", 270, 200, 400);
                        break;
                    case "page_0":
                    case "page_90":
                    case "page_180":
                    case "page_270":
                        upright(cs, f, "Upright on rotated page", 100, 600);
                        break;
                    case "combo_90":
                        rot(cs, f, "ComboNinety", 90, 300, 300);
                        break;
                    case "combo_180":
                        rot(cs, f, "ComboOneEighty", 180, 350, 500);
                        break;
                    case "combo_270":
                        rot(cs, f, "ComboTwoSeventy", 270, 300, 400);
                        break;
                    case "rise_pos":
                        cs.beginText();
                        cs.setFont(f, SIZE);
                        cs.newLineAtOffset(100, 500);
                        cs.showText("E=mc");
                        cs.setTextRise(6);
                        cs.showText("2");
                        cs.setTextRise(0);
                        cs.showText(" tail");
                        cs.endText();
                        break;
                    case "rise_neg":
                        cs.beginText();
                        cs.setFont(f, SIZE);
                        cs.newLineAtOffset(100, 500);
                        cs.showText("H");
                        cs.setTextRise(-4);
                        cs.showText("2");
                        cs.setTextRise(0);
                        cs.showText("O done");
                        cs.endText();
                        break;
                    case "rise_zero_baseline":
                        cs.beginText();
                        cs.setFont(f, SIZE);
                        cs.newLineAtOffset(100, 500);
                        cs.showText("A");
                        cs.setTextRise(5);
                        cs.setTextRise(0);
                        cs.showText("BC");
                        cs.endText();
                        break;
                    case "tz_wide":
                        cs.beginText();
                        cs.setFont(f, SIZE);
                        cs.newLineAtOffset(100, 500);
                        cs.setHorizontalScaling(300);
                        cs.showText("Wide text");
                        cs.endText();
                        break;
                    case "tz_narrow":
                        cs.beginText();
                        cs.setFont(f, SIZE);
                        cs.newLineAtOffset(100, 500);
                        cs.setHorizontalScaling(25);
                        cs.showText("Narrow text");
                        cs.endText();
                        break;
                    case "opposite_dir":
                        // First run upright, second run rotated 180 about a
                        // point to its right so it reads back toward the first.
                        rot(cs, f, "FORWARD", 0, 150, 500);
                        rot(cs, f, "DRAWKCAB", 180, 450, 514);
                        break;
                    case "bottom_to_top":
                        // Three short runs each rotated 90 deg, stacked so the
                        // column reads bottom-to-top in stream order.
                        rot(cs, f, "alpha", 90, 200, 200);
                        rot(cs, f, "beta", 90, 230, 200);
                        rot(cs, f, "gamma", 90, 260, 200);
                        break;
                    case "multiline_45":
                        rot(cs, f, "Line one", 45, 150, 300);
                        rot(cs, f, "Line two", 45, 170, 320);
                        rot(cs, f, "Line three", 45, 190, 340);
                        break;
                    case "mixed_dirs":
                        upright(cs, f, "Heading across top", 100, 700);
                        rot(cs, f, "Left sidebar up", 90, 80, 300);
                        rot(cs, f, "Right sidebar down", 270, 540, 500);
                        break;
                    case "rotate90_multiline":
                        cs.beginText();
                        cs.setFont(f, SIZE);
                        cs.newLineAtOffset(100, 700);
                        cs.showText("Heading Title");
                        cs.newLineAtOffset(0, -20);
                        cs.showText("First body line");
                        cs.newLineAtOffset(0, -20);
                        cs.showText("Second body line");
                        cs.endText();
                        break;
                    case "tm_neg_scale":
                        cs.beginText();
                        cs.setFont(f, SIZE);
                        // a=1 b=0 c=0 d=-1 -> vertically mirrored text.
                        cs.setTextMatrix(new Matrix(1, 0, 0, -1, 200, 500));
                        cs.showText("Mirrored");
                        cs.endText();
                        break;
                    default:
                        throw new IllegalArgumentException("unknown id: " + id);
                }
            }
            doc.save(target);
        }
    }
}
