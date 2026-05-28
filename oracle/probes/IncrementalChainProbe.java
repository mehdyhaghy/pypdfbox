import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for a chain of sequential incremental revisions.
 *
 * A PDF can carry multiple revisions in a single file: each
 * {@code saveIncremental} appends a new xref section + trailer at the end,
 * with the new trailer's {@code /Prev} pointing at the previous revision's
 * {@code startxref} offset. A parser must read the LAST trailer first and
 * then walk {@code /Prev} backwards through the chain so the latest version
 * of every object wins (PDF 32000-1 §7.5.6).
 *
 * Mode: one argument — the PDF to inspect. Output is line-oriented UTF-8
 * (key=value), with the text= line last so its embedded newlines stay
 * uncorrupted:
 *
 *   pages         = page count
 *   author        = /Info /Author        (LATEST revision wins)
 *   subject       = /Info /Subject       (LATEST revision wins)
 *   title         = /Info /Title         (LATEST revision wins)
 *   producer      = /Info /Producer
 *   xref_sections = count of "startxref" markers in the raw file bytes
 *                   (base + each incremental revision contributes one)
 *   text          = PDFTextStripper output, raw, last on stdout
 *
 * "NULL" marks an absent string entry so the Python side can tell a missing
 * key from an empty string. The xref_sections counter scans the raw bytes
 * because PDFBox merges all revisions into a single in-memory xref table
 * once loaded; the on-disk section count is what tells us whether the file
 * was actually written as a chain of incremental revisions.
 */
public final class IncrementalChainProbe {

    private static String nz(String v) {
        return v == null ? "NULL" : v;
    }

    private static int countOccurrences(byte[] haystack, byte[] needle) {
        int count = 0;
        int i = 0;
        outer:
        while (i <= haystack.length - needle.length) {
            for (int j = 0; j < needle.length; j++) {
                if (haystack[i + j] != needle[j]) {
                    i++;
                    continue outer;
                }
            }
            count++;
            i += needle.length;
        }
        return count;
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File file = new File(args[0]);
        byte[] bytes = Files.readAllBytes(file.toPath());
        int xrefSections = countOccurrences(bytes, "startxref".getBytes("ISO-8859-1"));
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(file)) {
            PDDocumentInformation info = doc.getDocumentInformation();
            sb.append("pages=").append(doc.getNumberOfPages()).append("\n");
            sb.append("author=").append(nz(info.getAuthor())).append("\n");
            sb.append("subject=").append(nz(info.getSubject())).append("\n");
            sb.append("title=").append(nz(info.getTitle())).append("\n");
            sb.append("producer=").append(nz(info.getProducer())).append("\n");
            sb.append("xref_sections=").append(xrefSections).append("\n");
            String text = new PDFTextStripper().getText(doc);
            sb.append("text=").append(text);
        }
        out.print(sb);
    }
}
