import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDMarkInfo;
import org.apache.pdfbox.pdmodel.graphics.color.PDOutputIntent;

/**
 * Live oracle probe: emit Apache PDFBox's view of a PDF's *secondary* catalog
 * metadata — the entries the wave-1440 surface targets:
 *
 *   /OutputIntents  (count + per-intent subtype / conditionId / info / profile)
 *   /MarkInfo       (isMarked / userProperties / suspects)
 *   /Lang           (document language)
 *   /Metadata       (XMP stream presence)
 *   /StructTreeRoot (presence)
 *   /Collection     (/View mode — read off the raw catalog dictionary because
 *                    PDFBox 3.0.7 has no typed PDCollection accessor)
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> CatalogMetaProbe input.pdf
 *
 * Output: canonical, line-oriented (UTF-8, stdout, no framing). Null string
 * fields render as the literal token "null"; booleans as "true"/"false".
 */
public final class CatalogMetaProbe {

    private static String s(String v) {
        return v == null ? "null" : v;
    }

    private static String b(boolean v) {
        return v ? "true" : "false";
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog cat = doc.getDocumentCatalog();

            // ---- /OutputIntents ----
            List<PDOutputIntent> intents = cat.getOutputIntents();
            out.println("outputIntents.count=" + intents.size());
            for (int i = 0; i < intents.size(); i++) {
                PDOutputIntent oi = intents.get(i);
                String subtype = null;
                COSBase sBase = oi.getCOSObject().getDictionaryObject(COSName.S);
                if (sBase instanceof COSName) {
                    subtype = ((COSName) sBase).getName();
                }
                out.println("outputIntent[" + i + "].subtype=" + s(subtype));
                out.println("outputIntent[" + i + "].conditionId="
                        + s(oi.getOutputConditionIdentifier()));
                out.println("outputIntent[" + i + "].info=" + s(oi.getInfo()));
                out.println("outputIntent[" + i + "].hasProfile="
                        + b(oi.getDestOutputIntent() != null));
            }

            // ---- /MarkInfo ----
            PDMarkInfo mark = cat.getMarkInfo();
            out.println("markInfo.present=" + b(mark != null));
            out.println("markInfo.isMarked=" + b(mark != null && mark.isMarked()));
            out.println("markInfo.userProperties="
                    + b(mark != null && mark.usesUserProperties()));
            out.println("markInfo.suspects="
                    + b(mark != null && mark.isSuspect()));

            // ---- /Lang ----
            out.println("language=" + s(cat.getLanguage()));

            // ---- /Metadata (XMP stream presence) ----
            out.println("metadata.present=" + b(cat.getMetadata() != null));

            // ---- /StructTreeRoot presence ----
            out.println("structTreeRoot.present="
                    + b(cat.getStructureTreeRoot() != null));

            // ---- /Collection /View ----
            COSBase coll = cat.getCOSObject()
                    .getDictionaryObject(COSName.COLLECTION);
            out.println("collection.present=" + b(coll instanceof COSDictionary));
            String view = null;
            if (coll instanceof COSDictionary) {
                COSBase viewBase = ((COSDictionary) coll)
                        .getDictionaryObject(COSName.getPDFName("View"));
                if (viewBase instanceof COSName) {
                    view = ((COSName) viewBase).getName();
                }
            }
            out.println("collection.view=" + s(view));
        }
    }
}
