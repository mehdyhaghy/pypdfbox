import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdfwriter.compress.CompressParameters;

/**
 * Live oracle probe: build a fresh PDDocument in memory (NOT loaded from disk),
 * full-save it UNCOMPRESSED (classic xref table), reload the saved bytes, and
 * emit the object-number assignment the writer chose for each indirect object,
 * tagged with its structural ROLE.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SaveObjectOrderProbe <numPages>
 *
 * The full-save object-numbering contract (ISO 32000 leaves numbering free, but
 * PDFBox's COSWriter assigns numbers by a deterministic breadth-first walk
 * seeded from the trailer's /Root then /Info then /Encrypt). For a document
 * created with `new PDDocument()` + N blank pages this produces a fixed
 * numbering that a port must reproduce so cross-tool diffs stay stable.
 *
 * Output (UTF-8, LF-terminated), sorted by object number:
 *
 *   count=<N>
 *   <objNum> <genNum>: <role>
 *
 * Roles (derived from /Type or position in the catalog graph, NOT from the
 * object's own number, so they are numbering-independent):
 *   catalog | pages | page | resources | content | font | other
 *
 * This lets the pypdfbox side assert the SAME role lands on the SAME object
 * number after its own full save — i.e. the writers agree on traversal order.
 */
public final class SaveObjectOrderProbe {

    public static void main(String[] args) throws Exception {
        int numPages = args.length > 0 ? Integer.parseInt(args[0]) : 1;

        byte[] saved;
        try (PDDocument doc = new PDDocument()) {
            for (int i = 0; i < numPages; i++) {
                doc.addPage(new PDPage(PDRectangle.LETTER));
            }
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            // Save UNCOMPRESSED (classic xref table, free-standing objects) so
            // the numbering is comparable to pypdfbox's full-save default,
            // which always emits an uncompressed classic-table file. PDFBox's
            // default would pack objects into an /ObjStm + /XRef stream, which
            // is a separate (documented) divergence, not the surface here.
            doc.save(bos, CompressParameters.NO_COMPRESSION);
            saved = bos.toByteArray();
        }

        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument pd = Loader.loadPDF(saved)) {
            COSDocument cos = pd.getDocument();
            // Resolve the catalog + pages node so we can role-tag by identity.
            COSDictionary catalog = pd.getDocumentCatalog().getCOSObject();
            COSBase pagesBase = catalog.getDictionaryObject(COSName.PAGES);
            COSDictionary pagesNode =
                    pagesBase instanceof COSDictionary ? (COSDictionary) pagesBase : null;

            java.util.TreeMap<Long, COSObjectKey> sorted = new java.util.TreeMap<>();
            for (COSObjectKey key : cos.getXrefTable().keySet()) {
                sorted.put(key.getNumber(), key);
            }

            StringBuilder sb = new StringBuilder();
            sb.append("count=").append(sorted.size()).append('\n');
            for (java.util.Map.Entry<Long, COSObjectKey> e : sorted.entrySet()) {
                COSObjectKey key = e.getValue();
                COSBase resolved;
                try {
                    resolved = cos.getObjectFromPool(key).getObject();
                } catch (Exception ex) {
                    resolved = null;
                }
                sb.append(key.getNumber()).append(' ').append(key.getGeneration())
                        .append(": ").append(role(resolved, catalog, pagesNode))
                        .append('\n');
            }
            out.print(sb);
        }
    }

    private static String role(COSBase base, COSDictionary catalog, COSDictionary pagesNode) {
        if (base instanceof COSObject) {
            base = ((COSObject) base).getObject();
        }
        if (!(base instanceof COSDictionary)) {
            return "other";
        }
        COSDictionary d = (COSDictionary) base;
        if (d == catalog) {
            return "catalog";
        }
        if (d == pagesNode) {
            return "pages";
        }
        COSBase typeBase = d.getDictionaryObject(COSName.TYPE);
        if (typeBase instanceof COSName) {
            String t = ((COSName) typeBase).getName();
            if ("Catalog".equals(t)) {
                return "catalog";
            }
            if ("Pages".equals(t)) {
                return "pages";
            }
            if ("Page".equals(t)) {
                return "page";
            }
            if ("Font".equals(t)) {
                return "font";
            }
        }
        if (d.containsKey(COSName.MEDIA_BOX) && d.containsKey(COSName.PARENT)) {
            return "page";
        }
        return "other";
    }
}
