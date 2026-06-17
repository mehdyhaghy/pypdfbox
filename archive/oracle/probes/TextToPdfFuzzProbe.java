import java.io.File;
import java.io.PrintStream;
import java.io.StringReader;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.tools.TextToPDF;

/**
 * Live oracle probe: differential fuzz of Apache PDFBox's
 * {@code TextToPDF.createPDFFromText(doc, reader)} across edge inputs.
 *
 * Unlike {@code TextToPdfProbe} (one fixed multi-line body, default config),
 * this probe parameterises the layout knobs so the Python port can be compared
 * across font size, page size, landscape, and margins as well as across
 * pathological text (empty, tabs, form-feeds, CR/LF, long single lines, lines
 * exactly at the wrap width, unicode beyond Latin-1, leading/trailing
 * whitespace, control chars).
 *
 * Usage:
 *   java ... TextToPdfFuzzProbe <input.txt> <output.pdf> \
 *            <fontSize> <pageSize> <landscape> <margin>
 *
 *   fontSize  float point size
 *   pageSize  one of LETTER LEGAL A4 A5 (resolved to PDRectangle)
 *   landscape "true"/"false"
 *   margin    float applied to all four margins
 *
 * Output (canonical structural summary, one fact per line):
 *   status=ok | status=err:<ExceptionSimpleName>
 *   pages=<n>
 *   text=<escaped PDFTextStripper output>
 *   fonts=<sorted comma-joined distinct /BaseFont names>
 *
 * When {@code createPDFFromText} throws (e.g. the standard font cannot encode
 * a code point), the probe emits only the {@code status=err:...} line, so the
 * Python side can pin the same raise-vs-substitute decision.
 */
public final class TextToPdfFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File inFile = new File(args[0]);
        File outFile = new File(args[1]);
        float fontSize = Float.parseFloat(args[2]);
        String pageSize = args[3];
        boolean landscape = "true".equals(args[4]);
        float margin = Float.parseFloat(args[5]);

        String text = new String(java.nio.file.Files.readAllBytes(inFile.toPath()),
                java.nio.charset.StandardCharsets.UTF_8);

        TextToPDF tool = new TextToPDF();
        tool.setFontSize((int) fontSize);
        tool.setMediaBox(resolve(pageSize));
        tool.setLandscape(landscape);
        tool.setLeftMargin(margin);
        tool.setRightMargin(margin);
        tool.setTopMargin(margin);
        tool.setBottomMargin(margin);

        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = new PDDocument()) {
            tool.createPDFFromText(doc, new StringReader(text));
            doc.save(outFile);
            sb.append("status=ok\n");
        } catch (Throwable t) {
            sb.append("status=err:").append(t.getClass().getSimpleName()).append('\n');
            out.print(sb);
            return;
        }

        try (PDDocument doc = Loader.loadPDF(outFile)) {
            sb.append("pages=").append(doc.getNumberOfPages()).append('\n');

            String extracted;
            try {
                extracted = new PDFTextStripper().getText(doc);
            } catch (Throwable t) {
                extracted = "<EXTRACT_FAIL>";
            }
            sb.append("text=").append(escape(extracted)).append('\n');

            List<String> fonts = new ArrayList<>();
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res == null) {
                    continue;
                }
                for (COSName name : res.getFontNames()) {
                    PDFont font = res.getFont(name);
                    if (font != null && !fonts.contains(font.getName())) {
                        fonts.add(font.getName());
                    }
                }
            }
            Collections.sort(fonts);
            sb.append("fonts=").append(String.join(",", fonts)).append('\n');
        }
        out.print(sb);
    }

    private static PDRectangle resolve(String name) {
        switch (name) {
            case "LEGAL":
                return PDRectangle.LEGAL;
            case "A4":
                return PDRectangle.A4;
            case "A5":
                return PDRectangle.A5;
            case "LETTER":
            default:
                return PDRectangle.LETTER;
        }
    }

    private static String escape(String s) {
        if (s == null) {
            return "null";
        }
        return s.replace("\\", "\\\\")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
