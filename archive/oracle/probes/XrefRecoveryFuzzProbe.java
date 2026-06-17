import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Differential parse-leniency fuzz probe for the PDF 1.5+ cross-reference
 * STREAM read path AS DRIVEN THROUGH THE WHOLE-FILE LOADER, plus the xref-stream
 * /Prev chain walk and the brute-force rebuild that fires when the stream xref
 * is unusable, Apache PDFBox 3.0.7 (wave 1543, agent A).
 *
 * <h2>How this complements the existing xref probes</h2>
 * <ul>
 *   <li>{@code XrefStreamFuzzProbe} (wave 1512) drives the
 *       {@code PDFXrefStreamParser} stream DECODER in isolation against a
 *       malformed {@code /W} // {@code /Index} // {@code /Size} geometry — it
 *       never goes through {@code Loader.loadPDF}, so the {@code startxref}
 *       resolution, the {@code /Prev} chain walk and the brute-force rebuild
 *       are NOT exercised.</li>
 *   <li>{@code XrefTableFuzzProbe} (wave 1516) and {@code TrailerRebuildFuzzProbe}
 *       (wave 1517) DO drive whole tiny PDFs through the loader, but every case
 *       they build uses the CLASSIC {@code xref} keyword table — none builds a
 *       PDF whose cross-reference is a {@code /Type /XRef} STREAM.</li>
 *   <li>{@code HybridXrefProbe} / {@code XRefStreamTrailerProbe} /
 *       {@code XrefWFieldsProbe} pin VALID xref streams only.</li>
 * </ul>
 * This probe fills the gap: it hand-builds ~30 tiny WHOLE PDFs whose
 * cross-reference is a {@code /Type /XRef} stream with deliberately malformed
 * geometry ({@code /W} arity / negative / sum&gt;20; {@code /Index} odd / empty
 * / overrunning {@code /Size}; {@code /Size} mismatch; truncated body), a
 * broken {@code /Prev} chain between two xref STREAMS (cyclic / dangling /
 * negative), a missing trailer {@code /Root}, and a stream xref so corrupt the
 * loader must brute-force rebuild from raw {@code n g obj} headers. It drives
 * the whole-file parse, the {@code startxref}-&gt;stream resolution, the
 * {@code /Prev} walk and (when those fail) the rebuild end-to-end.
 *
 * <h2>Input grammar (file-driven, SAME bytes drive both sides)</h2>
 * The pypdfbox sibling
 * (tests/pdfparser/oracle/test_xref_recovery_fuzz_wave1543.py) hand-crafts the
 * raw PDF bytes per case, writes each {@code <case>.pdf} into a directory plus a
 * {@code manifest.txt} (one case name per line, in order). This probe reads the
 * manifest and loads each {@code <case>.pdf} with the empty / default password.
 *
 * <h2>Output grammar (one line per case, manifest order)</h2>
 * <pre>
 *   CASE &lt;name&gt; loaded=&lt;1|ERR:&lt;ExcSimpleName&gt;&gt; pages=&lt;n|?&gt; root=&lt;present|absent|?&gt; nobj=&lt;count|?&gt; enc=&lt;0|1|?&gt;
 * </pre>
 * {@code loaded=ERR:&lt;X&gt;} means {@code Loader.loadPDF} threw exception class
 * X (then the other fields are all {@code ?}). On success {@code loaded=1};
 * {@code pages} is {@code getNumberOfPages()} (or {@code ?} if that throws),
 * {@code root} is {@code present} when the catalog resolves else {@code absent}
 * (or {@code ?} on throw), {@code nobj} is the count of resolved object keys in
 * the COS xref table — the size of the recovered/parsed object set — and
 * {@code enc} is {@code 1} when the document reports itself encrypted.
 *
 * <p>Exception CLASS names differ across runtimes (Java {@code IOException}
 * family vs pypdfbox {@code PDFParseError} // {@code OSError}); the sibling
 * compares the {@code ERR} arm on the THROW BOOLEAN only and asserts the
 * success-arm fields verbatim. Defensible robustness divergences are pinned
 * both-sides with a CHANGES.md citation.
 */
public final class XrefRecoveryFuzzProbe {

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

    static String enc(PDDocument doc) {
        try {
            return doc.isEncrypted() ? "1" : "0";
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
            sb.append(" enc=").append(enc(doc));
        } catch (Throwable t) {
            sb.append("loaded=ERR:").append(t.getClass().getSimpleName());
            sb.append(" pages=? root=? nobj=? enc=?");
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
