import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.OperatorName;
import org.apache.pdfbox.contentstream.operator.text.BeginText;
import org.apache.pdfbox.contentstream.operator.text.EndText;
import org.apache.pdfbox.contentstream.operator.text.MoveText;
import org.apache.pdfbox.contentstream.operator.text.MoveTextSetLeading;
import org.apache.pdfbox.contentstream.operator.text.NextLine;
import org.apache.pdfbox.contentstream.operator.text.SetCharSpacing;
import org.apache.pdfbox.contentstream.operator.text.SetFontAndSize;
import org.apache.pdfbox.contentstream.operator.text.SetTextHorizontalScaling;
import org.apache.pdfbox.contentstream.operator.text.SetTextLeading;
import org.apache.pdfbox.contentstream.operator.text.SetTextRenderingMode;
import org.apache.pdfbox.contentstream.operator.text.SetTextRise;
import org.apache.pdfbox.contentstream.operator.text.ShowText;
import org.apache.pdfbox.contentstream.operator.text.ShowTextAdjusted;
import org.apache.pdfbox.contentstream.operator.text.ShowTextLine;
import org.apache.pdfbox.contentstream.operator.text.ShowTextLineAndSpace;
import org.apache.pdfbox.contentstream.operator.state.Concatenate;
import org.apache.pdfbox.contentstream.operator.state.Restore;
import org.apache.pdfbox.contentstream.operator.state.Save;
import org.apache.pdfbox.contentstream.operator.state.SetGraphicsStateParameters;
import org.apache.pdfbox.contentstream.operator.state.SetMatrix;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for the COMPOSITE (Type0 / CID) font getText pipeline.
 *
 * Walks the first page's content stream with a {@link PDFStreamEngine} that
 * overrides {@code showText(byte[])}. For every glyph run drawn with a
 * {@link PDType0Font}, the multi-byte code stream is decoded exactly as the
 * stripper would (font.readCode over an InputStream so Identity-H two-byte
 * codes are honoured) and each code emits one canonical line:
 *
 *     CODE &lt;code&gt; CID &lt;cid&gt; GID &lt;gid&gt; UNI U+XXXX[ U+YYYY...]
 *
 * (UNI "(none)" when toUnicode returns null/empty). This verifies the whole
 * code -&gt; CID -&gt; GID + code -&gt; Unicode composite chain over the genuine
 * byte stream, not hand-fed codes. After the per-code block:
 *
 *     ===TEXT===
 *     &lt;PDFTextStripper output&gt;
 *
 * lets the caller diff the end-to-end extracted text too.
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; CompositeFontTextProbe input.pdf [pageIndex]
 */
public final class CompositeFontTextProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int pageIndex = args.length > 1 ? Integer.parseInt(args[1]) : 0;
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(pageIndex);
            CodeCollector engine = new CodeCollector();
            engine.processPage(page);
            for (String line : engine.lines) {
                out.println(line);
            }
            out.println("===TEXT===");
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setStartPage(pageIndex + 1);
            stripper.setEndPage(pageIndex + 1);
            out.print(stripper.getText(doc));
        }
    }

    /** Records one canonical line per composite-font code on the page. */
    private static final class CodeCollector extends PDFStreamEngine {
        final List<String> lines = new ArrayList<>();

        CodeCollector() {
            addOperator(new BeginText(this));
            addOperator(new EndText(this));
            addOperator(new SetFontAndSize(this));
            addOperator(new ShowText(this));
            addOperator(new ShowTextAdjusted(this));
            addOperator(new ShowTextLine(this));
            addOperator(new ShowTextLineAndSpace(this));
            addOperator(new MoveText(this));
            addOperator(new MoveTextSetLeading(this));
            addOperator(new NextLine(this));
            addOperator(new SetTextLeading(this));
            addOperator(new SetCharSpacing(this));
            addOperator(new SetTextHorizontalScaling(this));
            addOperator(new SetTextRenderingMode(this));
            addOperator(new SetTextRise(this));
            addOperator(new SetMatrix(this));
            addOperator(new Save(this));
            addOperator(new Restore(this));
            addOperator(new Concatenate(this));
            addOperator(new SetGraphicsStateParameters(this));
        }

        @Override
        protected void showText(byte[] string) throws IOException {
            PDFont font = getGraphicsState().getTextState().getFont();
            if (!(font instanceof PDType0Font)) {
                return;
            }
            PDType0Font t0 = (PDType0Font) font;
            InputStream in = new ByteArrayInputStream(string);
            while (in.available() > 0) {
                int code = font.readCode(in);
                int cid = t0.codeToCID(code);
                int gid = t0.codeToGID(code);
                String uni = font.toUnicode(code);
                StringBuilder sb = new StringBuilder();
                sb.append("CODE ").append(code)
                  .append(" CID ").append(cid)
                  .append(" GID ").append(gid)
                  .append(" UNI");
                if (uni == null || uni.isEmpty()) {
                    sb.append(" (none)");
                } else {
                    uni.codePoints().forEach(
                        cp -> sb.append(" U+").append(String.format("%04X", cp)));
                }
                lines.add(sb.toString());
            }
        }
    }
}
