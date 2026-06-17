import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.state.Concatenate;
import org.apache.pdfbox.contentstream.operator.state.Restore;
import org.apache.pdfbox.contentstream.operator.state.Save;
import org.apache.pdfbox.contentstream.operator.state.SetLineWidth;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe: emit Apache PDFBox's graphics-state SAVE / RESTORE (q/Q)
 * stack behaviour as a content stream is driven through the stream engine.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> QSaveRestoreProbe out.pdf
 *
 * The probe builds a one-page PDF whose content stream is a FIXED raw byte
 * sequence (see {@link #CONTENT}) exercising:
 *
 *   - nested q ... q ... Q ... Q (a two-level save/restore stack);
 *   - a cm (CTM concat) and a w (line width) MUTATED inside each q block,
 *     verifying the prior CTM + line width are restored on the matching Q;
 *   - an UNBALANCED extra Q (more Q than q) that PDFBox swallows via
 *     EmptyGraphicsStackException (PDFBOX-161) rather than aborting, so the
 *     operator AFTER the bad Q still runs;
 *   - a final q left OPEN at end-of-stream (no matching Q).
 *
 * The page media box is anchored at the origin (0,0,400,400) so the initial
 * CTM the engine seeds is the identity — the captured CTM is therefore the
 * pure user-space CTM (independent of any device / y-flip transform), making
 * it directly comparable to pypdfbox's renderer ``_gs.ctm``.
 *
 * After EVERY operator the probe appends one canonical, tab-separated line:
 *
 *   seq \t opName \t depth \t lw \t a \t b \t c \t d \t e \t f
 *
 * where depth is getGraphicsStackSize(), lw is the current line width, and
 * a..f are the current CTM components. Floats are rounded to %.4f with
 * Locale.ROOT so the rendering is stable across platforms / locales. Output
 * is UTF-8 to stdout, no framing.
 */
public final class QSaveRestoreProbe {
    // The fixed content stream under test. MUST be kept byte-for-byte in sync
    // with the Python reproduction in the differential test.
    static final String CONTENT =
            "1 w\n"
            + "q\n"
            + "2 w\n"
            + "3 0 0 3 10 20 cm\n"
            + "q\n"
            + "5 w\n"
            + "1 0 0 1 5 5 cm\n"
            + "Q\n"
            + "Q\n"
            + "Q\n"
            + "4 w\n"
            + "q\n"
            + "6 w\n"
            + "7 0 0 7 1 2 cm\n";

    public static void main(String[] args) throws Exception {
        final PrintStream out = new PrintStream(System.out, true, "UTF-8");
        final File outFile = new File(args[0]);

        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(new PDRectangle(0, 0, 400, 400));
            doc.addPage(page);
            page.setResources(new PDResources());
            PDStream contents = new PDStream(doc,
                    new ByteArrayInputStream(
                            CONTENT.getBytes(StandardCharsets.US_ASCII)));
            page.setContents(contents);
            doc.save(outFile);
        }

        final StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(outFile)) {
            PDPage page = doc.getPage(0);
            PDFStreamEngine engine = new PDFStreamEngine() {
                private int seq = 0;

                @Override
                public void processOperator(Operator operator,
                        List<COSBase> operands) throws java.io.IOException {
                    super.processOperator(operator, operands);
                    Matrix ctm =
                            getGraphicsState().getCurrentTransformationMatrix();
                    sb.append(String.format(
                            Locale.ROOT,
                            "%d\t%s\t%d\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f%n",
                            seq++,
                            operator.getName(),
                            getGraphicsStackSize(),
                            getGraphicsState().getLineWidth(),
                            ctm.getScaleX(), ctm.getShearY(),
                            ctm.getShearX(), ctm.getScaleY(),
                            ctm.getTranslateX(), ctm.getTranslateY()));
                }
            };
            engine.addOperator(new Save(engine));
            engine.addOperator(new Restore(engine));
            engine.addOperator(new Concatenate(engine));
            engine.addOperator(new SetLineWidth(engine));
            engine.processPage(page);
        }
        out.print(sb);
    }
}
