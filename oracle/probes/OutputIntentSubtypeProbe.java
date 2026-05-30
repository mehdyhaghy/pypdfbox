import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.graphics.color.PDOutputIntent;

import java.io.File;

/**
 * Live oracle probe: emit Apache PDFBox's view of the /S subtype and the
 * embedded ICC profile's /N (number of colour components) for every
 * /OutputIntent in a PDF.
 *
 * PDFBox 3.0's PDOutputIntent exposes no getSubtype() / getN() accessor, so
 * the subtype is read straight off the output-intent COSDictionary via /S and
 * /N off the /DestOutputProfile stream dictionary — exactly the raw entries
 * pypdfbox's get_subtype() / get_n_for_profile() resolve.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> OutputIntentSubtypeProbe input.pdf
 *
 * Output: a "count=" header, then one block per intent:
 *   intent <i>
 *   subtype=<getCOSObject().getNameAsString(COSName.S)>   (or "null")
 *   n=<DestOutputProfile stream /N int, or -1 when absent/no profile>
 *
 * Null subtype is emitted as the literal token "null" so the Python side maps
 * it to None unambiguously.
 */
public final class OutputIntentSubtypeProbe {
    private static String s(String v) {
        return v == null ? "null" : v;
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            List<PDOutputIntent> intents = catalog.getOutputIntents();
            out.println("count=" + intents.size());
            for (int i = 0; i < intents.size(); i++) {
                PDOutputIntent oi = intents.get(i);
                out.println("intent " + i);
                String subtype = oi.getCOSObject().getNameAsString(COSName.S);
                out.println("subtype=" + s(subtype));
                COSStream profile = oi.getDestOutputIntent();
                int n = -1;
                if (profile != null) {
                    n = profile.getInt(COSName.N);
                }
                out.println("n=" + n);
            }
        }
    }
}
