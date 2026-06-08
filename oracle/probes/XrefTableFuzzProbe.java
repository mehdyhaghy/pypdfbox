import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Differential parse-leniency fuzz probe for the CLASSIC cross-reference
 * {@code xref}-table + {@code trailer} keyword parse path and its broken-xref
 * recovery (brute-force rebuild), Apache PDFBox 3.0.7 (wave 1516, agent B).
 *
 * <h2>How this complements {@code XrefStreamFuzzProbe}</h2>
 * {@code XrefStreamFuzzProbe} (wave 1512) drives the PDF 1.5+ cross-reference
 * STREAM decoder ({@code PDFXrefStreamParser}) in isolation against a malformed
 * {@code /W} // {@code /Index} // {@code /Size} geometry. This probe targets the
 * DISTINCT classic {@code xref} keyword path: subsection headers
 * ({@code <start> <count>}), 20-byte entry framing
 * ({@code nnnnnnnnnn ggggg n\r\n} / {@code ... f}), the {@code trailer}
 * dictionary ({@code /Size} // {@code /Root} // {@code /Prev} //
 * {@code /XRefStm}), the {@code startxref} pointer, and {@code %%EOF}. It drives
 * WHOLE tiny PDFs through {@code Loader.loadPDF} so the table/trailer parse,
 * the {@code /Prev} chain walk, the hybrid-reference {@code /XRefStm} merge, and
 * (when those fail) the brute-force object rebuild are all exercised end-to-end.
 *
 * <h2>Input grammar (file-driven, SAME bytes drive both sides)</h2>
 * The pypdfbox sibling
 * (tests/pdfparser/oracle/test_xref_table_fuzz_wave1516.py) hand-crafts the raw
 * PDF bytes per case, writes each {@code <case>.pdf} into a directory plus a
 * {@code manifest.txt} (one case name per line, in order). This probe reads the
 * manifest and loads each {@code <case>.pdf} with the empty / default password.
 *
 * <h2>Output grammar (one line per case, manifest order)</h2>
 * <pre>
 *   CASE &lt;name&gt; loaded=&lt;1|ERR:&lt;ExcSimpleName&gt;&gt; pages=&lt;n|?&gt; root=&lt;present|absent|?&gt; nobj=&lt;count|?&gt;
 * </pre>
 * {@code loaded=ERR:&lt;X&gt;} means {@code Loader.loadPDF} threw exception class
 * X (then pages/root/nobj are all {@code ?}). On success {@code loaded=1};
 * {@code pages} is {@code getNumberOfPages()} (or {@code ?} if that throws),
 * {@code root} is {@code present} when the catalog resolves else {@code absent}
 * (or {@code ?} on throw), and {@code nobj} is the count of resolved object keys
 * in the COS xref table — the size of the recovered/parsed object set. These
 * fields capture whether the table/trailer resolved and whether recovery
 * (rebuild) kicked in.
 *
 * <p>Exception CLASS names differ across runtimes (Java {@code IOException}
 * family vs pypdfbox {@code PDFParseError} // {@code OSError}); the sibling
 * compares the {@code ERR} arm on the THROW BOOLEAN only and asserts the
 * success-arm fields verbatim. Defensible robustness divergences are pinned
 * both-sides with a CHANGES.md citation.
 */
public final class XrefTableFuzzProbe {

    static PrintStream out;

    static String pages(PDDocument doc) {
        try {
            return Integer.toString(doc.getNumberOfPages());
        } catch (Throwable t) {
            return "?";
        }
    }

    static String root(PDDocument doc) {
        try {
            return doc.getDocumentCatalog() != null ? "present" : "absent";
        } catch (Throwable t) {
            return "?";
        }
    }

    static String nobj(PDDocument doc) {
        try {
            COSDocument cos = doc.getDocument();
            int n = 0;
            for (COSObjectKey ignored : cos.getXrefTable().keySet()) {
                n++;
            }
            return Integer.toString(n);
        } catch (Throwable t) {
            return "?";
        }
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf, "");
            sb.append("loaded=1");
            sb.append(" pages=").append(pages(doc));
            sb.append(" root=").append(root(doc));
            sb.append(" nobj=").append(nobj(doc));
        } catch (Throwable t) {
            sb.append("loaded=ERR:").append(t.getClass().getSimpleName());
            sb.append(" pages=? root=? nobj=?");
        } finally {
            if (doc != null) {
                try {
                    doc.close();
                } catch (Exception ignored) {
                    // best-effort close
                }
            }
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        Arrays.stream(names)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(name -> runCase(dir, name));
    }
}
