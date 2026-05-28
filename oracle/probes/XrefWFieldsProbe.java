import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for xref-stream ``/W`` field-width parsing.
 *
 * PDF 32000-1 §7.5.8.3: the ``/W`` array of an xref stream specifies the
 * byte width of each entry's three fields (type / offset-or-objnum /
 * gen-or-index). PDFBox tolerates any reasonable combination — compact
 * ``[1 2 1]`` for small files all the way up to ``[1 8 2]`` for huge
 * (>4 GiB) files with 8-byte offsets. A parser that wires the widths in
 * via a fixed-size integer or mis-shifts a byte loses every offset.
 *
 * Mode (one ``key=value`` per line on stdout; the ``text=`` line is
 * emitted last and verbatim so its newlines are preserved):
 *
 *   facts file.pdf
 *       pages        = page count
 *       object_count = COSDocument.getXrefTable().size()
 *       text         = PDFTextStripper output, raw, last on stdout
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> XrefWFieldsProbe facts file.pdf
 */
public final class XrefWFieldsProbe {
    public static void main(String[] args) throws Exception {
        if (!"facts".equals(args[0])) {
            throw new IllegalArgumentException("unknown mode: " + args[0]);
        }
        String file = args[1];
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(file))) {
            sb.append("pages=").append(doc.getNumberOfPages()).append("\n");
            sb.append("object_count=")
              .append(doc.getDocument().getXrefTable().size()).append("\n");
            String text = new PDFTextStripper().getText(doc);
            sb.append("text=").append(text);
        }
        out.print(sb);
    }
}
