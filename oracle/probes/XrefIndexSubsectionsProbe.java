import java.io.File;
import java.io.PrintStream;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for xref-stream ``/Index`` multi-subsection parsing.
 *
 * PDF 32000-1 §7.5.8.2: a cross-reference stream's ``/Index`` array is a
 * sequence of ``[start_1 count_1 start_2 count_2 ...]`` pairs. Each pair
 * names a contiguous block of object numbers; the encoded xref rows map
 * onto those object numbers in order across all subsections. When
 * ``/Index`` is absent the default is ``[0 Size]`` (one contiguous block).
 *
 * A non-contiguous ``/Index`` (e.g. ``[0 1 5 3]`` → object 0, then objects
 * 5,6,7) makes the row→object-number mapping non-trivial: a parser that
 * ignores ``/Index`` and assumes ``0..Size-1`` mis-numbers every object
 * after the first subsection, so the catalog / page tree / content stream
 * resolves to the wrong bytes (or not at all).
 *
 * Mode (one ``key=value`` per line on stdout; the ``text=`` line is
 * emitted last and verbatim so its newlines are preserved):
 *
 *   facts file.pdf
 *       pages        = page count
 *       object_count = COSDocument.getXrefTable().size()
 *       xref=OBJNUM:GEN:OFFSET (one line per resolved key, sorted by
 *                               object number then generation; OFFSET is
 *                               the raw value PDFBox stored — negative for
 *                               object-stream membership)
 *       text         = PDFTextStripper output, raw, last on stdout
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> XrefIndexSubsectionsProbe facts file.pdf
 */
public final class XrefIndexSubsectionsProbe {
    public static void main(String[] args) throws Exception {
        if (!"facts".equals(args[0])) {
            throw new IllegalArgumentException("unknown mode: " + args[0]);
        }
        String file = args[1];
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(file))) {
            sb.append("pages=").append(doc.getNumberOfPages()).append("\n");
            Map<COSObjectKey, Long> xref = doc.getDocument().getXrefTable();
            sb.append("object_count=").append(xref.size()).append("\n");
            TreeMap<long[], Long> sorted = new TreeMap<>((a, b) -> {
                if (a[0] != b[0]) {
                    return Long.compare(a[0], b[0]);
                }
                return Long.compare(a[1], b[1]);
            });
            for (Map.Entry<COSObjectKey, Long> e : xref.entrySet()) {
                COSObjectKey k = e.getKey();
                sorted.put(new long[] {k.getNumber(), k.getGeneration()}, e.getValue());
            }
            for (Map.Entry<long[], Long> e : sorted.entrySet()) {
                long[] k = e.getKey();
                sb.append("xref=").append(k[0]).append(":").append(k[1])
                  .append(":").append(e.getValue()).append("\n");
            }
            String text = new PDFTextStripper().getText(doc);
            sb.append("text=").append(text);
        }
        out.print(sb);
    }
}
