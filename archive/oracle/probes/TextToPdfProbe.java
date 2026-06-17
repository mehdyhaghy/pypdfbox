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
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.tools.TextToPDF;

/**
 * Live oracle probe: Apache PDFBox's {@code TextToPDF.createPDFFromText(doc,
 * reader)} — build a PDF from plain text with default settings (Helvetica 10pt,
 * 40pt margins, 1.05 line spacing, Letter media box).
 *
 * The probe reads a UTF-8 text file, feeds it to a default-configured
 * {@link TextToPDF} via {@code createPDFFromText}, saves the result, then
 * re-loads the saved PDF and emits a canonical structural summary:
 *
 * <pre>
 *   pages=&lt;n&gt;
 *   text=&lt;escaped extracted text via PDFTextStripper&gt;
 *   fonts=&lt;sorted comma-joined distinct /BaseFont names across all pages&gt;
 * </pre>
 *
 * Usage: java -cp ... TextToPdfProbe input.txt output.pdf
 *
 * The Python side runs pypdfbox's {@code TextToPDF.create_pdf_from_text} on the
 * same text and asserts an identical summary (same page count + extracted text
 * + font), which is the parity claim for this surface.
 */
public final class TextToPdfProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File inFile = new File(args[0]);
        File outFile = new File(args[1]);

        String text = new String(java.nio.file.Files.readAllBytes(inFile.toPath()),
                java.nio.charset.StandardCharsets.UTF_8);

        TextToPDF tool = new TextToPDF();
        try (PDDocument doc = new PDDocument()) {
            tool.createPDFFromText(doc, new StringReader(text));
            doc.save(outFile);
        }

        StringBuilder sb = new StringBuilder();
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
