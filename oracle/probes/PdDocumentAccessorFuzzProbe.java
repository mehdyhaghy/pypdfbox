import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Differential leniency fuzz probe for the {@code PDDocument} top-level
 * read-accessor surface over MALFORMED / EDGE document state, Apache PDFBox
 * 3.0.7 (wave 1537, agent D).
 *
 * Complements the catalog / doc-info / doc-nav fuzz probes (which drive the
 * sub-dictionaries directly) by driving the PDDocument facade itself —
 * {@code getNumberOfPages}, {@code getPage(int)}, {@code getDocumentCatalog},
 * {@code getDocumentInformation}, {@code getVersion}, {@code isEncrypted} — over
 * documents whose /Root is missing or mistyped, whose /Pages is missing or has
 * a /Count that lies, whose header / catalog versions disagree, and whose
 * /Encrypt is present or absent.
 *
 * Both sides run on the SAME bytes: pypdfbox builds one {@code <case>.pdf} per
 * malformed-state case plus a {@code manifest.txt} into a tmp dir; this probe
 * loads each file and projects a stable framed line; the Python module reads the
 * identical files and projects the identical grammar, then asserts line parity.
 *
 * Line grammar (one per case, manifest order)::
 *
 *   CASE <name> numpages=<int|ERR:X> page0=<ok|ERR:X> pageN=<ok|ERR:X>
 *       version=<float|ERR:X> encrypted=<bool|ERR:X>
 *       hascatalog=<bool|ERR:X> hasinfo=<bool|ERR:X>
 *
 * where pageN probes {@code getPage(numpages)} (one past the last valid index)
 * to surface the out-of-range exception class. The catalog / info cells project
 * presence: whether {@code getDocumentCatalog()} / {@code getDocumentInformation()}
 * return a non-null wrapper (both upstream accessors auto-materialise, so these
 * are normally true; the interesting signal is the ERR token when a malformed
 * /Root makes materialisation throw).
 */
public final class PdDocumentAccessorFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()), "UTF-8")
                        .split("\\R");

        StringBuilder sb = new StringBuilder();
        for (String name : names) {
            if (name.isEmpty()) {
                continue;
            }
            sb.append(line(dir, name)).append('\n');
        }
        out.print(sb);
        out.flush();
    }

    private static String line(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
        } catch (Throwable t) {
            return "CASE " + name + " LOAD:" + t.getClass().getSimpleName();
        }
        try {
            return "CASE " + name
                    + " numpages=" + numPagesCell(doc)
                    + " page0=" + pageCell(doc, 0)
                    + " pageN=" + pageCellPastEnd(doc)
                    + " version=" + versionCell(doc)
                    + " encrypted=" + encryptedCell(doc)
                    + " hascatalog=" + catalogCell(doc)
                    + " hasinfo=" + infoCell(doc);
        } finally {
            try {
                doc.close();
            } catch (Exception ignore) {
                // closing a probe document never matters for the result.
            }
        }
    }

    private static String numPagesCell(PDDocument doc) {
        try {
            return Integer.toString(doc.getNumberOfPages());
        } catch (Throwable t) {
            return "ERR:" + t.getClass().getSimpleName();
        }
    }

    private static String pageCell(PDDocument doc, int index) {
        try {
            return doc.getPage(index) != null ? "ok" : "null";
        } catch (Throwable t) {
            return "ERR:" + t.getClass().getSimpleName();
        }
    }

    private static String pageCellPastEnd(PDDocument doc) {
        int n;
        try {
            n = doc.getNumberOfPages();
        } catch (Throwable t) {
            return "ERR:" + t.getClass().getSimpleName();
        }
        return pageCell(doc, n);
    }

    private static String versionCell(PDDocument doc) {
        try {
            return Float.toString(doc.getVersion());
        } catch (Throwable t) {
            return "ERR:" + t.getClass().getSimpleName();
        }
    }

    private static String encryptedCell(PDDocument doc) {
        try {
            return Boolean.toString(doc.isEncrypted());
        } catch (Throwable t) {
            return "ERR:" + t.getClass().getSimpleName();
        }
    }

    private static String catalogCell(PDDocument doc) {
        try {
            return Boolean.toString(doc.getDocumentCatalog() != null);
        } catch (Throwable t) {
            return "ERR:" + t.getClass().getSimpleName();
        }
    }

    private static String infoCell(PDDocument doc) {
        try {
            return Boolean.toString(doc.getDocumentInformation() != null);
        } catch (Throwable t) {
            return "ERR:" + t.getClass().getSimpleName();
        }
    }
}
