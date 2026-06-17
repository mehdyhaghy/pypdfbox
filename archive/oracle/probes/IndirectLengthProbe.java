import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: load a PDF whose content-stream ``/Length`` is an
 * indirect reference (PDF 1.7 §7.3.8 — writers compute the final length
 * after writing the stream body, so ``/Length 5 0 R`` pointing at
 * ``5 0 obj 123 endobj`` is common in real files). Emit:
 *
 *   pages=<n>
 *   length=<resolved-/Length>
 *   text=<escaped extracted text>
 *
 * The resolved ``/Length`` is read off the page's first content stream's
 * dictionary after parsing — once PDFBox has chased the indirect reference
 * (or recovered the body by scanning to ``endstream``) it rewrites the
 * stream dictionary's ``/Length`` with the actual byte count. This is the
 * semantic gold standard for indirect-length parity: pages + extracted
 * text + the post-parse length must all match pypdfbox.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> IndirectLengthProbe input.pdf
 *
 * Output is UTF-8, LF-terminated. ``PARSE_FAIL\n`` on any throw.
 */
public final class IndirectLengthProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pages = doc.getNumberOfPages();
            PDPage page = doc.getPage(0);
            COSDictionary pageDict = page.getCOSObject();
            COSBase contents = pageDict.getDictionaryObject(COSName.CONTENTS);
            long resolvedLen = -1;
            if (contents instanceof COSStream) {
                COSStream s = (COSStream) contents;
                COSBase lenItem = s.getDictionaryObject(COSName.LENGTH);
                if (lenItem instanceof COSNumber) {
                    resolvedLen = ((COSNumber) lenItem).longValue();
                }
            }
            String text = new PDFTextStripper().getText(doc);
            StringBuilder sb = new StringBuilder();
            sb.append("pages=").append(pages).append('\n');
            sb.append("length=").append(resolvedLen).append('\n');
            sb.append("text=").append(escape(text)).append('\n');
            out.print(sb);
        } catch (Exception ex) {
            out.print("PARSE_FAIL\n");
        }
    }

    private static String escape(String s) {
        StringBuilder b = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '\\') {
                b.append("\\\\");
            } else if (c == '\n') {
                b.append("\\n");
            } else if (c == '\r') {
                b.append("\\r");
            } else {
                b.append(c);
            }
        }
        return b.toString();
    }
}
