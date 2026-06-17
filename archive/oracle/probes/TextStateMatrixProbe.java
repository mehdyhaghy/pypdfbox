import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.DrawObject;
import org.apache.pdfbox.contentstream.operator.state.Concatenate;
import org.apache.pdfbox.contentstream.operator.state.Restore;
import org.apache.pdfbox.contentstream.operator.state.Save;
import org.apache.pdfbox.contentstream.operator.state.SetMatrix;
import org.apache.pdfbox.contentstream.operator.text.BeginText;
import org.apache.pdfbox.contentstream.operator.text.EndText;
import org.apache.pdfbox.contentstream.operator.text.MoveText;
import org.apache.pdfbox.contentstream.operator.text.MoveTextSetLeading;
import org.apache.pdfbox.contentstream.operator.text.NextLine;
import org.apache.pdfbox.contentstream.operator.text.SetCharSpacing;
import org.apache.pdfbox.contentstream.operator.text.SetFontAndSize;
import org.apache.pdfbox.contentstream.operator.text.SetTextHorizontalScaling;
import org.apache.pdfbox.contentstream.operator.text.SetTextLeading;
import org.apache.pdfbox.contentstream.operator.text.SetTextRise;
import org.apache.pdfbox.contentstream.operator.text.SetWordSpacing;
import org.apache.pdfbox.contentstream.operator.text.ShowText;
import org.apache.pdfbox.contentstream.operator.text.ShowTextAdjusted;
import org.apache.pdfbox.contentstream.operator.text.ShowTextLine;
import org.apache.pdfbox.contentstream.operator.text.ShowTextLineAndSpace;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.util.Matrix;
import org.apache.pdfbox.util.Vector;

/**
 * Live oracle probe: emit Apache PDFBox's per-glyph text-rendering-matrix
 * and the running text-state field values as a content stream's text
 * operators are driven through the stream engine.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TextStateMatrixProbe out.pdf
 *
 * The probe builds a one-page PDF whose content stream is a FIXED raw byte
 * sequence (see {@link #CONTENT}) exercising the full text-state +
 * text-positioning operator set:
 *
 *   BT / Tf / TL / Td / TD / Tm / T* / Tc / Tw / Tz / Ts / Tj / TJ / ' / "
 *   / ET
 *
 * with a Standard-14 Helvetica font (deterministic AFM widths) and the
 * page media box anchored at the origin (identity page CTM) so the text
 * rendering matrix delivered to showGlyph() is exactly
 * ``text_local * textMatrix`` in user space — directly comparable to
 * pypdfbox's ``glyph_to_user``. The raw content bytes are byte-for-byte
 * identical to the Python reproduction in the differential test.
 *
 * For each glyph delivered to showGlyph(Matrix trm, PDFont, code, Vector)
 * the probe emits one canonical, tab-separated line:
 *
 *   code \t trmA \t trmB \t trmC \t trmD \t trmE \t trmF \t dispX
 *
 * trmA..trmF are the six text-rendering-matrix components (so font size,
 * horizontal scale and rise all fold in); trmE/trmF are the glyph origin
 * in user space; dispX is the glyph's horizontal displacement (em units).
 * Floats are rounded to %.4f with Locale.ROOT so the rendering is stable
 * across platforms / locales. Output is UTF-8 to stdout, no framing.
 */
public final class TextStateMatrixProbe {
    // The fixed content stream under test. ``/F1`` is the font name the
    // probe registers in the page resources. MUST be kept byte-for-byte in
    // sync with the Python reproduction in the differential test.
    static final String CONTENT =
            "BT\n"
            + "/F1 12 Tf\n"
            + "14 TL\n"
            + "1 0 0 1 50 350 Tm\n"
            + "(Ab) Tj\n"
            + "10 -20 Td\n"
            + "2 Tc\n"
            + "5 Tw\n"
            + "(a b) Tj\n"
            + "0 -20 TD\n"
            + "150 Tz\n"
            + "(Wi) Tj\n"
            + "T*\n"
            + "4 Ts\n"
            + "(Cy) Tj\n"
            + "100 Tz\n"
            + "0 Tc\n"
            + "0 Tw\n"
            + "0 Ts\n"
            + "0 -20 Td\n"
            + "[(A) -120 (V) 80 (a)] TJ\n"
            + "(Lo) '\n"
            + "3 1 (ow) \"\n"
            + "ET\n";

    public static void main(String[] args) throws Exception {
        final PrintStream out = new PrintStream(System.out, true, "UTF-8");
        final File outFile = new File(args[0]);

        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(new PDRectangle(0, 0, 400, 400));
            doc.addPage(page);
            PDFont font = new PDType1Font(Standard14Fonts.FontName.HELVETICA);
            PDResources resources = new PDResources();
            COSName fontName = resources.add(font);
            // The content references /F1 explicitly; force the registered
            // name to match so the engine resolves it.
            if (!"F1".equals(fontName.getName())) {
                resources.put(COSName.getPDFName("F1"),
                        resources.getFont(fontName));
            }
            page.setResources(resources);
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
                @Override
                protected void showGlyph(Matrix trm, PDFont fnt, int code,
                        Vector displacement) throws java.io.IOException {
                    sb.append(String.format(
                            Locale.ROOT,
                            "%d\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f%n",
                            code,
                            trm.getScaleX(), trm.getShearY(),
                            trm.getShearX(), trm.getScaleY(),
                            trm.getTranslateX(), trm.getTranslateY(),
                            displacement.getX()));
                    super.showGlyph(trm, fnt, code, displacement);
                }
            };
            engine.addOperator(new BeginText(engine));
            engine.addOperator(new EndText(engine));
            engine.addOperator(new SetFontAndSize(engine));
            engine.addOperator(new SetTextLeading(engine));
            engine.addOperator(new MoveText(engine));
            engine.addOperator(new MoveTextSetLeading(engine));
            engine.addOperator(new SetMatrix(engine));
            engine.addOperator(new NextLine(engine));
            engine.addOperator(new SetCharSpacing(engine));
            engine.addOperator(new SetWordSpacing(engine));
            engine.addOperator(new SetTextHorizontalScaling(engine));
            engine.addOperator(new SetTextRise(engine));
            engine.addOperator(new ShowText(engine));
            engine.addOperator(new ShowTextAdjusted(engine));
            engine.addOperator(new ShowTextLine(engine));
            engine.addOperator(new ShowTextLineAndSpace(engine));
            engine.addOperator(new Save(engine));
            engine.addOperator(new Restore(engine));
            engine.addOperator(new Concatenate(engine));
            engine.addOperator(new DrawObject(engine));
            engine.processPage(page);
        }
        out.print(sb);
    }
}
