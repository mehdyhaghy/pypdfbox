import java.io.File;
import java.io.PrintStream;
import java.util.List;

import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSignature;

/**
 * Live oracle probe: report the signature-dictionary STRUCTURE of a prepared /
 * signed PDF exactly as Apache PDFBox parses it — the /Type, /Filter,
 * /SubFilter name fields plus the reserved /Contents placeholder size.
 *
 * This is the companion to {@code ByteRangeProbe} (which checks the /ByteRange
 * byte-offset arithmetic). The point here is the *dictionary identity*: when a
 * PDF is prepared for external signing, PDFBox must read back
 *   /Type    -> Sig
 *   /Filter  -> Adobe.PPKLite
 *   /SubFilter -> adbe.pkcs7.detached
 * and a /Contents hex placeholder whose decoded length is the reserved size.
 *
 * getContents() decodes the /Contents hex string to its raw byte form (the
 * zero-padded placeholder), so its length == half the reserved hex width.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SignatureDictProbe prepared.pdf
 * Output (stdout, one key=value per line):
 *   count=<number of signature dicts>
 *   sig.0.type=<COSName of /Type, or null>
 *   sig.0.filter=<String of /Filter, or null>
 *   sig.0.subfilter=<String of /SubFilter, or null>
 *   sig.0.contentsLen=<getContents().length, raw decoded bytes>
 *   sig.0.name=<String of /Name, or null>
 */
public final class SignatureDictProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File file = new File(args[0]);

        try (PDDocument doc = Loader.loadPDF(file)) {
            List<PDSignature> sigs = doc.getSignatureDictionaries();
            out.println("count=" + sigs.size());
            int i = 0;
            for (PDSignature sig : sigs) {
                String prefix = "sig." + i + ".";

                COSDictionary cd = sig.getCOSObject();
                COSBase typeVal = cd.getDictionaryObject(COSName.TYPE);
                String typeStr =
                        (typeVal instanceof COSName)
                                ? ((COSName) typeVal).getName()
                                : "null";
                out.println(prefix + "type=" + typeStr);

                String filter = sig.getFilter();
                out.println(prefix + "filter=" + (filter == null ? "null" : filter));

                String subFilter = sig.getSubFilter();
                out.println(
                        prefix + "subfilter="
                                + (subFilter == null ? "null" : subFilter));

                byte[] contents = sig.getContents();
                out.println(
                        prefix + "contentsLen="
                                + (contents == null ? -1 : contents.length));

                String name = sig.getName();
                out.println(prefix + "name=" + (name == null ? "null" : name));
                i++;
            }
        }
    }
}
