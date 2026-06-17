import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.DrawObject;
import org.apache.pdfbox.contentstream.operator.Operator;
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
import org.apache.pdfbox.contentstream.operator.text.SetTextLeading;
import org.apache.pdfbox.contentstream.operator.text.ShowText;
import org.apache.pdfbox.contentstream.operator.text.ShowTextLine;
import org.apache.pdfbox.contentstream.operator.text.ShowTextLineAndSpace;
import org.apache.pdfbox.contentstream.operator.text.SetWordSpacing;
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

/**
 * Live oracle probe: verify Apache PDFBox's DECOMPOSITION of the
 * move-to-next-line-and-show operators {@code ' } and {@code " } (ISO
 * 32000-1 §9.4.3).
 *
 *   ' string        ==  T* ; Tj string        (advance line by leading TL)
 *   " aw ac string  ==  Tw aw ; Tc ac ; ' string
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ShowTextLineDecompProbe out.pdf
 *
 * The probe builds a one-page PDF with a FIXED raw content stream (see
 * {@link #CONTENT}) and a Standard-14 Helvetica font on a media box anchored
 * at the origin (identity page CTM). It then drives the stream through a
 * {@link PDFStreamEngine} whose {@code processOperator(Operator,List)} is
 * overridden so that, immediately AFTER each {@code '} or {@code "}
 * operator's decomposition has run, the probe snapshots the observable
 * text state the decomposition is supposed to mutate:
 *
 *   - the text-LINE-matrix origin (translateX/translateY) — advanced by the
 *     {@code T*} step of the decomposition (so it must drop by the leading);
 *   - the word spacing (Tw) and character spacing (Tc) text-state fields —
 *     set by the {@code "} decomposition, left untouched by a bare {@code '}.
 *
 * For each {@code '}/{@code "} operator the probe emits one canonical
 * tab-separated line:
 *
 *   opName \t lineTx \t lineTy \t wordSpacing \t charSpacing
 *
 * Floats rounded to %.4f with Locale.ROOT so the rendering is stable across
 * platforms / locales. Output is UTF-8 to stdout, no framing.
 */
public final class ShowTextLineDecompProbe {
    // The fixed content stream under test. ``/F1`` is the font name the
    // probe registers in the page resources. MUST be kept byte-for-byte in
    // sync with the Python reproduction in the differential test.
    static final String CONTENT =
            "BT\n"
            + "/F1 12 Tf\n"
            + "16 TL\n"
            + "1 0 0 1 100 700 Tm\n"
            + "(L0) Tj\n"
            + "(L1) '\n"
            + "(L2) '\n"
            + "3 7 (L3) \"\n"
            + "(L4) '\n"
            + "1.5 2.5 (L5) \"\n"
            + "ET\n";

    public static void main(String[] args) throws Exception {
        final PrintStream out = new PrintStream(System.out, true, "UTF-8");
        final File outFile = new File(args[0]);

        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(new PDRectangle(0, 0, 400, 800));
            doc.addPage(page);
            PDFont font = new PDType1Font(Standard14Fonts.FontName.HELVETICA);
            PDResources resources = new PDResources();
            COSName fontName = resources.add(font);
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
                protected void processOperator(Operator operator,
                        List<org.apache.pdfbox.cos.COSBase> operands)
                        throws java.io.IOException {
                    super.processOperator(operator, operands);
                    String name = operator.getName();
                    if ("'".equals(name) || "\"".equals(name)) {
                        Matrix lm = getTextLineMatrix();
                        float tw = getGraphicsState().getTextState()
                                .getWordSpacing();
                        float tc = getGraphicsState().getTextState()
                                .getCharacterSpacing();
                        sb.append(String.format(
                                Locale.ROOT,
                                "%s\t%.4f\t%.4f\t%.4f\t%.4f%n",
                                name,
                                lm.getTranslateX(), lm.getTranslateY(),
                                tw, tc));
                    }
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
            engine.addOperator(new ShowText(engine));
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
